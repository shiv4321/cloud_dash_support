from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from api.models import AgentResponse, ConversationState, Message
from handover.audit_log import AuditLogger
from handover.protocol import HandoverProtocol


@pytest.fixture
def state():
    s = ConversationState()
    s.history = [
        Message(role="user", content="My SSO stopped working after credential rotation"),
        Message(role="assistant", content="Let me help you troubleshoot the SSO issue."),
        Message(role="user", content="Also I want to upgrade to Enterprise"),
    ]
    s.entities = {"customer_plan": "Pro", "urgency": "medium"}
    s.current_agent = "technical"
    return s


@pytest.fixture
def protocol(tmp_path, monkeypatch):
    monkeypatch.setattr("handover.audit_log._LOG_DIR", tmp_path)
    audit = AuditLogger()
    return HandoverProtocol(audit), tmp_path


def test_handover_updates_state(state, protocol):
    hp, _ = protocol
    response = AgentResponse(agent="Technical Support Agent", content="SSO resolved.", sources=["KB-011"])

    updated = hp.execute(
        state=state,
        source_agent="technical",
        target_agent="billing",
        reason="Customer wants plan upgrade",
        response=response,
    )

    assert updated.current_agent == "billing"
    assert updated.handover_count == 1
    assert updated.handover_context is not None
    assert updated.handover_context.source_agent == "technical"
    assert updated.handover_context.target_agent == "billing"
    assert updated.handover_context.entities["customer_plan"] == "Pro"


def test_handover_preserves_entities(state, protocol):
    hp, _ = protocol
    state.entities["issue_type"] = "sso_failure"
    response = AgentResponse(agent="Technical Support Agent", content="Done.")

    updated = hp.execute(state, "technical", "billing", "upgrade request", response)

    assert updated.handover_context.entities.get("issue_type") == "sso_failure"


def test_handover_writes_audit_log(state, protocol):
    hp, tmp_path = protocol
    response = AgentResponse(agent="Technical Support Agent", content="Resolved.")

    hp.execute(state, "technical", "billing", "plan upgrade", response)

    log_file = tmp_path / "audit.jsonl"
    assert log_file.exists()
    records = [json.loads(line) for line in log_file.read_text().strip().splitlines()]
    assert len(records) == 1
    record = records[0]
    assert record["event"] == "handover"
    assert record["source_agent"] == "technical"
    assert record["target_agent"] == "billing"
    assert record["trace_id"] == state.trace_id


def test_handover_summary_includes_history(state, protocol):
    hp, _ = protocol
    response = AgentResponse(agent="Technical Support Agent", content="Done.")
    updated = hp.execute(state, "technical", "escalation", "unresolved issue", response)

    summary = updated.handover_context.summary
    assert "SSO stopped working" in summary or "entities" in summary.lower()


def test_escalation_audit_logged(tmp_path, monkeypatch):
    monkeypatch.setattr("handover.audit_log._LOG_DIR", tmp_path)
    audit = AuditLogger()
    audit.log_escalation(
        trace_id="test-trace",
        urgency="high",
        plan="Pro",
        summary="Customer charged twice, requesting refund",
        entities={"customer_plan": "Pro", "urgency": "high"},
    )

    log_file = tmp_path / "audit.jsonl"
    records = [json.loads(line) for line in log_file.read_text().strip().splitlines()]
    assert records[0]["event"] == "escalation"
    assert records[0]["urgency"] == "high"
