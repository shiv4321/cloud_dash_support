from __future__ import annotations

import json
from unittest.mock import MagicMock

from api.models import ConversationState, Message
from agents.triage_agent import TriageAgent
from agents.technical_agent import TechnicalAgent
from agents.billing_agent import BillingAgent


def _mock_tool_response(args: dict):
    call = MagicMock()
    call.function.arguments = json.dumps(args)
    msg = MagicMock()
    msg.tool_calls = [call]
    return MagicMock(choices=[MagicMock(message=msg)])


def _mock_chat_response(content: str):
    return MagicMock(choices=[MagicMock(message=MagicMock(content=content))])


def _mock_rag_result():
    return MagicMock(
        needs_escalation=False,
        chunks=[],
        sources=[],
        format_context=lambda: "",
    )


def test_triage_stores_secondary_followup_target():
    client = MagicMock()
    client.chat.completions.create.return_value = _mock_tool_response(
        {
            "intent": "technical",
            "secondary_intent": "billing",
            "customer_plan": "Pro",
            "urgency": "medium",
            "extracted_entities": {"issue_type": "sso"},
            "routing_target": "technical",
            "acknowledgement": "Let me first route your SSO issue to technical support.",
        }
    )

    cfg = {
        "name": "Triage Agent",
        "model": "gpt-4o",
        "temperature": 0.1,
        "system_prompt": "You are triage.",
        "routing_rules": {
            "technical": "technical",
            "billing": "billing",
            "account": "technical",
            "general": "technical",
            "unknown": "triage",
        },
    }
    agent = TriageAgent(cfg, client)

    state = ConversationState()
    state.history.append(
        Message(
            role="user",
            content="I want to upgrade from Pro to Enterprise, but first check my SSO issue.",
        )
    )

    response = agent.process(state)

    assert response.routing_target == "technical"
    assert state.entities.get("pending_followup_intent") == "billing"


def test_triage_forces_technical_first_when_primary_is_billing():
    client = MagicMock()
    client.chat.completions.create.return_value = _mock_tool_response(
        {
            "intent": "billing",
            "secondary_intent": "technical",
            "customer_plan": "Pro",
            "urgency": "medium",
            "extracted_entities": {"issue_type": "sso", "requested_plan": "Enterprise"},
            "routing_target": "billing",
            "acknowledgement": "I can help with both. Let me check the technical issue first.",
        }
    )

    cfg = {
        "name": "Triage Agent",
        "model": "gpt-4o",
        "temperature": 0.1,
        "system_prompt": "You are triage.",
        "routing_rules": {
            "technical": "technical",
            "billing": "billing",
            "account": "technical",
            "general": "technical",
            "unknown": "triage",
        },
    }
    agent = TriageAgent(cfg, client)

    state = ConversationState()
    state.history.append(
        Message(
            role="user",
            content="I want to upgrade to Enterprise, but first check if SSO was fixed.",
        )
    )

    response = agent.process(state)

    assert response.routing_target == "technical"
    assert state.entities.get("pending_followup_intent") == "billing"


def test_technical_handover_uses_pending_followup_without_keyword_trigger():
    client = MagicMock()
    client.chat.completions.create.return_value = _mock_chat_response(
        "Your SSO issue is resolved. Please test login once more."
    )
    rag = MagicMock()
    rag.run.return_value = _mock_rag_result()

    cfg = {
        "name": "Technical Support Agent",
        "model": "gpt-4o",
        "temperature": 0.2,
        "system_prompt": "You are technical support.",
        "can_handover_to": ["billing", "escalation"],
    }
    agent = TechnicalAgent(cfg, client, rag)

    state = ConversationState(current_agent="technical")
    state.entities["pending_followup_intent"] = "billing"
    state.history.append(Message(role="user", content="Please resolve my SSO issue first."))

    response = agent.process(state)

    assert response.routing_target == "billing"
    assert state.entities.get("pending_followup_intent") is None


def test_billing_handover_can_use_pending_technical_or_escalation():
    client = MagicMock()
    client.chat.completions.create.return_value = _mock_chat_response(
        "I reviewed your billing details and answered your question."
    )
    rag = MagicMock()
    rag.run.return_value = _mock_rag_result()

    cfg = {
        "name": "Billing Agent",
        "model": "gpt-4o",
        "temperature": 0.1,
        "system_prompt": "You are billing support.",
        "can_handover_to": ["technical", "escalation"],
    }
    agent = BillingAgent(cfg, client, rag)

    state = ConversationState(current_agent="billing")
    state.history.append(Message(role="user", content="Also help with a technical setup issue."))
    state.entities["pending_followup_intent"] = "technical"

    response = agent.process(state)
    assert response.routing_target == "technical"
    assert state.entities.get("pending_followup_intent") is None

    state2 = ConversationState(current_agent="billing")
    state2.history.append(Message(role="user", content="Please proceed."))
    state2.entities["pending_followup_intent"] = "escalation"

    response2 = agent.process(state2)
    assert response2.routing_target == "escalation"
    assert state2.entities.get("pending_followup_intent") is None
