from __future__ import annotations

import logging

from api.models import AgentResponse, ConversationState, HandoverContext
from handover.audit_log import AuditLogger

log = logging.getLogger(__name__)


class HandoverProtocol:
    def __init__(self, audit: AuditLogger) -> None:
        self.audit = audit

    def execute(
        self,
        state: ConversationState,
        source_agent: str,
        target_agent: str,
        reason: str,
        response: AgentResponse,
    ) -> ConversationState:
        summary = self._build_summary(state, response)

        context = HandoverContext(
            source_agent=source_agent,
            target_agent=target_agent,
            reason=reason,
            summary=summary,
            entities=dict(state.entities),
        )

        self.audit.log_handover(
            trace_id=state.trace_id,
            source_agent=source_agent,
            target_agent=target_agent,
            reason=reason,
            snapshot=context.model_dump(),
        )

        state.current_agent = target_agent
        state.handover_context = context
        state.handover_count += 1

        log.info(
            "handover trace_id=%s from=%s to=%s reason=%r count=%d",
            state.trace_id, source_agent, target_agent, reason, state.handover_count,
        )

        return state

    def _build_summary(self, state: ConversationState, response: AgentResponse) -> str:
        recent_history = state.history[-6:]
        lines = [
            f"Handover from {state.current_agent} after {state.handover_count} prior handovers.",
            f"Extracted entities: {state.entities}",
            "",
            "Recent conversation:",
        ]
        for msg in recent_history:
            lines.append(f"  [{msg.role}] {msg.content[:300]}")
        if response.sources:
            lines.append(f"\nKB sources consulted: {', '.join(response.sources)}")
        return "\n".join(lines)
