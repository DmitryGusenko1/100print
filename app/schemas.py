import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class MessageCreate(BaseModel):
    project_id: uuid.UUID
    dialogue_key: str = Field(min_length=1, max_length=255)
    source: str = Field(min_length=1, max_length=32)
    external_id: str = Field(min_length=1, max_length=255)
    role: str = Field(pattern="^(user|assistant|system|tool)$")
    content: str = Field(min_length=1, max_length=20000)


class TaskCreate(BaseModel):
    project_id: uuid.UUID
    title: str = Field(min_length=1, max_length=500)
    source_message_id: uuid.UUID | None = None


class TaskUpdate(BaseModel):
    status: str = Field(pattern="^(open|doing|done|cancelled)$")


class DecisionCreate(BaseModel):
    project_id: uuid.UUID
    text: str = Field(min_length=1, max_length=10000)
    confirmed: bool = False
    source_message_id: uuid.UUID | None = None


class StateCreate(BaseModel):
    project_id: uuid.UUID
    summary: str = Field(min_length=1, max_length=30000)
    source_message_id: uuid.UUID | None = None


class ContextResponse(BaseModel):
    project_id: uuid.UUID
    state: str | None
    recent_messages: list[dict]
    relevant_messages: list[dict]
    tasks: list[dict]
    decisions: list[dict]
