from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from agents.orchestrator import Orchestrator
from api.models import (
    AgentMessage,
    ConversationHistoryResponse,
    ConversationState,
    SendMessageRequest,
    SendMessageResponse,
    StartConversationRequest,
    StartConversationResponse,
)
from guardrails.input_guard import InputGuard
from guardrails.output_guard import OutputGuard

log = logging.getLogger(__name__)

router = APIRouter()
_orchestrator = Orchestrator()
_input_guard = InputGuard()
_output_guard = OutputGuard()

_sessions: dict[str, ConversationState] = {}


@router.post("/conversation", response_model=StartConversationResponse, status_code=201)
def start_conversation(body: StartConversationRequest) -> StartConversationResponse:
    state = ConversationState()
    if body.customer_id:
        state.entities["customer_id"] = body.customer_id
    state.entities.update(body.metadata)
    _sessions[state.trace_id] = state

    log.info("conversation_start trace_id=%s customer_id=%s", state.trace_id, body.customer_id)

    if body.initial_message:
        guard_result = _input_guard.check(body.initial_message)
        if not guard_result.allowed:
            return StartConversationResponse(
                conversation_id=state.trace_id,
                trace_id=state.trace_id,
                message=guard_result.message,
            )
        state, responses = _orchestrator.handle_message_multi(state, body.initial_message)
        response = responses[-1]
        _sessions[state.trace_id] = state
        return StartConversationResponse(
            conversation_id=state.trace_id,
            trace_id=state.trace_id,
            message=response.content,
        )

    return StartConversationResponse(
        conversation_id=state.trace_id,
        trace_id=state.trace_id,
        message="Hello! Welcome to CloudDash support. How can I help you today?",
    )


@router.post("/conversation/{conversation_id}/message", response_model=SendMessageResponse)
def send_message(conversation_id: str, body: SendMessageRequest) -> SendMessageResponse:
    state = _sessions.get(conversation_id)
    if not state:
        raise HTTPException(status_code=404, detail="Conversation not found")

    guard_result = _input_guard.check(body.message)
    if not guard_result.allowed:
        log.info("input_blocked trace_id=%s reason=%s", conversation_id, guard_result.reason)
        return SendMessageResponse(
            conversation_id=conversation_id,
            trace_id=state.trace_id,
            agent="guardrail",
            response=guard_result.message or "Message blocked.",
        )

    state, responses = _orchestrator.handle_message_multi(state, body.message)
    responses = [_output_guard.process(r) for r in responses]
    response = responses[-1]
    _sessions[conversation_id] = state

    return SendMessageResponse(
        conversation_id=conversation_id,
        trace_id=state.trace_id,
        agent=response.agent,
        response=response.content,
        messages=[
            AgentMessage(
                agent=r.agent,
                response=r.content,
                sources=r.sources,
                routing_target=r.routing_target,
                metadata=r.metadata,
            )
            for r in responses
        ],
        sources=response.sources,
        routing_target=response.routing_target,
        metadata=response.metadata,
    )


@router.get("/conversation/{conversation_id}/history", response_model=ConversationHistoryResponse)
def get_history(conversation_id: str) -> ConversationHistoryResponse:
    state = _sessions.get(conversation_id)
    if not state:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return ConversationHistoryResponse(
        conversation_id=conversation_id,
        trace_id=state.trace_id,
        current_agent=state.current_agent,
        entities=state.entities,
        history=state.history,
        handover_count=state.handover_count,
    )
