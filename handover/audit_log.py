from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)
_LOG_DIR = Path("logs")


def _ensure_log_dir() -> None:
    _LOG_DIR.mkdir(exist_ok=True)


def _default(obj: Any) -> str:
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Not serializable: {type(obj)}")


def _write(record: dict[str, Any]) -> None:
    _ensure_log_dir()
    log_file = _LOG_DIR / "audit.jsonl"
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, default=_default) + "\n")
    log.info("audit event=%s trace_id=%s", record.get("event"), record.get("trace_id"))


class AuditLogger:
    def log_handover(
        self,
        trace_id: str,
        source_agent: str,
        target_agent: str,
        reason: str,
        snapshot: dict[str, Any],
    ) -> None:
        _write({
            "event": "handover",
            "timestamp": datetime.utcnow().isoformat(),
            "trace_id": trace_id,
            "source_agent": source_agent,
            "target_agent": target_agent,
            "reason": reason,
            "context_snapshot": snapshot,
        })

    def log_escalation(
        self,
        trace_id: str,
        urgency: str,
        plan: str,
        summary: str,
        entities: dict[str, Any],
    ) -> None:
        _write({
            "event": "escalation",
            "timestamp": datetime.utcnow().isoformat(),
            "trace_id": trace_id,
            "urgency": urgency,
            "customer_plan": plan,
            "entities": entities,
            "summary": summary,
        })

    def log_agent_invocation(
        self,
        trace_id: str,
        agent: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        latency_ms: float = 0.0,
    ) -> None:
        _write({
            "event": "agent_invocation",
            "timestamp": datetime.utcnow().isoformat(),
            "trace_id": trace_id,
            "agent": agent,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "latency_ms": latency_ms,
        })
