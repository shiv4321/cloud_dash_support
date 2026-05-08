from __future__ import annotations

import logging
from typing import Any

from openai import OpenAI

from agents.base_agent import BaseAgent
from api.models import AgentResponse, ConversationState
from handover.audit_log import AuditLogger

log = logging.getLogger(__name__)

_SLA_BY_PLAN = {
    "Enterprise": "1 business hour",
    "Pro": "8 business hours",
    "Starter": "3 business days",
    "unknown": "3 business days",
}


class EscalationAgent(BaseAgent):
    def __init__(self, config: dict[str, Any], openai_client: OpenAI, audit: AuditLogger) -> None:
        super().__init__(config, openai_client)
        self.audit = audit

    def process(self, state: ConversationState) -> AgentResponse:
        urgency = state.entities.get("urgency", "medium")
        plan = state.entities.get("customer_plan", "unknown")
        sla = _SLA_BY_PLAN.get(plan, _SLA_BY_PLAN["unknown"])
        ticket_ref = state.trace_id[:8].upper()

        summary = self._build_summary(state)
        augmented_system = (
            self.system_prompt
            + f"\n\nConversation summary for context:\n{summary}"
        )

        messages = self._build_messages(state)
        reply = self.client.chat.completions.create(
            model=self.model,
            temperature=self.temperature,
            messages=[{"role": "system", "content": augmented_system}] + messages,
        ).choices[0].message.content

        ticket_note = (
            f"\n\n---\nTicket #{ticket_ref} has been created with your full conversation context. "
            f"A specialist will reach out within {sla}. You will receive a confirmation email shortly."
        )

        self.audit.log_escalation(
            trace_id=state.trace_id,
            urgency=urgency,
            plan=plan,
            summary=summary,
            entities=state.entities,
        )

        log.info(
            "escalation trace_id=%s urgency=%s plan=%s ticket=%s",
            state.trace_id, urgency, plan, ticket_ref,
        )

        return AgentResponse(
            agent=self.name,
            content=reply + ticket_note,
            routing_target=None,
            metadata={
                "ticket_ref": ticket_ref,
                "urgency": urgency,
                "sla": sla,
                "escalated": True,
            },
        )

    def _build_summary(self, state: ConversationState) -> str:
        lines = [f"Trace ID: {state.trace_id}", f"Entities: {state.entities}"]
        lines.append("Conversation:")
        for msg in state.history[-6:]:
            lines.append(f"  [{msg.role}]: {msg.content[:200]}")
        return "\n".join(lines)
