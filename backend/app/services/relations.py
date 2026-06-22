from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from qdrant_client.http import models as qdrant_models

from app.core.config import Settings, get_settings
from app.core.contracts import DocumentStatus, QdrantPayloadKey, RelationType, SummaryType, TableName
from app.services.qdrant_client import create_qdrant_client
from app.services.shopaikey_client import create_shopaikey_client
from app.services.supabase_client import create_supabase_client

DOCUMENT_RELATIONS_TABLE = TableName.DOCUMENT_RELATIONS
DOCUMENTS_TABLE = TableName.DOCUMENTS
RELATION_SYSTEM_PROMPT = (
    "You identify lightweight document relations from supplied summaries and "
    "candidate evidence. Return strict JSON only with a top-level relations array."
)


@dataclass
class RelationCandidate:
    document_id: str
    evidence_chunk_ids: list[str] = field(default_factory=list)


def _resolve_supabase_client(supabase_client: Any | None = None) -> Any:
    return supabase_client if supabase_client is not None else create_supabase_client()


def _resolve_settings(settings: Settings | None = None) -> Settings:
    return settings if settings is not None else get_settings()


def _resolve_qdrant_client(settings: Settings, qdrant_client: Any | None = None) -> Any:
    return qdrant_client if qdrant_client is not None else create_qdrant_client(settings)


def _resolve_shopaikey_client(settings: Settings, shopaikey_client: Any | None = None) -> Any:
    return shopaikey_client if shopaikey_client is not None else create_shopaikey_client(settings)


def _response_rows(response: Any) -> list[dict[str, Any]]:
    data = getattr(response, "data", response)
    if data is None:
        return []
    if isinstance(data, Mapping):
        return [dict(data)]
    if isinstance(data, Iterable) and not isinstance(data, (str, bytes)):
        return [dict(row) for row in data]
    return []


def _point_rows(response: Any) -> list[dict[str, Any]]:
    data = getattr(response, "points", response)
    if data is None:
        return []
    if isinstance(data, Mapping):
        items = [data]
    elif isinstance(data, Iterable) and not isinstance(data, (str, bytes)):
        items = list(data)
    else:
        items = [data]

    rows: list[dict[str, Any]] = []
    for item in items:
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


def _normalize_optional_text(value: Any) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


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


def _document_summary_content(summary_records: Iterable[Mapping[str, Any]]) -> str | None:
    fallback: str | None = None
    for record in summary_records:
        content = _normalize_optional_text(record.get("content"))
        if content is None:
            continue
        summary_type = record.get("summary_type")
        try:
            if SummaryType(summary_type) is SummaryType.DOCUMENT:
                return content
        except ValueError:
            pass
        if fallback is None:
            fallback = content
    return fallback


def _chat_content(response: Any) -> str:
    choices = getattr(response, "choices", None)
    if choices is None and isinstance(response, Mapping):
        choices = response.get("choices")
    if not choices:
        raise ValueError("Relation response missing choices")
    first = choices[0]
    message = getattr(first, "message", None)
    if message is None and isinstance(first, Mapping):
        message = first.get("message")
    content = getattr(message, "content", None)
    if content is None and isinstance(message, Mapping):
        content = message.get("content")
    text = str(content or "").strip()
    if not text:
        raise ValueError("Relation response was empty")
    return text


def _embedding_vector(response: Any) -> list[float]:
    items = getattr(response, "data", response)
    if not items:
        raise ValueError("Relation embedding response missing vectors")
    first = items[0]
    embedding = getattr(first, "embedding", None)
    if embedding is None and isinstance(first, Mapping):
        embedding = first.get("embedding")
    if embedding is None:
        raise ValueError("Relation embedding response missing vectors")
    vector = [float(value) for value in embedding]
    if not vector:
        raise ValueError("Relation embedding response contained empty vector")
    return vector


def _payload_value(row: Mapping[str, Any], key: str) -> Any:
    payload = row.get("payload")
    if isinstance(payload, Mapping):
        return payload.get(key)
    return None


def _ready_document(client: Any, document_id: str) -> bool:
    rows = _response_rows(
        client.table(DOCUMENTS_TABLE)
        .select("id,status")
        .eq("id", document_id)
        .execute()
    )
    if not rows:
        return False
    return rows[0].get("status") == DocumentStatus.READY


def _relation_candidates_from_points(
    *,
    source_document_id: str,
    points: Iterable[Mapping[str, Any]],
    supabase_client: Any,
    max_related_documents: int,
) -> list[RelationCandidate]:
    grouped: dict[str, RelationCandidate] = {}
    for point in points:
        document_id = _normalize_optional_text(
            _payload_value(point, QdrantPayloadKey.DOCUMENT_ID)
        )
        if document_id is None or document_id == source_document_id:
            continue
        chunk_id = _normalize_optional_text(
            _payload_value(point, QdrantPayloadKey.CHUNK_ID) or point.get("id")
        )
        if chunk_id is None:
            continue
        candidate = grouped.setdefault(
            document_id,
            RelationCandidate(document_id=document_id),
        )
        if chunk_id not in candidate.evidence_chunk_ids:
            candidate.evidence_chunk_ids.append(chunk_id)

    ready_candidates: list[RelationCandidate] = []
    for candidate in grouped.values():
        if not _ready_document(supabase_client, candidate.document_id):
            continue
        ready_candidates.append(candidate)
        if len(ready_candidates) >= max_related_documents:
            break
    return ready_candidates


def select_relation_candidates(
    *,
    document_id: UUID | str,
    summary_content: str,
    settings: Settings | None = None,
    shopaikey_client: Any | None = None,
    qdrant_client: Any | None = None,
    supabase_client: Any | None = None,
) -> list[RelationCandidate]:
    resolved_settings = _resolve_settings(settings)
    normalized_document_id = _normalize_uuid(document_id, "document_id")
    client = _resolve_shopaikey_client(resolved_settings, shopaikey_client)
    embedding_response = client.embeddings.create(
        model=resolved_settings.SHOPAIKEY_EMBEDDING_MODEL,
        input=[_normalize_text(summary_content, "summary_content")],
    )
    query_embedding = _embedding_vector(embedding_response)

    qdrant = _resolve_qdrant_client(resolved_settings, qdrant_client)
    query_filter = qdrant_models.Filter(
        must_not=[
            qdrant_models.FieldCondition(
                key=QdrantPayloadKey.DOCUMENT_ID,
                match=qdrant_models.MatchValue(value=normalized_document_id),
            )
        ]
    )
    response = qdrant.query_points(
        collection_name=resolved_settings.QDRANT_COLLECTION,
        query=query_embedding,
        query_filter=query_filter,
        limit=max(resolved_settings.RELATION_MAX_RELATED_DOCUMENTS * 5, 1),
        with_payload=True,
        with_vectors=False,
    )
    return _relation_candidates_from_points(
        source_document_id=normalized_document_id,
        points=_point_rows(response),
        supabase_client=_resolve_supabase_client(supabase_client),
        max_related_documents=resolved_settings.RELATION_MAX_RELATED_DOCUMENTS,
    )


def _relation_prompt(
    *,
    source_document_id: str,
    summary_content: str,
    candidates: Iterable[RelationCandidate],
) -> str:
    candidate_lines = [
        (
            f"- document_id: {candidate.document_id}\n"
            f"  evidence_chunk_ids: {candidate.evidence_chunk_ids}"
        )
        for candidate in candidates
    ]
    allowed_types = [relation_type.value for relation_type in RelationType]
    return (
        "Create zero or more bounded document relations for the source document.\n"
        f"Source document id: {source_document_id}\n"
        f"Source document summary:\n{summary_content}\n\n"
        f"Allowed relation types: {allowed_types}\n"
        "Allowed target documents and evidence chunks:\n"
        + "\n".join(candidate_lines)
        + "\n\nReturn JSON exactly like: "
        '{"relations":[{"target_document_id":"uuid","relation_type":"supports",'
        '"description":"short reason","evidence_chunk_ids":["uuid"],"confidence":0.8}]}'
    )


def _strict_relation_json(content: str) -> tuple[list[Mapping[str, Any]], int]:
    try:
        payload = json.loads(content)
    except json.JSONDecodeError:
        return [], 1
    if not isinstance(payload, Mapping):
        return [], 1
    relations = payload.get("relations")
    if not isinstance(relations, list):
        return [], 1
    return [item for item in relations if isinstance(item, Mapping)], sum(
        1 for item in relations if not isinstance(item, Mapping)
    )


def _validated_relation_records(
    *,
    source_document_id: str,
    candidates: Iterable[RelationCandidate],
    raw_relations: Iterable[Mapping[str, Any]],
    model: str,
) -> tuple[list[dict[str, Any]], int]:
    candidate_evidence = {
        candidate.document_id: set(candidate.evidence_chunk_ids)
        for candidate in candidates
    }
    accepted: list[dict[str, Any]] = []
    discarded = 0
    for relation in raw_relations:
        try:
            target_document_id = _normalize_uuid(
                relation.get("target_document_id"),
                "target_document_id",
            )
            if target_document_id not in candidate_evidence:
                raise ValueError("target_document_id is not an allowed candidate")
            evidence_chunk_ids = _normalize_evidence_ids(
                relation.get("evidence_chunk_ids")
            )
            if not evidence_chunk_ids:
                raise ValueError("evidence_chunk_ids are required")
            if any(
                chunk_id not in candidate_evidence[target_document_id]
                for chunk_id in evidence_chunk_ids
            ):
                raise ValueError("evidence_chunk_ids must belong to the candidate")
            accepted.append(
                _normalize_payload(
                    source_document_id=source_document_id,
                    target_document_id=target_document_id,
                    relation_type=relation.get("relation_type"),
                    description=relation.get("description"),
                    evidence_chunk_ids=evidence_chunk_ids,
                    confidence=relation.get("confidence"),
                    model=model,
                )
            )
        except Exception:
            discarded += 1
    return accepted, discarded


def _dedupe_payloads(payloads: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    best_by_key: dict[tuple[str, str, str], dict[str, Any]] = {}
    for payload in payloads:
        normalized = dict(payload)
        key = (
            str(normalized["source_document_id"]),
            str(normalized["target_document_id"]),
            str(normalized["relation_type"]),
        )
        existing = best_by_key.get(key)
        if existing is None or float(normalized["confidence"]) > float(
            existing["confidence"]
        ):
            best_by_key[key] = normalized
    return sorted(best_by_key.values(), key=_relation_sort_key)


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
    payloads = _dedupe_payloads(payloads)
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


def update_document_relations(
    document_id: UUID | str,
    *,
    summary_records: Iterable[Mapping[str, Any]] | None = None,
    settings: Settings | None = None,
    shopaikey_client: Any | None = None,
    qdrant_client: Any | None = None,
    supabase_client: Any | None = None,
) -> dict[str, Any]:
    resolved_settings = _resolve_settings(settings)
    normalized_document_id = _normalize_uuid(document_id, "document_id")
    if not resolved_settings.ENABLE_RELATION_RETRIEVAL:
        return {"status": "skipped", "reason": "relation retrieval disabled"}

    records = list(summary_records or [])
    summary_content = _document_summary_content(records)
    if summary_content is None:
        return {"status": "skipped", "reason": "document summary missing"}

    client = _resolve_supabase_client(supabase_client)
    candidates = select_relation_candidates(
        document_id=normalized_document_id,
        summary_content=summary_content,
        settings=resolved_settings,
        shopaikey_client=shopaikey_client,
        qdrant_client=qdrant_client,
        supabase_client=client,
    )
    if not candidates:
        replace_document_relations(
            normalized_document_id,
            [],
            supabase_client=client,
        )
        return {
            "status": "updated",
            "candidate_document_count": 0,
            "accepted_relation_count": 0,
            "discarded_relation_count": 0,
        }

    model_client = _resolve_shopaikey_client(resolved_settings, shopaikey_client)
    response = model_client.chat.completions.create(
        model=resolved_settings.SHOPAIKEY_CHAT_MODEL,
        messages=[
            {"role": "system", "content": RELATION_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": _relation_prompt(
                    source_document_id=normalized_document_id,
                    summary_content=summary_content,
                    candidates=candidates,
                ),
            },
        ],
        temperature=0,
        max_tokens=600,
    )
    raw_relations, discarded_count = _strict_relation_json(_chat_content(response))
    accepted_records, validation_discards = _validated_relation_records(
        source_document_id=normalized_document_id,
        candidates=candidates,
        raw_relations=raw_relations,
        model=resolved_settings.SHOPAIKEY_CHAT_MODEL,
    )
    saved_relations = replace_document_relations(
        normalized_document_id,
        accepted_records,
        supabase_client=client,
    )
    return {
        "status": "updated",
        "candidate_document_count": len(candidates),
        "accepted_relation_count": len(saved_relations),
        "discarded_relation_count": discarded_count + validation_discards,
    }


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
