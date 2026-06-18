from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


DocumentStatus = Literal["uploaded", "processing", "ready", "failed"]


class APIModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        from_attributes=True,
        str_strip_whitespace=True,
    )


class DocumentResponse(APIModel):
    id: UUID
    title: str | None = None
    file_name: str = Field(min_length=1)
    mime_type: str | None = None
    file_size: int | None = None
    file_hash: str | None = None
    storage_path: str = Field(min_length=1)
    status: DocumentStatus
    total_pages: int | None = None
    total_chunks: int = 0
    parser_name: str | None = None
    parser_version: str | None = None
    chunking_strategy: str | None = None
    chunking_version: str | None = None
    embedding_model: str | None = None
    embedding_dimension: int | None = None
    qdrant_collection: str | None = None
    indexed_at: datetime | None = None
    error_message: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class DocumentListResponse(APIModel):
    documents: list[DocumentResponse] = Field(default_factory=list)


class UploadDocumentResponse(APIModel):
    document_id: UUID
    status: DocumentStatus
    duplicate: bool


class SourceCitation(APIModel):
    document_id: UUID
    chunk_id: UUID
    file_name: str = Field(min_length=1)
    chunk_index: int
    page_start: int | None = None
    page_end: int | None = None
    heading: str | None = None
    qdrant_score: float | None = None
    rerank_score: float | None = None


class ChatRequest(APIModel):
    question: str = Field(min_length=1)
    document_ids: list[UUID] = Field(default_factory=list)
    save_message: bool = False


class ChatResponse(APIModel):
    answer: str = Field(min_length=1)
    sources: list[SourceCitation] = Field(default_factory=list)

