from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, model_validator


NonNegativeInt = Annotated[StrictInt, Field(ge=0)]
DeletionLogStatus = Literal["success", "failed"]
DeletionFailureStage = Literal["qdrant", "storage", "database"]
SAFE_DELETION_ERROR_MESSAGE = "Document deletion failed. Please try again."


class DeletionLogResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    document_id: UUID
    file_name: str | None
    status: DeletionLogStatus
    failure_stage: DeletionFailureStage | None
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

    @model_validator(mode="after")
    def normalize_failure_details(self) -> "DeletionLogResponse":
        if self.status == "success":
            if self.failure_stage is not None or self.error_message is not None:
                raise ValueError("Successful deletion logs cannot contain failure details.")
            return self

        if self.failure_stage is None:
            raise ValueError("Failed deletion logs require a failure stage.")

        self.error_message = SAFE_DELETION_ERROR_MESSAGE
        return self


class DeletionLogListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    logs: list[DeletionLogResponse]
    limit: int = Field(ge=1, le=100)
    offset: int = Field(ge=0)
    has_more: StrictBool


__all__ = [
    "DeletionLogListResponse",
    "DeletionLogResponse",
    "DeletionFailureStage",
    "DeletionLogStatus",
    "SAFE_DELETION_ERROR_MESSAGE",
]
