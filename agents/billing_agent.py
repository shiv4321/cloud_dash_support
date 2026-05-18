from __future__ import annotations

import logging
from typing import Any

from openai import OpenAI

from agents.base_agent import BaseAgent
from api.models import AgentResponse, ConversationState
from retrieval.rag_chain import RAGChain

log = logging.getLogger(__name__)

# Only escalate for active demands — NOT policy questions like "what is your refund policy?"
_ESCALATION_TRIGGERS = [
    "i need a refund",
    "i want a refund",
    "give me a refund",
    "issue a refund",
    "charged twice",
    "duplicate charge",
    "double charge",
    "double charged",
    "speak to a manager",
    "talk to a manager",
    "want to speak to",
    "want my money back",
    "overcharged",
    "wrongly charged",
    "demand a refund",
]


class BillingAgent(BaseAgent):
    def __init__(self, config: dict[str, Any], openai_client: OpenAI, rag: RAGChain) -> None:
        super().__init__(config, openai_client)
        self.rag = rag
        self.can_handover_to: list[str] = config.get("can_handover_to", [])

    def process(self, state: ConversationState) -> AgentResponse:
        last_user_msg = next(
            (m.content for m in reversed(state.history) if m.role == "user"), ""
        )

        if self._needs_escalation(last_user_msg, state):
            log.info("billing trace_id=%s action=escalate reason=demand_refund_or_manager", state.trace_id)
            state.entities["urgency"] = "high"
            return AgentResponse(
                agent=self.name,
                content=(
                    "I completely understand your frustration, and I want to make sure this is "
                    "resolved for you as quickly as possible. This type of request requires "
                    "authorization from our billing team. I'm escalating this now with high "
                    "priority so a specialist can assist you directly."
                ),
                routing_target="escalation",
                metadata={"escalation_reason": "refund_demand_or_manager_request"},
            )

        rag_result = self.rag.run(last_user_msg, state.history)
        context_block = rag_result.format_context() if not rag_result.needs_escalation else ""

        augmented_system = self.system_prompt
        if context_block:
            augmented_system += f"\n\n--- RETRIEVED BILLING POLICIES ---\n{context_block}\n---"

        messages = self._build_messages(state)
        full_messages = [{"role": "system", "content": augmented_system}] + messages

        reply = self.client.chat.completions.create(
            model=self.model,
            temperature=self.temperature,
            messages=full_messages,
        ).choices[0].message.content

        handover_target = self._detect_handover(reply, state)
        handover_reason = "model_signal" if handover_target else None
        if not handover_target:
            handover_target = self._consume_pending_followup(state)
            if handover_target:
                handover_reason = "pending_followup"

        log.info(
            "billing trace_id=%s chunks_used=%d handover=%s",
            state.trace_id, len(rag_result.chunks), handover_target or "none",
        )

        return AgentResponse(
            agent=self.name,
            content=reply,
            routing_target=handover_target,
            sources=rag_result.sources,
            metadata={
                "chunks_retrieved": len(rag_result.chunks),
                "handover_reason": handover_reason,
            },
        )

    def _needs_escalation(self, message: str, state: ConversationState) -> bool:
        msg_lower = message.lower()
        if any(trigger in msg_lower for trigger in _ESCALATION_TRIGGERS):
            return True
        if state.entities.get("urgency") == "critical":
            return True
        return False

    def _detect_handover(self, reply: str, state: ConversationState) -> str | None:
        reply_lower = reply.lower()
        if any(kw in reply_lower for kw in ["technical support", "technical agent", "technical team"]):
            if "technical" in self.can_handover_to:
                return "technical"
        if any(kw in reply_lower for kw in ["escalat", "human support"]):
            if "escalation" in self.can_handover_to:
                return "escalation"
        return None

    def _consume_pending_followup(self, state: ConversationState) -> str | None:
        target = state.entities.get("pending_followup_intent")
        if target in self.can_handover_to:
            state.entities.pop("pending_followup_intent", None)
            return target
        return None
