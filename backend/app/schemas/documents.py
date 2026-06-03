from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


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
