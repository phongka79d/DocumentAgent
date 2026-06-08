from collections.abc import Callable
import re
from typing import Protocol
from uuid import UUID

from app.core.config import get_settings
from app.schemas.retrieval import (
    HybridRetrievalCandidate,
    HybridSearchResponse,
    RetrievalResult,
    SearchResponse,
)
from app.services import graph_retrieval_service, retrieval_service
from app.services.graph_retrieval_service import GraphRetrievalCandidate
from app.utils.scoring import (
    clamp_score,
    final_score,
    keyword_overlap_score,
    metadata_match_score,
    recency_or_position_score,
)


MIN_TOP_K = 1
MAX_TOP_K = 50
_REASON_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


class HybridRetrievalValidationError(ValueError):
    """Raised when hybrid retrieval input is invalid."""


class SemanticSearchDependency(Protocol):
    def __call__(
        self,
        question: str,
        document_ids: list[UUID] | None = None,
        top_k: int | None = None,
    ) -> SearchResponse:
        """Return semantic retrieval candidates."""


class GraphRetrievalDependency(Protocol):
    def __call__(
        self,
        question: str,
        document_ids: list[UUID] | None = None,
        top_k: int | None = None,
    ) -> list[GraphRetrievalCandidate]:
        """Return graph retrieval candidates."""


def retrieve_hybrid(
    question: str,
    document_ids: list[UUID] | None = None,
    final_top_k: int | None = None,
    *,
    semantic_top_k: int | None = None,
    graph_top_k: int | None = None,
    semantic_search: SemanticSearchDependency | None = None,
    graph_retrieval: GraphRetrievalDependency | None = None,
) -> HybridSearchResponse:
    """Call semantic and graph retrieval paths and merge candidates by chunk ID.

    The response stays retrieval-only: reasons describe deterministic matching
    and scoring signals, not answers to the question.
    """

    trimmed_question = question.strip()
    if not trimmed_question:
        raise HybridRetrievalValidationError("Question must be non-empty.")

    settings = get_settings()
    resolved_semantic_top_k = _resolve_top_k(
        semantic_top_k,
        settings.retrieval_semantic_top_k,
        "semantic_top_k",
    )
    resolved_graph_top_k = _resolve_top_k(
        graph_top_k,
        settings.retrieval_graph_top_k,
        "graph_top_k",
    )
    resolved_final_top_k = _resolve_top_k(
        final_top_k,
        settings.retrieval_final_top_k,
        "final_top_k",
    )

    semantic_dependency = semantic_search or retrieval_service.semantic_search
    graph_dependency = graph_retrieval or graph_retrieval_service.find_graph_candidates

    semantic_response = semantic_dependency(
        trimmed_question,
        document_ids=document_ids,
        top_k=resolved_semantic_top_k,
    )
    graph_candidates = graph_dependency(
        trimmed_question,
        document_ids=document_ids,
        top_k=resolved_graph_top_k,
    )

    scored_candidates = _score_candidates(
        _merge_candidates_by_chunk_id(
            semantic_response.results,
            graph_candidates,
        ),
        question=trimmed_question,
        document_ids=document_ids,
    )

    return HybridSearchResponse(
        question=trimmed_question,
        candidates=_rank_and_limit_candidates(scored_candidates, resolved_final_top_k),
    )


def _resolve_top_k(value: int | None, default: int, field_name: str) -> int:
    resolved_top_k = default if value is None else value
    if resolved_top_k < MIN_TOP_K or resolved_top_k > MAX_TOP_K:
        raise HybridRetrievalValidationError(f"{field_name} must be between 1 and 50.")

    return resolved_top_k


def _merge_candidates_by_chunk_id(
    semantic_candidates: list[RetrievalResult],
    graph_candidates: list[GraphRetrievalCandidate],
) -> list[HybridRetrievalCandidate]:
    merged: dict[UUID, HybridRetrievalCandidate] = {}
    order: list[UUID] = []

    for semantic_candidate in semantic_candidates:
        chunk_id = semantic_candidate.chunk_id
        if chunk_id in merged:
            continue

        merged[chunk_id] = _candidate_from_semantic(semantic_candidate)
        order.append(chunk_id)

    for graph_candidate in graph_candidates:
        chunk_id = graph_candidate.chunk_id
        if chunk_id not in merged:
            merged[chunk_id] = _candidate_from_graph(graph_candidate)
            order.append(chunk_id)
            continue

        merged[chunk_id] = _merge_duplicate_candidate(
            merged[chunk_id],
            graph_candidate,
        )

    return [merged[chunk_id] for chunk_id in order]


def _score_candidates(
    candidates: list[HybridRetrievalCandidate],
    *,
    question: str,
    document_ids: list[UUID] | None,
) -> list[HybridRetrievalCandidate]:
    return [
        _score_candidate(candidate, question=question, document_ids=document_ids)
        for candidate in candidates
    ]


def _rank_and_limit_candidates(
    candidates: list[HybridRetrievalCandidate],
    final_top_k: int,
) -> list[HybridRetrievalCandidate]:
    return sorted(
        candidates,
        key=lambda candidate: candidate.final_score,
        reverse=True,
    )[:final_top_k]


def _score_candidate(
    candidate: HybridRetrievalCandidate,
    *,
    question: str,
    document_ids: list[UUID] | None,
) -> HybridRetrievalCandidate:
    semantic_similarity = clamp_score(candidate.semantic_similarity)
    graph_relevance = clamp_score(candidate.graph_relevance)
    keyword_overlap = keyword_overlap_score(
        question,
        candidate.content or candidate.content_preview,
    )
    metadata_match = metadata_match_score(question, candidate, document_ids)
    position = recency_or_position_score(candidate)
    calculated_final_score = final_score(
        {
            "semantic_similarity": semantic_similarity,
            "graph_relevance": graph_relevance,
            "keyword_overlap": keyword_overlap,
            "metadata_match": metadata_match,
            "recency_or_position_score": position,
        }
    )

    return candidate.model_copy(
        update={
            "semantic_similarity": semantic_similarity,
            "graph_relevance": graph_relevance,
            "keyword_overlap": keyword_overlap,
            "metadata_match": metadata_match,
            "recency_or_position_score": position,
            "final_score": calculated_final_score,
            "retrieval_reason": _build_retrieval_reason(
                candidate,
                question=question,
                semantic_similarity=semantic_similarity,
                graph_relevance=graph_relevance,
                keyword_overlap=keyword_overlap,
                metadata_match=metadata_match,
                position=position,
            ),
        }
    )


def _candidate_from_semantic(candidate: RetrievalResult) -> HybridRetrievalCandidate:
    return HybridRetrievalCandidate(
        chunk_id=candidate.chunk_id,
        document_id=candidate.document_id,
        file_name=candidate.file_name,
        file_type=candidate.file_type,
        content=candidate.content,
        content_preview=candidate.content_preview,
        page_number=candidate.page_number,
        section_title=candidate.section_title,
        chunk_index=candidate.chunk_index,
        semantic_similarity=clamp_score(candidate.semantic_similarity),
        metadata=None,
        graph_relevance=0.0,
        keyword_overlap=0.0,
        metadata_match=0.0,
        recency_or_position_score=0.0,
        final_score=0.0,
        retrieval_reason=None,
    )


def _candidate_from_graph(candidate: GraphRetrievalCandidate) -> HybridRetrievalCandidate:
    return HybridRetrievalCandidate(
        chunk_id=candidate.chunk_id,
        document_id=candidate.document_id,
        file_name=candidate.file_name,
        file_type=candidate.file_type,
        content=candidate.content,
        content_preview=None,
        page_number=candidate.page_number,
        section_title=candidate.section_title,
        chunk_index=candidate.chunk_index,
        semantic_similarity=0.0,
        metadata=dict(candidate.metadata) if candidate.metadata else None,
        graph_relevance=clamp_score(candidate.graph_relevance),
        keyword_overlap=0.0,
        metadata_match=0.0,
        recency_or_position_score=0.0,
        final_score=0.0,
        retrieval_reason=candidate.retrieval_reason,
    )


def _merge_duplicate_candidate(
    semantic_candidate: HybridRetrievalCandidate,
    graph_candidate: GraphRetrievalCandidate,
) -> HybridRetrievalCandidate:
    metadata = _merge_metadata(semantic_candidate.metadata, graph_candidate.metadata)
    return semantic_candidate.model_copy(
        update={
            "document_id": semantic_candidate.document_id or graph_candidate.document_id,
            "file_name": _richest_string(
                semantic_candidate.file_name,
                graph_candidate.file_name,
            ),
            "file_type": _first_present(
                semantic_candidate.file_type,
                graph_candidate.file_type,
            ),
            "content": _richest_string(
                semantic_candidate.content,
                graph_candidate.content,
            ),
            "content_preview": semantic_candidate.content_preview
            or _content_preview(graph_candidate.content),
            "page_number": _first_present(
                semantic_candidate.page_number,
                graph_candidate.page_number,
            ),
            "section_title": _richest_string(
                semantic_candidate.section_title,
                graph_candidate.section_title,
            ),
            "chunk_index": _first_present(
                semantic_candidate.chunk_index,
                graph_candidate.chunk_index,
            ),
            "graph_relevance": clamp_score(graph_candidate.graph_relevance),
            "metadata": metadata,
            "retrieval_reason": graph_candidate.retrieval_reason
            or semantic_candidate.retrieval_reason,
        }
    )


def _merge_metadata(
    existing_metadata: dict[str, object] | None,
    incoming_metadata: dict[str, object] | None,
) -> dict[str, object] | None:
    if not existing_metadata and not incoming_metadata:
        return None

    merged = dict(incoming_metadata or {})
    merged.update(existing_metadata or {})
    return merged


def _first_present[T](first: T | None, second: T | None) -> T | None:
    return first if first is not None else second


def _richest_string(first: str | None, second: str | None) -> str | None:
    if not first:
        return second
    if not second:
        return first

    return first if len(first.strip()) >= len(second.strip()) else second


def _content_preview(content: str | None) -> str | None:
    if not content:
        return None

    return content[:240]


def _build_retrieval_reason(
    candidate: HybridRetrievalCandidate,
    *,
    question: str,
    semantic_similarity: float,
    graph_relevance: float,
    keyword_overlap: float,
    metadata_match: float,
    position: float,
) -> str | None:
    reason_parts: list[str] = []

    has_graph_reason = bool(candidate.retrieval_reason)
    if candidate.retrieval_reason:
        reason_parts.append(f"Graph match: {candidate.retrieval_reason}")
    elif graph_relevance > 0.0:
        reason_parts.append(f"Graph match score: {graph_relevance:.2f}")

    if semantic_similarity > 0.0:
        reason_parts.append(f"Semantic match score: {semantic_similarity:.2f}")

    overlap_terms = _keyword_overlap_terms(
        question,
        candidate.content or candidate.content_preview,
    )
    if keyword_overlap > 0.0 and overlap_terms:
        reason_parts.append(f"keyword overlap: {', '.join(overlap_terms)}")

    if metadata_match > 0.0:
        reason_parts.append(f"metadata match score: {metadata_match:.2f}")

    if position > 0.0:
        reason_parts.append(f"position signal score: {position:.2f}")

    if not reason_parts:
        return None

    max_parts = 3 if has_graph_reason else 4
    return "; ".join(reason_parts[:max_parts])


def _keyword_overlap_terms(
    question: str | None,
    content: str | None,
    *,
    limit: int = 3,
) -> list[str]:
    content_tokens = set(_reason_tokens(content))
    if not content_tokens:
        return []

    overlap_terms: list[str] = []
    seen: set[str] = set()
    for token in _reason_tokens(question):
        if token in content_tokens and token not in seen:
            overlap_terms.append(token)
            seen.add(token)
        if len(overlap_terms) >= limit:
            break

    return overlap_terms


def _reason_tokens(value: str | None) -> list[str]:
    if not value:
        return []

    return _REASON_TOKEN_PATTERN.findall(value.lower())


__all__ = [
    "GraphRetrievalDependency",
    "HybridRetrievalValidationError",
    "SemanticSearchDependency",
    "retrieve_hybrid",
]
