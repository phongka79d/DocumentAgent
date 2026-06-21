from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any
from uuid import UUID

from app.core.contracts import RelationType, TableName
from app.services.supabase_client import create_supabase_client

DOCUMENT_RELATIONS_TABLE = TableName.DOCUMENT_RELATIONS


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


def _normalize_text(value: Any, field_name: str) -> str:
    cleaned = str(value or "").strip()
    if not cleaned:
        raise ValueError(f"{field_name} is required")
    return cleaned


def _canonical_pair(
    source_document_id: UUID | str, target_document_id: UUID | str
) -> tuple[str, str]:
    source = _normalize_uuid(source_document_id, "source_document_id")
    target = _normalize_uuid(target_document_id, "target_document_id")
    if source == target:
        raise ValueError("source_document_id and target_document_id must be different")
    return (source, target) if source < target else (target, source)


def _normalize_evidence_ids(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (str, bytes, UUID)):
        value = [value]
    if not isinstance(value, Iterable):
        raise ValueError("evidence_chunk_ids must be a sequence")
    normalized: list[str] = []
    seen: set[str] = set()
    for item in value:
        item_id = _normalize_uuid(item, "evidence_chunk_ids")
        if item_id not in seen:
            normalized.append(item_id)
            seen.add(item_id)
    return normalized


def _normalize_payload(
    *,
    source_document_id: UUID | str,
    target_document_id: UUID | str,
    relation_type: RelationType | str,
    description: str,
    evidence_chunk_ids: Iterable[UUID | str] | None,
    confidence: float,
    model: str,
) -> dict[str, Any]:
    source, target = _canonical_pair(source_document_id, target_document_id)
    normalized_confidence = float(confidence)
    if not 0 <= normalized_confidence <= 1:
        raise ValueError("confidence must be between 0 and 1")
    return {
        "source_document_id": source,
        "target_document_id": target,
        "relation_type": RelationType(relation_type).value,
        "description": _normalize_text(description, "description"),
        "evidence_chunk_ids": _normalize_evidence_ids(evidence_chunk_ids),
        "confidence": normalized_confidence,
        "model": _normalize_text(model, "model"),
    }


def _normalize_row(row: Mapping[str, Any]) -> dict[str, Any]:
    normalized = dict(row)
    if normalized.get("id") is not None:
        normalized["id"] = _normalize_uuid(normalized["id"], "id")
    source, target = _canonical_pair(
        normalized["source_document_id"], normalized["target_document_id"]
    )
    normalized["source_document_id"] = source
    normalized["target_document_id"] = target
    normalized["relation_type"] = RelationType(normalized["relation_type"]).value
    normalized["evidence_chunk_ids"] = _normalize_evidence_ids(
        normalized.get("evidence_chunk_ids")
    )
    normalized["confidence"] = float(normalized["confidence"])
    return normalized


def _relation_sort_key(row: Mapping[str, Any]) -> tuple[str, ...]:
    return (
        str(row["source_document_id"]),
        str(row["target_document_id"]),
        str(row["relation_type"]),
        str(row.get("id") or ""),
    )


def create_relation(
    *,
    source_document_id: UUID | str,
    target_document_id: UUID | str,
    relation_type: RelationType | str,
    description: str,
    evidence_chunk_ids: Iterable[UUID | str] | None,
    confidence: float,
    model: str,
    supabase_client: Any | None = None,
) -> dict[str, Any]:
    payload = _normalize_payload(
        source_document_id=source_document_id,
        target_document_id=target_document_id,
        relation_type=relation_type,
        description=description,
        evidence_chunk_ids=evidence_chunk_ids,
        confidence=confidence,
        model=model,
    )
    client = _resolve_supabase_client(supabase_client)
    rows = _response_rows(
        client.table(DOCUMENT_RELATIONS_TABLE).insert(payload).execute()
    )
    return _normalize_row(rows[0]) if rows else payload


def list_relations(
    document_id: UUID | str, *, supabase_client: Any | None = None
) -> list[dict[str, Any]]:
    normalized_document_id = _normalize_uuid(document_id, "document_id")
    client = _resolve_supabase_client(supabase_client)
    expression = (
        f"source_document_id.eq.{normalized_document_id},"
        f"target_document_id.eq.{normalized_document_id}"
    )
    response = (
        client.table(DOCUMENT_RELATIONS_TABLE)
        .select("*")
        .or_(expression)
        .execute()
    )
    return sorted(
        (_normalize_row(row) for row in _response_rows(response)),
        key=_relation_sort_key,
    )


def replace_document_relations(
    document_id: UUID | str,
    relation_records: Iterable[Mapping[str, Any]],
    *,
    supabase_client: Any | None = None,
) -> list[dict[str, Any]]:
    normalized_document_id = _normalize_uuid(document_id, "document_id")
    payloads = [
        _normalize_payload(
            source_document_id=record["source_document_id"],
            target_document_id=record["target_document_id"],
            relation_type=record["relation_type"],
            description=record["description"],
            evidence_chunk_ids=record.get("evidence_chunk_ids"),
            confidence=record["confidence"],
            model=record["model"],
        )
        for record in relation_records
    ]
    if any(
        normalized_document_id
        not in (payload["source_document_id"], payload["target_document_id"])
        for payload in payloads
    ):
        raise ValueError("every replacement relation must involve document_id")
    expression = (
        f"source_document_id.eq.{normalized_document_id},"
        f"target_document_id.eq.{normalized_document_id}"
    )
    client = _resolve_supabase_client(supabase_client)
    (
        client.table(DOCUMENT_RELATIONS_TABLE)
        .delete()
        .or_(expression)
        .execute()
    )
    if not payloads:
        return []
    rows = _response_rows(
        client.table(DOCUMENT_RELATIONS_TABLE).insert(payloads).execute()
    )
    normalized_rows = [_normalize_row(row) for row in rows] if rows else payloads
    return sorted(normalized_rows, key=_relation_sort_key)


def delete_document_relations(
    document_id: UUID | str, *, supabase_client: Any | None = None
) -> None:
    normalized_document_id = _normalize_uuid(document_id, "document_id")
    expression = (
        f"source_document_id.eq.{normalized_document_id},"
        f"target_document_id.eq.{normalized_document_id}"
    )
    client = _resolve_supabase_client(supabase_client)
    client.table(DOCUMENT_RELATIONS_TABLE).delete().or_(expression).execute()
