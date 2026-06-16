import logging
from collections.abc import Mapping
from typing import Any
from uuid import UUID

from app.core.config import get_settings
from app.schemas.retrieval import RetrievalResult, SearchResponse
from app.services.qdrant_service import search_vectors
from app.services.shopaikey_service import ShopAIKeyServiceError, create_embedding
from app.services.supabase_service import get_chunk_content_by_ids


MIN_TOP_K = 1
MAX_TOP_K = 50

logger = logging.getLogger(__name__)


class RetrievalValidationError(ValueError):
    """Raised when semantic retrieval input is invalid."""


class RetrievalDependencyError(RuntimeError):
    """Raised when semantic retrieval cannot safely complete because of a dependency."""

    def __init__(self, public_message: str) -> None:
        self.public_message = public_message
        super().__init__(public_message)


def semantic_search(
    question: str,
    document_ids: list[UUID] | None = None,
    top_k: int | None = None,
) -> SearchResponse:
    trimmed_question = question.strip()
    if not trimmed_question:
        raise RetrievalValidationError("Question must be non-empty.")

    resolved_top_k = _resolve_top_k(top_k)
    query_vector = _create_query_embedding(trimmed_question)
    qdrant_results = search_vectors(
        query_vector=query_vector,
        top_k=resolved_top_k,
        document_ids=document_ids,
    )

    return SearchResponse(
        question=trimmed_question,
        results=_enrich_missing_content_from_supabase(
            _retrieval_results_from_qdrant(qdrant_results)
        ),
    )


def _resolve_top_k(top_k: int | None) -> int:
    resolved_top_k = (
        get_settings().retrieval_semantic_top_k if top_k is None else top_k
    )
    if resolved_top_k < MIN_TOP_K or resolved_top_k > MAX_TOP_K:
        raise RetrievalValidationError("top_k must be between 1 and 50.")

    return resolved_top_k


def _create_query_embedding(question: str) -> list[float]:
    try:
        return create_embedding(question)
    except ShopAIKeyServiceError as exc:
        logger.error(
            "ShopAIKey embedding failed during semantic retrieval. "
            "exception_type=%s; provider details were suppressed for safety.",
            exc.__class__.__name__,
        )
        raise RetrievalDependencyError(
            "Semantic retrieval is temporarily unavailable."
        ) from exc


def _retrieval_results_from_qdrant(results: list[Any]) -> list[RetrievalResult]:
    mapped_results: list[RetrievalResult] = []
    for result in results:
        mapped_result = _retrieval_result_from_qdrant(result)
        if mapped_result is not None:
            mapped_results.append(mapped_result)

    return mapped_results


def _enrich_missing_content_from_supabase(
    results: list[RetrievalResult],
) -> list[RetrievalResult]:
    missing_content_chunk_ids = [
        str(result.chunk_id)
        for result in results
        if result.content is None
    ]
    if not missing_content_chunk_ids:
        return results

    content_by_chunk_id = get_chunk_content_by_ids(missing_content_chunk_ids)
    enriched_results: list[RetrievalResult] = []
    for result in results:
        if result.content is not None:
            enriched_results.append(result)
            continue

        chunk_id = str(result.chunk_id)
        if chunk_id not in content_by_chunk_id or content_by_chunk_id[chunk_id] is None:
            logger.warning(
                "Skipping retrieval result because Supabase chunk content was not found. "
                "chunk_id=%s",
                chunk_id,
            )
            continue

        enriched_results.append(
            result.model_copy(update={"content": content_by_chunk_id[chunk_id]})
        )

    return enriched_results


def _retrieval_result_from_qdrant(result: Any) -> RetrievalResult | None:
    payload = _payload_from_qdrant_result(result)
    if payload is None:
        _log_malformed_point("payload is missing or not an object", result)
        return None

    chunk_id = _required_uuid(payload.get("chunk_id"), "chunk_id", result)
    document_id = _required_uuid(payload.get("document_id"), "document_id", result)
    semantic_similarity = _semantic_similarity(result)
    if chunk_id is None or document_id is None or semantic_similarity is None:
        return None

    return RetrievalResult(
        chunk_id=chunk_id,
        document_id=document_id,
        file_name=_optional_string(payload, "file_name"),
        file_type=_optional_string(payload, "file_type"),
        content=_optional_string(payload, "content"),
        content_preview=_optional_string(payload, "content_preview"),
        page_number=_optional_int(payload, "page_number"),
        section_title=_optional_string(payload, "section_title"),
        chunk_index=_optional_int(payload, "chunk_index"),
        semantic_similarity=semantic_similarity,
    )


def _payload_from_qdrant_result(result: Any) -> dict[str, Any] | None:
    payload = getattr(result, "payload", None)
    if payload is None:
        return None

    if isinstance(payload, dict):
        return payload

    if isinstance(payload, Mapping):
        return dict(payload)

    return None


def _required_uuid(value: Any, field_name: str, result: Any) -> UUID | None:
    if value is None:
        _log_malformed_point(f"required payload field '{field_name}' is missing", result)
        return None

    try:
        return UUID(str(value))
    except (AttributeError, TypeError, ValueError):
        _log_malformed_point(f"required payload field '{field_name}' is invalid", result)
        return None


def _optional_string(payload: dict[str, Any], field_name: str) -> str | None:
    value = payload.get(field_name)
    if value is None:
        return None

    if isinstance(value, str):
        return value

    _log_malformed_optional_field(field_name)
    return None


def _optional_int(payload: dict[str, Any], field_name: str) -> int | None:
    value = payload.get(field_name)
    if value is None:
        return None

    if isinstance(value, bool):
        _log_malformed_optional_field(field_name)
        return None

    if isinstance(value, int):
        return value

    _log_malformed_optional_field(field_name)
    return None


def _semantic_similarity(result: Any) -> float | None:
    value = getattr(result, "semantic_similarity", None)
    if value is None:
        _log_malformed_point("semantic_similarity is missing", result)
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        _log_malformed_point("semantic_similarity is invalid", result)
        return None


def _log_malformed_point(reason: str, result: Any) -> None:
    logger.warning(
        "Skipping malformed Qdrant point during retrieval mapping: %s. point_id=%s",
        reason,
        _point_identifier(result),
    )


def _log_malformed_optional_field(field_name: str) -> None:
    logger.warning(
        "Malformed optional Qdrant payload field '%s' during retrieval mapping; using null.",
        field_name,
    )


def _point_identifier(result: Any) -> Any:
    return (
        getattr(result, "point_id", None)
        or getattr(result, "id", None)
        or getattr(result, "id_", None)
    )
