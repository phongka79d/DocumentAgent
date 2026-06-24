from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any
from uuid import UUID

from app.core.config import Settings, get_settings
from app.rag.formatting import normalize_text
from app.models.schemas import RetrievalFilters


def _resolve_settings(settings: Settings | None = None) -> Settings:
    return settings if settings is not None else get_settings()


def _normalize_document_ids(
    document_ids: Sequence[UUID | str] | UUID | str | bytes | None,
) -> list[str]:
    if document_ids is None:
        return []

    if isinstance(document_ids, (str, bytes)):
        text = normalize_text(document_ids)
        return [text] if text is not None else []

    normalized: list[str] = []
    seen: set[str] = set()
    for value in document_ids:
        text = normalize_text(value)
        if text is None or text in seen:
            continue
        normalized.append(text)
        seen.add(text)
    return normalized


def _normalize_filters(filters: Any) -> dict[str, Any]:
    if isinstance(filters, RetrievalFilters):
        model = filters
    else:
        model = RetrievalFilters.model_validate(filters)
    return model.model_dump(mode="json", exclude_none=True)


def prepare_query_node(
    state: Mapping[str, Any], *, settings: Settings | None = None
) -> dict[str, Any]:
    from app.core.config import get_settings as _get_settings

    _resolve_settings(settings)

    question = normalize_text(state.get("question"))
    if question is None:
        return {"error_message": "question is required"}

    document_ids = _normalize_document_ids(state.get("document_ids"))
    save_message = bool(state.get("save_message", False))
    result = {
        "question": question,
        "prepared_query": question,
        "document_ids": document_ids,
        "save_message": save_message,
    }
    if "filters" in state:
        try:
            result["filters"] = _normalize_filters(state.get("filters") or {})
        except Exception:
            return {"error_message": "invalid retrieval filters"}
    return result
