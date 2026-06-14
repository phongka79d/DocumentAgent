from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt


NonNegativeInt = Annotated[StrictInt, Field(ge=0)]


class DeletionLogItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    document_id: UUID
    file_name: str | None
    status: Literal["success", "failed"]
    failure_stage: str | None
    error_message: str | None
    deleted_storage_file: StrictBool
    deleted_qdrant_points: StrictBool
    deleted_chunks: NonNegativeInt
    deleted_entities: NonNegativeInt
    deleted_relationships: NonNegativeInt
    deleted_agent_runs: NonNegativeInt
    deleted_agent_steps: NonNegativeInt
    deleted_chat_messages: NonNegativeInt
    deleted_chat_sessions: NonNegativeInt
    created_at: datetime


class DeletionLogListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    logs: list[DeletionLogItem]
    limit: int = Field(ge=1, le=100)
    offset: int = Field(ge=0)
    has_more: StrictBool


__all__ = ["DeletionLogItem", "DeletionLogListResponse"]
