from __future__ import annotations

import importlib
import logging
import os
from pathlib import Path
from typing import Any

import yaml
from openai import OpenAI

from api.models import AgentResponse, ConversationState, HandoverContext, Message
from handover.audit_log import AuditLogger
from handover.protocol import HandoverProtocol
from retrieval.rag_chain import RAGChain

log = logging.getLogger(__name__)


def _make_langfuse():
    pub  = os.getenv("LANGFUSE_PUBLIC_KEY")
    sec  = os.getenv("LANGFUSE_SECRET_KEY")
    host = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
    if not (pub and sec):
        return None
    try:
        from langfuse import Langfuse
        lf = Langfuse(public_key=pub, secret_key=sec, host=host, debug=True)
        log.info("langfuse client host=%s", host)
        return lf
    except Exception as exc:
        log.warning("langfuse init failed: %s — tracing disabled", exc)
        return None


_CONFIG_PATH = Path(__file__).parent.parent / "config" / "agents.yaml"
_MAX_HANDOVERS = 5


def _load_config() -> dict[str, Any]:
    with open(_CONFIG_PATH) as f:
        return yaml.safe_load(f)["agents"]


def _instantiate_agent(key: str, cfg: dict, client: OpenAI, rag: RAGChain, audit: AuditLogger):
    module_path, class_name = cfg["class"].rsplit(".", 1)
    module = importlib.import_module(module_path)
    cls = getattr(module, class_name)

    init_kwargs: dict[str, Any] = {"config": cfg, "openai_client": client}
    if key == "escalation":
        init_kwargs["audit"] = audit
    elif key in ("technical", "billing"):
        init_kwargs["rag"] = rag

    return cls(**init_kwargs)


class Orchestrator:
    def __init__(self) -> None:
        self.client = OpenAI()
        self.audit = AuditLogger()
        self.rag = RAGChain()
        self._configs = _load_config()
        self._agents: dict[str, Any] = {
            key: _instantiate_agent(key, cfg, self.client, self.rag, self.audit)
            for key, cfg in self._configs.items()
        }
        self.handover = HandoverProtocol(self.audit)
        self._lf = _make_langfuse()
        log.info("orchestrator loaded agents=%s langfuse=%s", list(self._agents.keys()), self._lf is not None)

    def handle_message_multi(self, state: ConversationState, user_message: str) -> tuple[ConversationState, list[AgentResponse]]:
        state.history.append(Message(role="user", content=user_message))

        # Only triage on the very first message; subsequent messages go to current specialist
        is_first_message = len([m for m in state.history if m.role == "user"]) == 1
        if is_first_message or state.current_agent in (None, "triage"):
            state.current_agent = "triage"

        handover_count = 0
        responses: list[AgentResponse] = []

        while handover_count <= _MAX_HANDOVERS:
            agent_key = state.current_agent
            agent = self._agents.get(agent_key)

            if agent is None:
                log.error("orchestrator unknown_agent=%s falling_back=triage", agent_key)
                agent_key = "triage"
                agent = self._agents["triage"]

            log.info(
                "orchestrator trace_id=%s agent=%s handover_count=%d",
                state.trace_id, agent_key, handover_count,
            )

            try:
                response = agent.process(state)
            except Exception as exc:
                log.exception("orchestrator agent=%s error=%s", agent_key, exc)
                response = AgentResponse(
                    agent=agent.name,
                    content="I'm experiencing a technical difficulty. Let me escalate this for you.",
                    routing_target="escalation",
                )

            responses.append(response)
            state.history.append(Message(role="assistant", content=response.content))

            # No further routing needed
            if not response.routing_target or response.routing_target == agent_key:
                # Persist the specialist agent so next message skips triage
                if agent_key != "triage":
                    state.current_agent = agent_key
                break

            target = response.routing_target
            if target not in self._agents:
                log.warning("orchestrator unknown_target=%s falling_back=escalation", target)
                target = "escalation"

            try:
                state = self.handover.execute(
                    state=state,
                    source_agent=agent_key,
                    target_agent=target,
                    reason=f"Routed from {agent_key} to {target}",
                    response=response,
                )
            except Exception as exc:
                log.exception("orchestrator handover_failed error=%s", exc)
                state.current_agent = "escalation"
                state.handover_context = HandoverContext(
                    source_agent=agent_key,
                    target_agent="escalation",
                    reason=f"Handover failed: {exc}",
                    summary="",
                    entities=state.entities,
                )

            handover_count += 1

        if not responses:
            responses = [AgentResponse(
                agent="orchestrator",
                content="I'm unable to process your request at the moment. Please try again.",
            )]

        return state, responses

    def handle_message(self, state: ConversationState, user_message: str) -> tuple[ConversationState, AgentResponse]:
        state, responses = self.handle_message_multi(state, user_message)
        return state, responses[-1]
