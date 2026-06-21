from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Any
from uuid import UUID

from app.core.config import Settings, get_settings
from app.core.contracts import RetrievalPath
from app.models.schemas import RetrievalCandidate, RetrievalFilters
from app.services.supabase_client import create_supabase_client


KEYWORD_SEARCH_RPC = "search_document_chunks_keyword"


class KeywordSearchValidationError(ValueError):
    """Raised when a keyword retrieval request is invalid."""


class KeywordSearchError(RuntimeError):
    """Safe recoverable error raised when keyword retrieval cannot run."""

    def __init__(
        self,
        message: str = "keyword retrieval is unavailable",
        *,
        code: str = "keyword_rpc_unavailable",
        recoverable: bool = True,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.recoverable = recoverable


def _resolve_settings(settings: Settings | None = None) -> Settings:
    return settings if settings is not None else get_settings()


def _resolve_supabase_client(supabase_client: Any | None = None) -> Any:
    return supabase_client if supabase_client is not None else create_supabase_client()


def _normalize_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalize_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _normalize_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalize_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (str, bytes)):
        text = _normalize_text(value)
        return [text] if text is not None else []
    if isinstance(value, Iterable):
        normalized: list[str] = []
        seen: set[str] = set()
        for item in value:
            text = _normalize_text(item)
            if text is None or text in seen:
                continue
            normalized.append(text)
            seen.add(text)
        return normalized
    text = _normalize_text(value)
    return [text] if text is not None else []


def _normalize_document_ids(document_ids: Sequence[UUID | str] | None) -> list[str]:
    return _normalize_string_list(document_ids)


def _normalize_filters(filters: RetrievalFilters | Mapping[str, Any] | None) -> dict[str, Any]:
    if filters is None:
        return {}
    if isinstance(filters, RetrievalFilters):
        model = filters
    elif isinstance(filters, Mapping):
        model = RetrievalFilters.model_validate(dict(filters))
    else:
        model = RetrievalFilters.model_validate(filters)
    return model.model_dump(mode="json", exclude_none=True)


def _optional_list(values: list[str]) -> list[str] | None:
    return values or None


def _response_rows(response: Any) -> list[dict[str, Any]]:
    data = getattr(response, "data", response)
    if data is None:
        return []
    if isinstance(data, Mapping):
        return [dict(data)]
    if not isinstance(data, list):
        data = list(data) if isinstance(data, Iterable) and not isinstance(data, (str, bytes)) else [data]

    rows: list[dict[str, Any]] = []
    for item in data:
        if isinstance(item, Mapping):
            rows.append(dict(item))
        elif hasattr(item, "model_dump"):
            rows.append(dict(item.model_dump()))
        elif hasattr(item, "__dict__"):
            rows.append(
                {
                    key: value
                    for key, value in vars(item).items()
                    if not key.startswith("_")
                }
            )
    return rows


def _candidate_sort_key(candidate: Mapping[str, Any]) -> tuple[float, str, int]:
    score = _normalize_float(candidate.get("keyword_score"))
    document_id = _normalize_text(candidate.get("document_id")) or ""
    chunk_index = _normalize_int(candidate.get("chunk_index"))
    return (-(score if score is not None else float("-inf")), document_id, chunk_index or 0)


def _normalize_candidate(row: Mapping[str, Any], *, rank: int) -> dict[str, Any] | None:
    chunk_id = _normalize_text(row.get("chunk_id") or row.get("id"))
    document_id = _normalize_text(row.get("document_id"))
    file_name = _normalize_text(row.get("file_name"))
    chunk_index = _normalize_int(row.get("chunk_index"))
    content = _normalize_text(row.get("content")) or ""
    if chunk_id is None or document_id is None or file_name is None or chunk_index is None:
        return None

    candidate = RetrievalCandidate.model_validate(
        {
            "chunk_id": chunk_id,
            "document_id": document_id,
            "file_name": file_name,
            "chunk_index": chunk_index,
            "content": content,
            "heading": _normalize_text(row.get("heading")),
            "section_path": _normalize_string_list(row.get("section_path")),
            "page_start": _normalize_int(row.get("page_start")),
            "page_end": _normalize_int(row.get("page_end")),
            "chunk_type": _normalize_text(row.get("chunk_type")),
            "token_count": _normalize_int(row.get("token_count")),
            "qdrant_score": None,
            "rerank_score": None,
            "semantic_rank": None,
            "semantic_score": None,
            "keyword_rank": rank,
            "keyword_score": _normalize_float(row.get("keyword_score")),
            "fusion_score": None,
            "retrieval_paths": [RetrievalPath.KEYWORD],
            "subquery_ids": [],
        }
    )
    return candidate.model_dump(mode="json")


def search_keyword_chunks(
    query: str,
    *,
    document_ids: Sequence[UUID | str] | None = None,
    filters: RetrievalFilters | Mapping[str, Any] | None = None,
    settings: Settings | None = None,
    supabase_client: Any | None = None,
) -> list[dict[str, Any]]:
    """Search chunks with Postgres full-text search and normalize candidates."""

    resolved_settings = _resolve_settings(settings)
    normalized_query = _normalize_text(query)
    if normalized_query is None:
        raise KeywordSearchValidationError("query is required")

    normalized_filters = _normalize_filters(filters)
    params = {
        "query_text": normalized_query,
        "result_limit": resolved_settings.RETRIEVAL_KEYWORD_TOP_K,
        "document_ids": _optional_list(_normalize_document_ids(document_ids)),
        "mime_types": _optional_list(
            _normalize_string_list(normalized_filters.get("mime_types"))
        ),
        "filter_heading": _normalize_text(normalized_filters.get("heading")),
        "filter_section_path": _optional_list(
            _normalize_string_list(normalized_filters.get("section_path"))
        ),
        "filter_page_start": _normalize_int(normalized_filters.get("page_start")),
        "filter_page_end": _normalize_int(normalized_filters.get("page_end")),
    }

    client = _resolve_supabase_client(supabase_client)
    try:
        response = client.rpc(KEYWORD_SEARCH_RPC, params).execute()
    except Exception:
        raise KeywordSearchError() from None

    sorted_rows = sorted(_response_rows(response), key=_candidate_sort_key)[
        : resolved_settings.RETRIEVAL_KEYWORD_TOP_K
    ]
    candidates: list[dict[str, Any]] = []
    for rank, row in enumerate(sorted_rows, start=1):
        candidate = _normalize_candidate(row, rank=rank)
        if candidate is not None:
            candidates.append(candidate)
    return candidates
