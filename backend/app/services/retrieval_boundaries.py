from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any
from uuid import UUID

from app.core.config import Settings, get_settings
from app.core.contracts import RetrievalBoundary
from app.services import chunks as chunk_service


def _resolve_settings(settings: Settings | None = None) -> Settings:
    return settings if settings is not None else get_settings()


def _normalize_boundary_positions(
    boundary_positions: Sequence[str | RetrievalBoundary],
) -> list[RetrievalBoundary]:
    positions: list[RetrievalBoundary] = []
    seen: set[RetrievalBoundary] = set()
    for raw_position in boundary_positions:
        try:
            position = RetrievalBoundary(raw_position)
        except ValueError:
            continue
        if position in seen:
            continue
        positions.append(position)
        seen.add(position)
    return positions


def _dedupe_chunks(chunks: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for chunk in chunks:
        chunk_key = chunk.get("id")
        if chunk_key is None:
            chunk_key = chunk.get("chunk_index")
        key = str(chunk_key)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(dict(chunk))
    return deduped


def _last_chunk_index(chunk: Mapping[str, Any] | None) -> int | None:
    if chunk is None:
        return None
    try:
        return int(chunk.get("chunk_index"))
    except (TypeError, ValueError):
        return None


def resolve_boundary_chunks(
    document_id: UUID | str,
    boundary_positions: Sequence[str | RetrievalBoundary],
    *,
    settings: Settings | None = None,
    supabase_client: Any | None = None,
) -> list[dict[str, Any]]:
    resolved_settings = _resolve_settings(settings)
    positions = _normalize_boundary_positions(boundary_positions)
    chunks: list[dict[str, Any]] = []

    if RetrievalBoundary.BEGINNING in positions:
        start_count = max(0, resolved_settings.RETRIEVAL_BOUNDARY_START_CHUNKS)
        if start_count > 0:
            chunks.extend(
                chunk_service.get_chunks_by_document_and_indexes(
                    document_id,
                    range(start_count),
                    settings=resolved_settings,
                    supabase_client=supabase_client,
                )
            )

    if RetrievalBoundary.END in positions:
        end_count = max(0, resolved_settings.RETRIEVAL_BOUNDARY_END_CHUNKS)
        if end_count > 0:
            last_chunk = chunk_service.get_last_chunk_by_document(
                document_id,
                settings=resolved_settings,
                supabase_client=supabase_client,
            )
            last_index = _last_chunk_index(last_chunk)
            if last_index is not None:
                first_index = max(0, last_index - end_count + 1)
                chunks.extend(
                    chunk_service.get_chunks_by_document_and_indexes(
                        document_id,
                        range(first_index, last_index + 1),
                        settings=resolved_settings,
                        supabase_client=supabase_client,
                    )
                )

    return _dedupe_chunks(chunks)
