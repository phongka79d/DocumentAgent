from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel


class SearchRequest(BaseModel):
    question: str
    document_ids: list[UUID] | None = None
    top_k: int | None = None
    mode: Literal["semantic", "hybrid"] = "semantic"


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


class HybridScoreComponents(BaseModel):
    semantic_similarity: float
    graph_relevance: float
    keyword_overlap: float
    metadata_match: float
    recency_or_position_score: float


class HybridRetrievalCandidate(RetrievalResult):
    metadata: dict[str, Any] | None = None
    graph_relevance: float
    keyword_overlap: float
    metadata_match: float
    recency_or_position_score: float
    final_score: float
    retrieval_reason: str | None = None


class HybridSearchResponse(BaseModel):
    question: str
    candidates: list[HybridRetrievalCandidate]
