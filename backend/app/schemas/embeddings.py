from uuid import UUID

from pydantic import BaseModel, Field


class EmbeddingInput(BaseModel):
    text: str = Field(min_length=1)


class EmbeddingResult(BaseModel):
    text: str = Field(min_length=1)
    vector: list[float] = Field(min_length=1)


class IndexedChunkPayload(BaseModel):
    user_id: str = Field(min_length=1)
    document_id: UUID
    chunk_id: UUID
    file_name: str = Field(min_length=1)
    file_type: str = Field(min_length=1)
    page_number: int | None = Field(default=None, ge=1)
    section_title: str | None = None
    chunk_index: int = Field(ge=0)
    content_preview: str = Field(max_length=500)


class ChunkIndexingError(BaseModel):
    chunk_id: UUID | None = None
    chunk_index: int | None = Field(default=None, ge=0)
    message: str = Field(min_length=1)


class DocumentIndexingResult(BaseModel):
    document_id: UUID
    indexed_count: int = Field(ge=0)
    failed_count: int = Field(ge=0)
    errors: list[ChunkIndexingError] = Field(default_factory=list)
