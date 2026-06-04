from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class ParsedSection(BaseModel):
    text: str
    page_number: int | None = Field(default=None, ge=1)
    section_title: str | None = None
    file_name: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChunkDraft(BaseModel):
    content: str
    chunk_index: int = Field(ge=0)
    token_count: int = Field(ge=0)
    document_id: UUID | None = None
    user_id: str | None = None
    page_number: int | None = Field(default=None, ge=1)
    section_title: str | None = None
    file_name: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    qdrant_point_id: str | None = None
