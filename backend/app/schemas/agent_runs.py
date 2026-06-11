from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator

from app.agents.schemas import RejectedChunk, VerifiedChunk


class AgentRunEvidenceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    verified_chunks: list[VerifiedChunk]
    rejected_chunks: list[RejectedChunk]


class AgentRunLogStepResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent_name: str = Field(min_length=1)
    input: dict[str, JsonValue]
    output: dict[str, JsonValue]
    status: Literal["success", "failed"]
    created_at: datetime

    @field_validator("agent_name")
    @classmethod
    def normalize_agent_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("agent_name must not be empty")
        return normalized


class AgentRunLogsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent_run_id: UUID
    steps: list[AgentRunLogStepResponse]


__all__ = [
    "AgentRunEvidenceResponse",
    "AgentRunLogsResponse",
    "AgentRunLogStepResponse",
]
