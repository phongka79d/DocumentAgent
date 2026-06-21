from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Any
from uuid import UUID

from app.core.contracts import SummaryType, TableName
from app.services.supabase_client import create_supabase_client

DOCUMENT_SUMMARIES_TABLE = TableName.DOCUMENT_SUMMARIES


def _resolve_supabase_client(supabase_client: Any | None = None) -> Any:
    return supabase_client if supabase_client is not None else create_supabase_client()


def _response_rows(response: Any) -> list[dict[str, Any]]:
    data = getattr(response, "data", response)
    if data is None:
        return []
    if isinstance(data, Mapping):
        return [dict(data)]
    if isinstance(data, Iterable) and not isinstance(data, (str, bytes)):
        return [dict(row) for row in data]
    return []


def _normalize_uuid(value: UUID | str, field_name: str) -> str:
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError, AttributeError) as exc:
        raise ValueError(f"{field_name} must be a valid UUID") from exc


def _normalize_text(value: Any, field_name: str, *, nullable: bool = False) -> str | None:
    if value is None and nullable:
        return None
    cleaned = str(value or "").strip()
    if not cleaned:
        if nullable:
            return None
        raise ValueError(f"{field_name} is required")
    return cleaned


def _normalize_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (str, bytes)):
        value = [value]
    if not isinstance(value, Sequence):
        raise ValueError("section_path must be a sequence")
    return [text for item in value if (text := str(item).strip())]


def _normalize_uuid_list(value: Any, field_name: str) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (str, bytes, UUID)):
        value = [value]
    if not isinstance(value, Iterable):
        raise ValueError(f"{field_name} must be a sequence")
    normalized: list[str] = []
    seen: set[str] = set()
    for item in value:
        item_id = _normalize_uuid(item, field_name)
        if item_id not in seen:
            normalized.append(item_id)
            seen.add(item_id)
    return normalized


def _normalize_payload(
    *,
    document_id: UUID | str,
    summary_type: SummaryType | str,
    content: str,
    model: str,
    heading: str | None = None,
    section_path: Sequence[str] | None = None,
    source_chunk_ids: Iterable[UUID | str] | None = None,
) -> dict[str, Any]:
    normalized_type = SummaryType(summary_type).value
    normalized_path = _normalize_string_list(section_path)
    normalized_heading = _normalize_text(heading, "heading", nullable=True)
    if normalized_type == SummaryType.DOCUMENT:
        normalized_heading = None
        normalized_path = []
    return {
        "document_id": _normalize_uuid(document_id, "document_id"),
        "summary_type": normalized_type,
        "heading": normalized_heading,
        "section_path": normalized_path,
        "content": _normalize_text(content, "content"),
        "source_chunk_ids": _normalize_uuid_list(source_chunk_ids, "source_chunk_ids"),
        "model": _normalize_text(model, "model"),
    }


def _normalize_row(row: Mapping[str, Any]) -> dict[str, Any]:
    normalized = dict(row)
    if normalized.get("id") is not None:
        normalized["id"] = _normalize_uuid(normalized["id"], "id")
    if normalized.get("document_id") is not None:
        normalized["document_id"] = _normalize_uuid(
            normalized["document_id"], "document_id"
        )
    normalized["summary_type"] = SummaryType(normalized["summary_type"]).value
    normalized["section_path"] = _normalize_string_list(
        normalized.get("section_path")
    )
    normalized["source_chunk_ids"] = _normalize_uuid_list(
        normalized.get("source_chunk_ids"), "source_chunk_ids"
    )
    return normalized


def _summary_sort_key(row: Mapping[str, Any]) -> tuple[Any, ...]:
    summary_type = SummaryType(row["summary_type"])
    return (
        0 if summary_type is SummaryType.DOCUMENT else 1,
        tuple(row.get("section_path") or []),
        str(row.get("heading") or ""),
        str(row.get("id") or ""),
    )


def create_summary(
    *,
    document_id: UUID | str,
    summary_type: SummaryType | str,
    content: str,
    model: str,
    heading: str | None = None,
    section_path: Sequence[str] | None = None,
    source_chunk_ids: Iterable[UUID | str] | None = None,
    supabase_client: Any | None = None,
) -> dict[str, Any]:
    payload = _normalize_payload(
        document_id=document_id,
        summary_type=summary_type,
        heading=heading,
        section_path=section_path,
        content=content,
        source_chunk_ids=source_chunk_ids,
        model=model,
    )
    client = _resolve_supabase_client(supabase_client)
    rows = _response_rows(
        client.table(DOCUMENT_SUMMARIES_TABLE).insert(payload).execute()
    )
    return _normalize_row(rows[0]) if rows else payload


def list_summaries(
    document_id: UUID | str, *, supabase_client: Any | None = None
) -> list[dict[str, Any]]:
    normalized_document_id = _normalize_uuid(document_id, "document_id")
    client = _resolve_supabase_client(supabase_client)
    response = (
        client.table(DOCUMENT_SUMMARIES_TABLE)
        .select("*")
        .eq("document_id", normalized_document_id)
        .execute()
    )
    rows = [_normalize_row(row) for row in _response_rows(response)]
    return sorted(rows, key=_summary_sort_key)


def replace_document_summaries(
    document_id: UUID | str,
    summary_records: Iterable[Mapping[str, Any]],
    *,
    supabase_client: Any | None = None,
) -> list[dict[str, Any]]:
    normalized_document_id = _normalize_uuid(document_id, "document_id")
    payloads = [
        _normalize_payload(
            document_id=normalized_document_id,
            summary_type=record["summary_type"],
            heading=record.get("heading"),
            section_path=record.get("section_path"),
            content=record["content"],
            source_chunk_ids=record.get("source_chunk_ids"),
            model=record["model"],
        )
        for record in summary_records
    ]
    client = _resolve_supabase_client(supabase_client)
    (
        client.table(DOCUMENT_SUMMARIES_TABLE)
        .delete()
        .eq("document_id", normalized_document_id)
        .execute()
    )
    if not payloads:
        return []
    rows = _response_rows(
        client.table(DOCUMENT_SUMMARIES_TABLE).insert(payloads).execute()
    )
    normalized_rows = [_normalize_row(row) for row in rows] if rows else payloads
    return sorted(normalized_rows, key=_summary_sort_key)


def delete_document_summaries(
    document_id: UUID | str, *, supabase_client: Any | None = None
) -> None:
    normalized_document_id = _normalize_uuid(document_id, "document_id")
    client = _resolve_supabase_client(supabase_client)
    (
        client.table(DOCUMENT_SUMMARIES_TABLE)
        .delete()
        .eq("document_id", normalized_document_id)
        .execute()
    )
