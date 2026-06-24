from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any
from uuid import UUID

from qdrant_client.http import models as qdrant_models

from app.core.contracts import QdrantPayloadKey
from app.models.schemas import RetrievalFilters
from app.services.retrieval_normalization import (
    _normalize_document_ids,
    _normalize_filters,
    _normalize_int,
    _normalize_section_path,
    _normalize_text,
)


def build_qdrant_filter(
    document_ids: Sequence[UUID | str] | None,
    filters: RetrievalFilters | Mapping[str, Any] | None = None,
) -> qdrant_models.Filter | None:
    from app.services import retrieval
    payload_key = getattr(retrieval, "QdrantPayloadKey", QdrantPayloadKey)

    conditions: list[qdrant_models.Condition] = []

    normalized_document_ids = _normalize_document_ids(document_ids)
    if normalized_document_ids:
        conditions.append(
            qdrant_models.FieldCondition(
                key=payload_key.DOCUMENT_ID,
                match=qdrant_models.MatchAny(any=normalized_document_ids),
            )
        )

    normalized_filters = _normalize_filters(filters)
    mime_types = _normalize_section_path(normalized_filters.get("mime_types"))
    if mime_types:
        conditions.append(
            qdrant_models.FieldCondition(
                key=payload_key.MIME_TYPE,
                match=qdrant_models.MatchAny(any=mime_types),
            )
        )

    heading = _normalize_text(normalized_filters.get("heading"))
    if heading is not None:
        conditions.append(
            qdrant_models.FieldCondition(
                key=payload_key.HEADING,
                match=qdrant_models.MatchText(text=heading),
            )
        )

    for section_segment in _normalize_section_path(normalized_filters.get("section_path")):
        conditions.append(
            qdrant_models.FieldCondition(
                key=payload_key.SECTION_PATH,
                match=qdrant_models.MatchValue(value=section_segment),
            )
        )

    page_start = _normalize_int(normalized_filters.get("page_start"))
    page_end = _normalize_int(normalized_filters.get("page_end"))
    if page_end is not None:
        conditions.append(
            qdrant_models.FieldCondition(
                key=payload_key.PAGE_START,
                range=qdrant_models.Range(lte=page_end),
            )
        )
    if page_start is not None:
        conditions.append(
            qdrant_models.FieldCondition(
                key=payload_key.PAGE_END,
                range=qdrant_models.Range(gte=page_start),
            )
        )

    if not conditions:
        return None

    return qdrant_models.Filter(must=conditions)


def build_document_id_filter(
    document_ids: Sequence[UUID | str] | None,
) -> qdrant_models.Filter | None:
    return build_qdrant_filter(document_ids)
