from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class Message(BaseModel):
    role: str
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class HandoverContext(BaseModel):
    source_agent: str
    target_agent: str
    reason: str
    summary: str
    entities: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ConversationState(BaseModel):
    trace_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    current_agent: str = "triage"
    history: list[Message] = Field(default_factory=list)
    entities: dict[str, Any] = Field(default_factory=dict)
    handover_context: HandoverContext | None = None
    handover_count: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class AgentResponse(BaseModel):
    agent: str
    content: str
    routing_target: str | None = None
    sources: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class HandoverRequest(BaseModel):
    source_agent: str
    target_agent: str
    reason: str
    trace_id: str


class StartConversationRequest(BaseModel):
    customer_id: str | None = None
    initial_message: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class StartConversationResponse(BaseModel):
    conversation_id: str
    trace_id: str
    message: str | None = None


class SendMessageRequest(BaseModel):
    message: str


class AgentMessage(BaseModel):
    agent: str
    response: str
    sources: list[str] = Field(default_factory=list)
    routing_target: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SendMessageResponse(BaseModel):
    conversation_id: str
    trace_id: str
    agent: str
    response: str
    messages: list[AgentMessage] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    routing_target: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ConversationHistoryResponse(BaseModel):
    conversation_id: str
    trace_id: str
    current_agent: str
    entities: dict[str, Any]
    history: list[Message]
    handover_count: int
