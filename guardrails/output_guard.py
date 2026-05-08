from __future__ import annotations

import logging
import re
from pathlib import Path

import yaml

from api.models import AgentResponse

log = logging.getLogger(__name__)

_CONFIG_PATH = Path(__file__).parent.parent / "config" / "guardrails.yaml"

# Only apply grounding check to agents that are expected to cite KB sources
_RAG_AGENTS = {"technical support agent", "billing agent"}


class OutputGuard:
    def __init__(self) -> None:
        with open(_CONFIG_PATH) as f:
            cfg = yaml.safe_load(f)["output_guard"]
        self._pii_patterns = [
            (re.compile(p["regex"]), p["replacement"])
            for p in cfg["pii_redaction"]["patterns"]
        ]
        self._disclaimer: str = cfg["grounding_check"]["disclaimer"]
        self._deny_patterns: list[str] = cfg["fabrication_guard"]["deny_patterns"]

    def process(self, response: AgentResponse) -> AgentResponse:
        content = response.content

        content = self._redact_pii(content)
        content = self._strip_fabrications(content)

        is_rag_agent = response.agent.lower() in _RAG_AGENTS
        already_handled = response.metadata.get("kb_miss") or response.metadata.get("escalated")

        if is_rag_agent and not response.sources and not already_handled:
            log.info("output_guard grounding_disclaimer added agent=%s", response.agent)
            content += f"\n\n{self._disclaimer}"

        response.content = content
        return response

    def _redact_pii(self, text: str) -> str:
        for pattern, replacement in self._pii_patterns:
            text = pattern.sub(replacement, text)
        return text

    def _strip_fabrications(self, text: str) -> str:
        for phrase in self._deny_patterns:
            if phrase.lower() in text.lower():
                log.warning("output_guard fabrication_phrase_detected phrase=%r", phrase)
                text = re.sub(re.escape(phrase), "[claim removed]", text, flags=re.IGNORECASE)
        return text
