"""
End-to-end scenario tests matching the 4 assessment scenarios.
These tests use mocked LLM + retriever so they run without live API keys.
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from api.models import ConversationState, Message
from retrieval.retriever import RetrievedChunk


def _chunk(article_id: str, title: str, text: str) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=f"{article_id}-0",
        article_id=article_id,
        title=title,
        category="troubleshooting",
        chunk_text=text,
        score=0.85,
    )


def _mock_openai_response(content: str):
    return MagicMock(choices=[MagicMock(message=MagicMock(content=content))])


def _mock_tool_response(args: dict):
    call = MagicMock()
    call.function.arguments = json.dumps(args)
    msg = MagicMock()
    msg.tool_calls = [call]
    return MagicMock(choices=[MagicMock(message=msg)])


@pytest.fixture(autouse=True)
def patch_pinecone():
    with patch("retrieval.retriever.Pinecone"):
        yield


class TestScenario1SingleAgentResolution:
    """Alerts not firing → Technical agent → KB retrieval → step-by-step with citation."""

    def test_routes_to_technical_and_cites_kb(self):
        with patch("agents.triage_agent.OpenAI") as mock_oa, \
             patch("agents.technical_agent.RAGChain") as mock_rag_cls, \
             patch("agents.technical_agent.OpenAI") as mock_tech_oa:

            triage_client = MagicMock()
            triage_client.chat.completions.create.return_value = _mock_tool_response({
                "intent": "technical",
                "routing_target": "technical",
                "urgency": "medium",
                "customer_plan": "Pro",
                "acknowledgement": "I can see your alerts stopped firing. Let me route you to our Technical Support Agent.",
                "extracted_entities": {"service": "aws", "issue": "alerts_not_firing"},
            })
            mock_oa.return_value = triage_client

            mock_rag = MagicMock()
            mock_rag.run.return_value = MagicMock(
                needs_escalation=False,
                chunks=[_chunk("KB-007", "Alerts Not Firing After Credential Update", "Step 1: Update credentials.")],
                sources=["KB-007 — Alerts Not Firing After Credential Update"],
                format_context=lambda: "[Source: KB-007]\nStep 1: Update credentials in CloudDash.",
            )
            mock_rag_cls.return_value = mock_rag

            tech_client = MagicMock()
            tech_client.chat.completions.create.return_value = _mock_openai_response(
                "According to KB-007 (Alerts Not Firing After Credential Update), "
                "you need to update your AWS credentials in Settings → Integrations → AWS → Edit. "
                "Step 1: Paste your new credentials. Step 2: Click Test Connection. "
                "Source: KB-007 — Alerts Not Firing After Credential Update"
            )
            mock_tech_oa.return_value = tech_client

            state = ConversationState()
            state.history.append(Message(
                role="user",
                content="My CloudDash alerts stopped firing after I updated my AWS integration credentials. I'm on the Pro plan."
            ))

            from agents.triage_agent import TriageAgent
            from agents.technical_agent import TechnicalAgent
            from config import agents as _  # noqa

            triage_cfg = {
                "name": "Triage Agent", "model": "gpt-4o", "temperature": 0.1,
                "system_prompt": "You are triage.",
                "routing_rules": {"technical": "technical"},
            }
            triage = TriageAgent(triage_cfg, triage_client)
            triage_response = triage.process(state)

            assert triage_response.routing_target == "technical"

            tech_cfg = {
                "name": "Technical Support Agent", "model": "gpt-4o", "temperature": 0.2,
                "system_prompt": "You are technical support.",
                "can_handover_to": ["billing", "escalation"],
            }
            tech = TechnicalAgent(tech_cfg, tech_client, mock_rag)
            tech_response = tech.process(state)

            assert "KB-007" in tech_response.content
            assert tech_response.sources


class TestScenario2CrossAgentHandover:
    """SSO issue + Enterprise upgrade → Technical → Billing handover."""

    def test_two_intent_handover(self):
        state = ConversationState()
        state.history.append(Message(
            role="user",
            content="I want to upgrade from Pro to Enterprise, but first check if the SSO integration issue was resolved."
        ))
        state.entities = {"customer_plan": "Pro"}

        from handover.audit_log import AuditLogger
        from handover.protocol import HandoverProtocol

        audit = AuditLogger()
        protocol = HandoverProtocol(audit)

        from api.models import AgentResponse
        tech_response = AgentResponse(
            agent="Technical Support Agent",
            content="SSO issue resolved. Source: KB-011",
            sources=["KB-011 — SSO Login Not Working"],
            routing_target="billing",
        )

        updated_state = protocol.execute(
            state=state,
            source_agent="technical",
            target_agent="billing",
            reason="Customer wants plan upgrade after SSO resolution",
            response=tech_response,
        )

        assert updated_state.current_agent == "billing"
        assert updated_state.handover_context.source_agent == "technical"
        assert updated_state.handover_context.entities.get("customer_plan") == "Pro"
        assert "SSO" in updated_state.handover_context.summary or updated_state.handover_count == 1


class TestScenario3EscalationToHuman:
    """Duplicate charge + refund request → Billing → Escalation with high urgency."""

    def test_billing_escalates_on_refund_request(self):
        with patch("agents.billing_agent.RAGChain") as mock_rag_cls, \
             patch("agents.billing_agent.OpenAI") as mock_oa:

            mock_rag = MagicMock()
            mock_rag.run.return_value = MagicMock(
                needs_escalation=False,
                chunks=[_chunk("KB-017", "Refund Policy", "Duplicate charges investigated in 2 business days.")],
                sources=["KB-017 — Refund and Cancellation Policy"],
                format_context=lambda: "[Source: KB-017]\nDuplicate charges investigated in 2 business days.",
            )
            mock_rag_cls.return_value = mock_rag

            billing_client = MagicMock()
            mock_oa.return_value = billing_client

            state = ConversationState()
            state.history.append(Message(
                role="user",
                content="I've been charged twice for April. I need an immediate refund and I want to speak to a manager."
            ))
            state.entities = {"customer_plan": "Pro"}

            from agents.billing_agent import BillingAgent
            billing_cfg = {
                "name": "Billing Agent", "model": "gpt-4o", "temperature": 0.1,
                "system_prompt": "You are billing.",
                "can_handover_to": ["technical", "escalation"],
            }
            billing = BillingAgent(billing_cfg, billing_client, mock_rag)
            response = billing.process(state)

            assert response.routing_target == "escalation"
            assert state.entities.get("urgency") == "high"


class TestScenario4KBRetrievalFailure:
    """Datadog integration question → KB miss → transparent escalation."""

    def test_kb_miss_triggers_escalation(self):
        with patch("agents.technical_agent.RAGChain") as mock_rag_cls, \
             patch("agents.technical_agent.OpenAI") as mock_oa:

            mock_rag = MagicMock()
            mock_rag.run.return_value = MagicMock(
                needs_escalation=True,
                chunks=[],
                sources=[],
            )
            mock_rag_cls.return_value = mock_rag

            tech_client = MagicMock()
            mock_oa.return_value = tech_client

            state = ConversationState()
            state.history.append(Message(
                role="user",
                content="Does CloudDash support integration with Datadog for cross-platform alerting?"
            ))

            from agents.technical_agent import TechnicalAgent
            tech_cfg = {
                "name": "Technical Support Agent", "model": "gpt-4o", "temperature": 0.2,
                "system_prompt": "You are technical support.",
                "can_handover_to": ["billing", "escalation"],
            }
            tech = TechnicalAgent(tech_cfg, tech_client, mock_rag)
            response = tech.process(state)

            assert response.routing_target == "escalation"
            assert "don't have" in response.content.lower() or "knowledge base" in response.content.lower()
