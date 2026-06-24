from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Any
from uuid import UUID

from app.models.schemas import RetrievalFilters


def _response_rows(response: Any) -> list[dict[str, Any]]:
    data = getattr(response, "points", response)
    if data is None:
        return []
    if isinstance(data, Mapping):
        return [dict(data)]
    if isinstance(data, list):
        items = data
    elif isinstance(data, Iterable) and not isinstance(data, (str, bytes)):
        items = list(data)
    else:
        items = [data]

    rows: list[dict[str, Any]] = []
    for item in items:
        if isinstance(item, Mapping):
            rows.append(dict(item))
            continue
        if hasattr(item, "model_dump"):
            rows.append(dict(item.model_dump()))
            continue
        if hasattr(item, "__dict__"):
            rows.append(
                {
                    key: value
                    for key, value in vars(item).items()
                    if not key.startswith("_")
                }
            )
            continue
        try:
            rows.append(dict(item))
        except Exception:
            rows.append({"value": item})
    return rows


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


def _normalize_uuid(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, UUID):
        return str(value)
    text = str(value).strip()
    return text or None


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
