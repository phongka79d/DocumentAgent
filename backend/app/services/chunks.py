from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any
from uuid import UUID

from app.core.config import Settings, get_settings
from app.services.supabase_client import create_supabase_client

DOCUMENT_CHUNKS_TABLE = "document_chunks"


def _resolve_settings(settings: Settings | None = None) -> Settings:
    return settings if settings is not None else get_settings()


def _resolve_supabase_client(supabase_client: Any | None = None) -> Any:
    return supabase_client if supabase_client is not None else create_supabase_client()


def _response_rows(response: Any) -> list[dict[str, Any]]:
    data = getattr(response, "data", response)
    if data is None:
        return []
    if isinstance(data, list):
        return [dict(row) for row in data]
    if isinstance(data, Mapping):
        return [dict(data)]
    if isinstance(data, Iterable) and not isinstance(data, (str, bytes)):
        return [dict(row) for row in data]
    return [dict(data)]


def _normalize_chunk_index_values(chunk_indexes: Iterable[int | str]) -> list[int]:
    normalized: list[int] = []
    seen: set[int] = set()
    for value in chunk_indexes:
        if value is None:
            continue
        try:
            index = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError("chunk_indexes must contain integers") from exc
        if index < 0 or index in seen:
            continue
        seen.add(index)
        normalized.append(index)
    normalized.sort()
    return normalized


def _normalize_row(row: Mapping[str, Any]) -> dict[str, Any]:
    normalized = dict(row)
    row_id = normalized.get("id")
    if row_id is not None:
        normalized["id"] = str(row_id)
    document_id = normalized.get("document_id")
    if document_id is not None:
        normalized["document_id"] = str(document_id)
    return normalized


def get_chunks_by_document_and_indexes(
    document_id: UUID | str,
    chunk_indexes: Iterable[int | str],
    *,
    settings: Settings | None = None,
    supabase_client: Any | None = None,
) -> list[dict[str, Any]]:
    _resolve_settings(settings)
    indexes = _normalize_chunk_index_values(chunk_indexes)
    if not indexes:
        return []

    client = _resolve_supabase_client(supabase_client)
    response = (
        client.table(DOCUMENT_CHUNKS_TABLE)
        .select("*")
        .eq("document_id", str(document_id))
        .in_("chunk_index", indexes)
        .order("chunk_index")
        .execute()
    )
    return [_normalize_row(row) for row in _response_rows(response)]


def get_chunk_by_document_and_index(
    document_id: UUID | str,
    chunk_index: int,
    *,
    settings: Settings | None = None,
    supabase_client: Any | None = None,
) -> dict[str, Any] | None:
    rows = get_chunks_by_document_and_indexes(
        document_id,
        [chunk_index],
        settings=settings,
        supabase_client=supabase_client,
    )
    return rows[0] if rows else None
