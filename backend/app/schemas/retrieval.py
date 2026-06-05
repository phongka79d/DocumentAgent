from uuid import UUID

from pydantic import BaseModel


class SearchRequest(BaseModel):
    question: str
    document_ids: list[UUID] | None = None
    top_k: int | None = None


class RetrievalResult(BaseModel):
    chunk_id: UUID
    document_id: UUID
    file_name: str | None = None
    file_type: str | None = None
    content: str | None = None
    content_preview: str | None = None
    page_number: int | None = None
    section_title: str | None = None
    chunk_index: int | None = None
    semantic_similarity: float


class SearchResponse(BaseModel):
    question: str
    results: list[RetrievalResult]
