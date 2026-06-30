"""Agent-related Pydantic v2 models."""
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field


class AgentStatus(StrEnum):
    IDLE = "idle"
    RUNNING = "running"
    WAITING = "waiting"
    COMPLETED = "completed"
    FAILED = "failed"


class AgentRunCreate(BaseModel):
    campaign_id: UUID
    instructions: str = Field(default="", max_length=4000)
    model: str = Field(default="gpt-4o")
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)


class AgentRunRead(BaseModel):
    id: UUID
    campaign_id: UUID
    status: AgentStatus
    thread_id: str
    model: str
    created_at: datetime
    completed_at: datetime | None = None
    error: str | None = None

    model_config = {"from_attributes": True}


class AgentEventRead(BaseModel):
    id: UUID
    run_id: UUID
    event_type: str
    payload: dict
    created_at: datetime

    model_config = {"from_attributes": True}
