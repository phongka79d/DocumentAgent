from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any
from uuid import UUID

from app.core.config import Settings, get_settings
from app.core.contracts import ContextMode
from app.services import chunks as chunk_service
from app.services.retrieval_boundaries import resolve_boundary_chunks
from app.services.retrieval_hints import _normalize_retrieval_hints


class RetrievalContextError(RuntimeError):
    """Raised when retrieval context expansion cannot be completed."""


NEIGHBOR_CONTEXT_MODE = ContextMode.NEIGHBOR
SECTION_AWARE_CONTEXT_MODE = ContextMode.SECTION_AWARE


def _resolve_settings(settings: Settings | None = None) -> Settings:
    return settings if settings is not None else get_settings()


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


def _normalize_context_mode(value: Any) -> ContextMode:
    mode = _normalize_text(value)
    if mode is None:
        return SECTION_AWARE_CONTEXT_MODE
    try:
        return ContextMode(mode.lower())
    except ValueError as exc:
        raise RetrievalContextError(f"Unsupported retrieval context mode: {value}") from exc


def _normalize_section_path(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (str, bytes)):
        text = str(value).strip()
        return [text] if text else []
    if isinstance(value, Sequence):
        path: list[str] = []
        for item in value:
            text = _normalize_text(item)
            if text is not None:
                path.append(text)
        return path
    text = _normalize_text(value)
    return [text] if text is not None else []


def _normalize_document_ids(document_ids: Sequence[UUID | str] | None) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    if not document_ids:
        return normalized

    for value in document_ids:
        text = _normalize_text(value)
        if text is None or text in seen:
            continue
        normalized.append(text)
        seen.add(text)
    return normalized


def _normalize_context_chunk(
    chunk: Mapping[str, Any],
    *,
    file_name_override: str | None = None,
    is_neighbor_context: bool | None = None,
) -> dict[str, Any]:
    chunk_id = _normalize_text(chunk.get("chunk_id") or chunk.get("id"))
    if chunk_id is None:
        raise RetrievalContextError("Chunk id is required")

    document_id = _normalize_text(chunk.get("document_id"))
    if document_id is None:
        raise RetrievalContextError("Document id is required")

    content = _normalize_text(chunk.get("content") or chunk.get("text")) or ""
    file_name = _normalize_text(chunk.get("file_name") or file_name_override)

    normalized: dict[str, Any] = {
        "id": chunk_id,
        "chunk_id": chunk_id,
        "document_id": document_id,
        "file_name": file_name,
        "chunk_index": _normalize_int(chunk.get("chunk_index")),
        "content": content,
        "text": content,
        "heading": chunk.get("heading"),
        "section_path": _normalize_section_path(chunk.get("section_path")),
        "page_start": _normalize_int(chunk.get("page_start")),
        "page_end": _normalize_int(chunk.get("page_end")),
        "chunk_type": _normalize_text(chunk.get("chunk_type")),
        "token_count": _normalize_int(chunk.get("token_count")),
        "qdrant_score": _normalize_float(chunk.get("qdrant_score")),
        "rerank_score": _normalize_float(chunk.get("rerank_score")),
    }
    if is_neighbor_context is not None:
        normalized["is_neighbor_context"] = is_neighbor_context
    return normalized


def _neighbor_indexes(chunk_index: int, window: int) -> list[int]:
    if window <= 0:
        return []

    indexes: list[int] = []
    for offset in range(1, window + 1):
        if chunk_index - offset >= 0:
            indexes.append(chunk_index - offset)
        indexes.append(chunk_index + offset)
    return indexes


def _append_normalized_context_chunks(
    selected: list[dict[str, Any]],
    seen_chunk_ids: set[str],
    chunks: Sequence[Mapping[str, Any]],
    *,
    max_candidates: int,
) -> bool:
    for chunk in chunks:
        if len(selected) >= max_candidates:
            return False
        chunk_id = _normalize_text(chunk.get("chunk_id") or chunk.get("id"))
        if chunk_id is None:
            raise RetrievalContextError("Chunk id is required")
        if chunk_id in seen_chunk_ids:
            continue
        selected.append(dict(chunk))
        seen_chunk_ids.add(chunk_id)
    return len(selected) < max_candidates


def _append_boundary_chunks(
    selected: list[dict[str, Any]],
    seen_chunk_ids: set[str],
    normalized_reranked_chunks: Sequence[Mapping[str, Any]],
    *,
    settings: Settings,
    supabase_client: Any | None,
    retrieval_hints: Mapping[str, Any] | None,
    document_ids: Sequence[UUID | str] | None,
) -> bool:
    normalized_hints = _normalize_retrieval_hints(retrieval_hints or {})
    boundary_positions = normalized_hints["boundary_positions"]
    if not boundary_positions:
        return True

    hint_document_ids = _normalize_document_ids(document_ids)
    if not hint_document_ids:
        hint_document_ids = list(
            dict.fromkeys(chunk["document_id"] for chunk in normalized_reranked_chunks)
        )

    for document_id in hint_document_ids:
        if len(selected) >= settings.RETRIEVAL_CONTEXT_MAX_CANDIDATES:
            return False
        boundary_rows = resolve_boundary_chunks(
            document_id,
            boundary_positions,
            settings=settings,
            supabase_client=supabase_client,
        )
        for boundary_row in boundary_rows:
            boundary_chunk = _normalize_context_chunk(
                boundary_row,
                is_neighbor_context=True,
            )
            if not _append_normalized_context_chunks(
                selected,
                seen_chunk_ids,
                [boundary_chunk],
                max_candidates=settings.RETRIEVAL_CONTEXT_MAX_CANDIDATES,
            ):
                return False
    return True


def _expand_neighbor_context_legacy(
    reranked_chunks: Sequence[Mapping[str, Any]],
    *,
    settings: Settings,
    supabase_client: Any | None,
    retrieval_hints: Mapping[str, Any] | None,
    document_ids: Sequence[UUID | str] | None,
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    seen_chunk_ids: set[str] = set()

    normalized_reranked_chunks = [
        _normalize_context_chunk(chunk)
        for chunk in reranked_chunks
        if _normalize_text(chunk.get("chunk_id") or chunk.get("id")) is not None
    ]

    if not _append_normalized_context_chunks(
        selected,
        seen_chunk_ids,
        normalized_reranked_chunks,
        max_candidates=settings.RETRIEVAL_CONTEXT_MAX_CANDIDATES,
    ):
        return selected

    if not _append_boundary_chunks(
        selected,
        seen_chunk_ids,
        normalized_reranked_chunks,
        settings=settings,
        supabase_client=supabase_client,
        retrieval_hints=retrieval_hints,
        document_ids=document_ids,
    ):
        return selected

    for chunk in normalized_reranked_chunks:
        if len(selected) >= settings.RETRIEVAL_CONTEXT_MAX_CANDIDATES:
            break

        document_id = chunk["document_id"]
        chunk_index = chunk.get("chunk_index")
        if chunk_index is None:
            continue

        neighbor_indexes = _neighbor_indexes(
            chunk_index,
            settings.RETRIEVAL_CONTEXT_WINDOW,
        )
        if not neighbor_indexes:
            continue

        neighbor_rows = chunk_service.get_chunks_by_document_and_indexes(
            document_id,
            neighbor_indexes,
            settings=settings,
            supabase_client=supabase_client,
        )
        neighbor_chunks = [
            _normalize_context_chunk(
                neighbor_row,
                file_name_override=chunk.get("file_name"),
                is_neighbor_context=True,
            )
            for neighbor_row in neighbor_rows
        ]
        if not _append_normalized_context_chunks(
            selected,
            seen_chunk_ids,
            neighbor_chunks,
            max_candidates=settings.RETRIEVAL_CONTEXT_MAX_CANDIDATES,
        ):
            return selected

    return selected


def _expand_neighbor_context_section_aware(
    reranked_chunks: Sequence[Mapping[str, Any]],
    *,
    settings: Settings,
    supabase_client: Any | None,
    retrieval_hints: Mapping[str, Any] | None,
    document_ids: Sequence[UUID | str] | None,
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    seen_chunk_ids: set[str] = set()

    normalized_reranked_chunks = [
        _normalize_context_chunk(chunk)
        for chunk in reranked_chunks
        if _normalize_text(chunk.get("chunk_id") or chunk.get("id")) is not None
    ]

    if not _append_normalized_context_chunks(
        selected,
        seen_chunk_ids,
        normalized_reranked_chunks,
        max_candidates=settings.RETRIEVAL_CONTEXT_MAX_CANDIDATES,
    ):
        return selected

    if not _append_boundary_chunks(
        selected,
        seen_chunk_ids,
        normalized_reranked_chunks,
        settings=settings,
        supabase_client=supabase_client,
        retrieval_hints=retrieval_hints,
        document_ids=document_ids,
    ):
        return selected

    section_window = settings.RETRIEVAL_SECTION_SIBLING_WINDOW
    context_window = settings.RETRIEVAL_CONTEXT_WINDOW

    for chunk in normalized_reranked_chunks:
        if len(selected) >= settings.RETRIEVAL_CONTEXT_MAX_CANDIDATES:
            break

        document_id = chunk["document_id"]
        chunk_index = chunk.get("chunk_index")
        if chunk_index is None:
            continue

        section_indexes = set(_neighbor_indexes(chunk_index, section_window))
        context_indexes = set(_neighbor_indexes(chunk_index, context_window))
        candidate_indexes = sorted(section_indexes | context_indexes)
        if not candidate_indexes:
            continue

        candidate_rows = chunk_service.get_chunks_by_document_and_indexes(
            document_id,
            candidate_indexes,
            settings=settings,
            supabase_client=supabase_client,
        )

        section_chunks: list[dict[str, Any]] = []
        generic_chunks: list[dict[str, Any]] = []
        anchor_section_path = chunk["section_path"]
        for candidate_row in candidate_rows:
            candidate_chunk = _normalize_context_chunk(
                candidate_row,
                file_name_override=chunk.get("file_name"),
                is_neighbor_context=True,
            )
            candidate_index = candidate_chunk.get("chunk_index")
            if candidate_index is None:
                continue
            if (
                candidate_index in section_indexes
                and candidate_chunk["section_path"] == anchor_section_path
            ):
                section_chunks.append(candidate_chunk)
            elif candidate_index in context_indexes:
                generic_chunks.append(candidate_chunk)

        if not _append_normalized_context_chunks(
            selected,
            seen_chunk_ids,
            section_chunks,
            max_candidates=settings.RETRIEVAL_CONTEXT_MAX_CANDIDATES,
        ):
            return selected
        if not _append_normalized_context_chunks(
            selected,
            seen_chunk_ids,
            generic_chunks,
            max_candidates=settings.RETRIEVAL_CONTEXT_MAX_CANDIDATES,
        ):
            return selected

    return selected


def expand_neighbor_context(
    reranked_chunks: Sequence[Mapping[str, Any]],
    *,
    settings: Settings | None = None,
    supabase_client: Any | None = None,
    retrieval_hints: Mapping[str, Any] | None = None,
    document_ids: Sequence[UUID | str] | None = None,
) -> list[dict[str, Any]]:
    resolved_settings = _resolve_settings(settings)
    if not reranked_chunks:
        return []

    context_mode = _normalize_context_mode(resolved_settings.RETRIEVAL_CONTEXT_MODE)
    if context_mode == NEIGHBOR_CONTEXT_MODE:
        return _expand_neighbor_context_legacy(
            reranked_chunks,
            settings=resolved_settings,
            supabase_client=supabase_client,
            retrieval_hints=retrieval_hints,
            document_ids=document_ids,
        )
    if context_mode == SECTION_AWARE_CONTEXT_MODE:
        return _expand_neighbor_context_section_aware(
            reranked_chunks,
            settings=resolved_settings,
            supabase_client=supabase_client,
            retrieval_hints=retrieval_hints,
            document_ids=document_ids,
        )

    raise RetrievalContextError(
        f"Unsupported retrieval context mode: {resolved_settings.RETRIEVAL_CONTEXT_MODE}"
    )
