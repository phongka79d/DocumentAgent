from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, StrictBool, StrictInt


class DocumentUploadResponse(BaseModel):
    document_id: UUID
    file_name: str
    status: str


class DocumentListItem(BaseModel):
    id: UUID
    file_name: str
    file_type: str
    status: str
    chunk_count: int
    created_at: datetime
    error_message: str | None = None


class DocumentListResponse(BaseModel):
    documents: list[DocumentListItem]


class DocumentDetailResponse(BaseModel):
    id: UUID
    file_name: str
    file_type: str
    status: str
    chunk_count: int
    created_at: datetime
    updated_at: datetime
    error_message: str | None = None
    chunks: list[dict[str, Any]] = Field(default_factory=list)


class DocumentDeleteResponse(BaseModel):
    document_id: UUID
    deleted: bool
    deleted_agent_runs: int
    deleted_agent_steps: int
    deleted_chat_messages: int
    deleted_chat_sessions: int
    deleted_chunks: int
    deleted_entities: int
    deleted_relationships: int
    deleted_qdrant_points: bool
    deleted_storage_file: bool


class DocumentDeleteRpcSuccessRow(BaseModel):
    document_id: UUID
    file_name: str
    deleted: StrictBool
    deleted_agent_runs: StrictInt = Field(ge=0)
    deleted_agent_steps: StrictInt = Field(ge=0)
    deleted_chat_messages: StrictInt = Field(ge=0)
    deleted_chat_sessions: StrictInt = Field(ge=0)
    deleted_chunks: StrictInt = Field(ge=0)
    deleted_entities: StrictInt = Field(ge=0)
    deleted_relationships: StrictInt = Field(ge=0)
    deleted_qdrant_points: StrictBool
    deleted_storage_file: StrictBool


class DocumentDeleteAuditSuccessRow(BaseModel):
    document_id: UUID
    file_name: str
    status: Literal["success"]
    deleted_agent_runs: StrictInt = Field(ge=0)
    deleted_agent_steps: StrictInt = Field(ge=0)
    deleted_chat_messages: StrictInt = Field(ge=0)
    deleted_chat_sessions: StrictInt = Field(ge=0)
    deleted_chunks: StrictInt = Field(ge=0)
    deleted_entities: StrictInt = Field(ge=0)
    deleted_relationships: StrictInt = Field(ge=0)
    deleted_qdrant_points: StrictBool
    deleted_storage_file: StrictBool
