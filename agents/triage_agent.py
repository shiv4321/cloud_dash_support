from __future__ import annotations

import json
import logging
from typing import Any

from openai import OpenAI

from agents.base_agent import BaseAgent
from api.models import AgentResponse, ConversationState

log = logging.getLogger(__name__)


_CLASSIFY_TOOL = {
    "type": "function",
    "function": {
        "name": "classify_intent",
        "description": "Classify the customer's intent and extract entities.",
        "parameters": {
            "type": "object",
            "properties": {
                "intent": {
                    "type": "string",
                    "enum": ["technical", "billing", "account", "general", "unknown"],
                },
                "secondary_intent": {
                    "type": "string",
                    "enum": ["technical", "billing", "account", "general", "escalation", "none"],
                },
                "customer_plan": {
                    "type": "string",
                    "enum": ["Starter", "Pro", "Enterprise", "unknown"],
                },
                "urgency": {
                    "type": "string",
                    "enum": ["low", "medium", "high", "critical"],
                },
                "extracted_entities": {
                    "type": "object",
                    "description": "Key-value pairs of relevant entities (service, issue_type, etc.)",
                },
                "routing_target": {
                    "type": "string",
                    "enum": ["technical", "billing", "triage"],
                },
                "acknowledgement": {
                    "type": "string",
                    "description": "A brief, friendly response to show the customer they were understood.",
                },
            },
            "required": ["intent", "routing_target", "acknowledgement", "urgency"],
        },
    },
}


class TriageAgent(BaseAgent):
    def __init__(self, config: dict[str, Any], openai_client: OpenAI) -> None:
        super().__init__(config, openai_client)
        self.routing_rules: dict[str, str] = config.get("routing_rules", {})

    def process(self, state: ConversationState) -> AgentResponse:
        last_user_msg = next(
            (m.content for m in reversed(state.history) if m.role == "user"), ""
        ).strip()

        messages = self._build_messages(state)

        response = self.client.chat.completions.create(
            model=self.model,
            temperature=self.temperature,
            messages=[{"role": "system", "content": self.system_prompt}] + messages,
            tools=[_CLASSIFY_TOOL],
            tool_choice={"type": "function", "function": {"name": "classify_intent"}},
        )

        tool_call = response.choices[0].message.tool_calls[0]
        classification = json.loads(tool_call.function.arguments)

        log.info(
            "triage trace_id=%s intent=%s urgency=%s routing_to=%s entities=%s",
            state.trace_id,
            classification.get("intent"),
            classification.get("urgency"),
            classification.get("routing_target"),
            classification.get("extracted_entities", {}),
        )

        state.entities.update(classification.get("extracted_entities", {}))
        state.entities["customer_plan"] = classification.get("customer_plan", "unknown")
        state.entities["urgency"] = classification.get("urgency", "medium")
        state.entities["primary_intent"] = classification.get("intent")
        state.entities["secondary_intent"] = classification.get("secondary_intent", "none")

        routing_target = classification["routing_target"]
        acknowledgement = classification["acknowledgement"]
        primary_target = self._resolve_primary_target(classification.get("intent", "unknown"), routing_target)
        secondary_target = self._resolve_secondary_target(classification.get("secondary_intent", "none"))

        # If LLM still somehow returns escalation, convert to clarification
        if primary_target == "escalation":
            primary_target = "triage"

        # Deterministic sequencing for mixed intents:
        # if a technical track is present anywhere, always handle technical first.
        routing_target, secondary_target = self._enforce_technical_first(primary_target, secondary_target)

        # Persist a normalized follow-up target for specialist agents.
        # This enables deterministic cross-agent sequencing after primary resolution.
        if secondary_target and secondary_target != routing_target:
            state.entities["pending_followup_intent"] = secondary_target
        else:
            state.entities.pop("pending_followup_intent", None)

        return AgentResponse(
            agent=self.name,
            content=acknowledgement,
            routing_target=routing_target,
            metadata={
                "intent": classification.get("intent"),
                "secondary_intent": classification.get("secondary_intent", "none"),
                "pending_followup_intent": state.entities.get("pending_followup_intent"),
                "urgency": classification.get("urgency"),
                "entities": classification.get("extracted_entities", {}),
            },
        )

    def _resolve_secondary_target(self, secondary_intent: str) -> str | None:
        if not secondary_intent or secondary_intent == "none":
            return None
        normalized = self.routing_rules.get(secondary_intent, secondary_intent)
        if normalized in {"technical", "billing", "escalation"}:
            return normalized
        return None

    def _resolve_primary_target(self, intent: str, routing_target: str) -> str:
        if routing_target in {"technical", "billing", "triage", "escalation"}:
            return routing_target
        normalized = self.routing_rules.get(intent, "triage")
        if normalized in {"technical", "billing", "triage", "escalation"}:
            return normalized
        return "triage"

    def _enforce_technical_first(self, primary_target: str, secondary_target: str | None) -> tuple[str, str | None]:
        targets = {t for t in [primary_target, secondary_target] if t}
        if "technical" in targets and len(targets) > 1:
            followup = secondary_target if primary_target == "technical" else primary_target
            if followup in {"billing", "escalation"}:
                return "technical", followup
            return "technical", None
        return primary_target, secondary_target
