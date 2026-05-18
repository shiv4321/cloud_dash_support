from __future__ import annotations

from unittest.mock import MagicMock

from api.models import AgentResponse, ConversationState
from agents.orchestrator import Orchestrator


class _StubAgent:
    def __init__(self, name: str, responses: list[AgentResponse]) -> None:
        self.name = name
        self._responses = responses

    def process(self, state: ConversationState) -> AgentResponse:
        return self._responses.pop(0)


def _build_orchestrator(agents: dict[str, _StubAgent], handover: MagicMock) -> Orchestrator:
    orch = Orchestrator.__new__(Orchestrator)
    orch.client = None
    orch.audit = None
    orch.rag = None
    orch._configs = {}
    orch._agents = agents
    orch.handover = handover
    orch._lf = None
    return orch


def test_pending_followup_handover_returns_multi_messages_same_turn():
    triage = _StubAgent(
        "Triage Agent",
        [
            AgentResponse(
                agent="Triage Agent",
                content="Routing to technical.",
                routing_target="technical",
            )
        ],
    )
    technical = _StubAgent(
        "Technical Support Agent",
        [
            AgentResponse(
                agent="Technical Support Agent",
                content="SSO issue resolved. Please retest login now.",
                routing_target="billing",
                metadata={"handover_reason": "pending_followup"},
            )
        ],
    )
    billing = _StubAgent(
        "Billing Agent",
        [AgentResponse(agent="Billing Agent", content="Upgrade steps.", routing_target=None)],
    )

    def _handover_execute(state, source_agent, target_agent, reason, response):
        state.current_agent = target_agent
        state.handover_count += 1
        return state

    handover = MagicMock()
    handover.execute.side_effect = _handover_execute

    orch = _build_orchestrator(
        {"triage": triage, "technical": technical, "billing": billing, "escalation": billing},
        handover,
    )

    state = ConversationState()
    updated_state, responses = orch.handle_message_multi(
        state,
        "I want to upgrade, but first resolve my SSO issue.",
    )

    assert len(responses) == 3
    assert responses[0].agent == "Triage Agent"
    assert responses[1].agent == "Technical Support Agent"
    assert responses[2].agent == "Billing Agent"
    assert "SSO issue resolved" in responses[1].content
    assert "Upgrade steps." in responses[2].content
    assert updated_state.current_agent == "billing"
    assert handover.execute.call_count == 2


def test_model_signal_handover_remains_immediate():
    triage = _StubAgent(
        "Triage Agent",
        [
            AgentResponse(
                agent="Triage Agent",
                content="Routing to technical.",
                routing_target="technical",
            )
        ],
    )
    technical = _StubAgent(
        "Technical Support Agent",
        [
            AgentResponse(
                agent="Technical Support Agent",
                content="This needs billing team help.",
                routing_target="billing",
                metadata={"handover_reason": "model_signal"},
            )
        ],
    )
    billing = _StubAgent(
        "Billing Agent",
        [AgentResponse(agent="Billing Agent", content="Handled by billing.", routing_target=None)],
    )

    def _handover_execute(state, source_agent, target_agent, reason, response):
        state.current_agent = target_agent
        state.handover_count += 1
        return state

    handover = MagicMock()
    handover.execute.side_effect = _handover_execute

    orch = _build_orchestrator(
        {"triage": triage, "technical": technical, "billing": billing, "escalation": billing},
        handover,
    )

    state = ConversationState()
    updated_state, response = orch.handle_message(
        state,
        "I have a billing issue tied to technical setup.",
    )

    assert response.agent == "Billing Agent"
    assert "Handled by billing." in response.content
    assert updated_state.current_agent == "billing"
    assert handover.execute.call_count == 2
