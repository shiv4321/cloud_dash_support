from __future__ import annotations

import logging
import re
from pathlib import Path

import yaml

log = logging.getLogger(__name__)

_CONFIG_PATH = Path(__file__).parent.parent / "config" / "guardrails.yaml"
_CLOUDDASH_KEYWORDS = {
    "cloud", "monitor", "alert", "dashboard", "billing", "subscription",
    "integration", "aws", "gcp", "azure", "api", "sso", "account", "team",
    "support", "technical", "metric", "webhook", "plan", "upgrade", "downgrade",
    "invoice", "payment", "credential", "clouddash", "login", "access", "refund",
    "error", "issue", "help", "problem", "setup", "configure", "install", "key",
    "not", "working", "broken", "fix", "how", "why", "what", "when", "does",
    "can", "my", "the", "still", "again", "more", "another",
}

# Short conversational replies that should always pass through
_ALWAYS_ALLOW = {
    "yes", "no", "ok", "okay", "sure", "thanks", "thank", "you",
    "great", "got", "it", "understood", "hello", "hi", "hey",
    "still", "not", "working", "more", "continue", "please", "again",
}


class InputGuardResult:
    def __init__(self, allowed: bool, message: str | None = None, reason: str | None = None):
        self.allowed = allowed
        self.message = message
        self.reason = reason


class InputGuard:
    def __init__(self) -> None:
        with open(_CONFIG_PATH) as f:
            cfg = yaml.safe_load(f)["input_guard"]
        self._injection_patterns: list[str] = cfg["prompt_injection"]["patterns"]
        self._injection_msg: str = cfg["prompt_injection"]["message"]
        self._off_topic_msg: str = cfg["off_topic"]["message"]
        self._max_len: int = cfg["max_input_length"]

    def check(self, text: str) -> InputGuardResult:
        if len(text) > self._max_len:
            return InputGuardResult(
                allowed=False,
                message="Your message is too long. Please keep it under 4000 characters.",
                reason="max_length_exceeded",
            )

        text_lower = text.lower()

        for pattern in self._injection_patterns:
            if pattern.lower() in text_lower:
                log.warning("input_guard blocked=prompt_injection pattern=%r", pattern)
                return InputGuardResult(
                    allowed=False,
                    message=self._injection_msg,
                    reason="prompt_injection",
                )

        tokens = set(re.findall(r"\b\w+\b", text_lower))

        # Always allow: short replies, pure conversational tokens, or any CloudDash keyword present
        if len(tokens) <= 6 or tokens & _ALWAYS_ALLOW or tokens & _CLOUDDASH_KEYWORDS:
            return InputGuardResult(allowed=True)

        log.info("input_guard flagged=off_topic tokens_sample=%s", list(tokens)[:5])
        return InputGuardResult(
            allowed=False,
            message=self._off_topic_msg,
            reason="off_topic",
        )
