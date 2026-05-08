from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

from openai import OpenAI

from api.models import AgentResponse, ConversationState, HandoverRequest

log = logging.getLogger(__name__)


class BaseAgent(ABC):
    def __init__(self, config: dict[str, Any], openai_client: OpenAI) -> None:
        self.config = config
        self.client = openai_client
        self.name: str = config["name"]
        self.model: str = config.get("model", "gpt-4o")
        self.temperature: float = config.get("temperature", 0.2)
        self.system_prompt: str = config["system_prompt"]

    @abstractmethod
    def process(self, state: ConversationState) -> AgentResponse:
        """Handle the current conversation state and return a response."""

    def _chat(self, messages: list[dict]) -> str:
        full_messages = [{"role": "system", "content": self.system_prompt}] + messages
        response = self.client.chat.completions.create(
            model=self.model,
            temperature=self.temperature,
            messages=full_messages,
        )
        return response.choices[0].message.content

    def _build_messages(self, state: ConversationState) -> list[dict]:
        messages = []
        if state.handover_context:
            messages.append({
                "role": "system",
                "content": (
                    f"[HANDOVER FROM {state.handover_context.source_agent.upper()}] "
                    f"Reason: {state.handover_context.reason}\n"
                    f"Extracted entities: {state.handover_context.entities}\n"
                    f"Prior summary: {state.handover_context.summary}"
                ),
            })
        for msg in state.history:
            messages.append({"role": msg.role, "content": msg.content})
        return messages

    def request_handover(self, target: str, reason: str, state: ConversationState) -> HandoverRequest:
        log.info(
            "agent=%s trace_id=%s handover_to=%s reason=%s",
            self.name, state.trace_id, target, reason,
        )
        return HandoverRequest(
            source_agent=self.name,
            target_agent=target,
            reason=reason,
            trace_id=state.trace_id,
        )
