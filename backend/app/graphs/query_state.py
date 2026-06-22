from __future__ import annotations

from typing import Any, TypedDict

from app.core.contracts import RetrievalStrategy
from app.models.schemas import (
    CitationValidationResult,
    GroundingResult,
    QueryPlan,
    QuerySubquery,
    RetrievalCandidate,
    RetrievalFilters,
)


class QueryState(TypedDict, total=False):
    question: str
    document_ids: list[str]
    save_message: bool
    filters: RetrievalFilters

    prepared_query: str
    query_embedding: list[float]
    retrieval_hints: dict[str, list[str]]
    query_plan: QueryPlan
    subqueries: list[QuerySubquery]
    route: RetrievalStrategy
    relation_document_ids: list[str]
    path_candidates: dict[str, list[RetrievalCandidate]]
    fused_candidates: list[RetrievalCandidate]

    retrieved_chunks: list[dict[str, Any]]
    reranked_chunks: list[dict[str, Any]]
    context_chunks: list[dict[str, Any]]

    answer: str
    sources: list[dict[str, Any]]
    citation_validation_result: CitationValidationResult
    grounding_result: GroundingResult
    verification_attempt_count: int
    answer_verified: bool
    grounding_provider_failed: bool
    trace_id: str
    workflow_trace: list[dict[str, Any]]
    retrieval_metrics: dict[str, int | float | str | None]

    error_message: str | None
