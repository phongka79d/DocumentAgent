from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from app.core.config import Settings, get_settings
from app.core.contracts import MessageField, TableName
from app.models.schemas import MessageResponse
from app.services.supabase_client import create_supabase_client

MESSAGES_TABLE = TableName.MESSAGES
MIN_MESSAGE_LIMIT = 1
MAX_MESSAGE_LIMIT = 100


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


def _normalize_limit(limit: int | str) -> int:
    try:
        requested_limit = int(limit)
    except (TypeError, ValueError) as exc:
        raise ValueError("limit must be an integer") from exc

    if requested_limit < MIN_MESSAGE_LIMIT:
        return MIN_MESSAGE_LIMIT
    if requested_limit > MAX_MESSAGE_LIMIT:
        return MAX_MESSAGE_LIMIT
    return requested_limit


def _normalize_sources(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    if isinstance(value, Mapping):
        return [dict(value)]
    if isinstance(value, (str, bytes)):
        return []
    if isinstance(value, Iterable):
        sources: list[dict[str, Any]] = []
        for item in value:
            if isinstance(item, Mapping):
                sources.append(dict(item))
        return sources
    return []


def _normalize_metadata(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def _normalize_row(row: Mapping[str, Any]) -> dict[str, Any]:
    normalized = dict(row)
    message_id = normalized.get("id")
    if message_id is not None:
        normalized["id"] = str(message_id)
    normalized["sources"] = _normalize_sources(normalized.get("sources"))
    normalized["metadata"] = _normalize_metadata(normalized.get("metadata"))
    return normalized


def _message_from_row(row: Mapping[str, Any]) -> MessageResponse:
    return MessageResponse.model_validate(_normalize_row(row))


def create_message(
    *,
    question: str,
    answer: str,
    sources: list[dict[str, Any]],
    metadata: dict[str, Any],
    settings: Settings | None = None,
    supabase_client: Any | None = None,
) -> None:
    _resolve_settings(settings)
    client = _resolve_supabase_client(supabase_client)
    payload = {
        MessageField.QUESTION: question,
        MessageField.ANSWER: answer,
        MessageField.SOURCES: sources,
        MessageField.METADATA: metadata,
    }
    client.table(MESSAGES_TABLE).insert(payload).execute()


def list_messages(
    limit: int = 50,
    *,
    settings: Settings | None = None,
    supabase_client: Any | None = None,
) -> list[MessageResponse]:
    _resolve_settings(settings)
    clamped_limit = _normalize_limit(limit)
    client = _resolve_supabase_client(supabase_client)
    response = (
        client.table(MESSAGES_TABLE)
        .select("*")
        .order("created_at", desc=True)
        .limit(clamped_limit)
        .execute()
    )
    return [_message_from_row(row) for row in _response_rows(response)]
