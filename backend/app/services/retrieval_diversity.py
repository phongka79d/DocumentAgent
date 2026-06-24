from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

from app.core.config import Settings, get_settings


def _tokens(value: Any) -> set[str]:
    text = str(value or "").strip().lower()
    # Unicode-safe: Remove punctuation and split by whitespace
    text = re.sub(r"[^\w\s]", "", text, flags=re.UNICODE)
    return set(text.split())


def _overlap_coefficient(left: Any, right: Any) -> float:
    left_tokens = _tokens(left)
    right_tokens = _tokens(right)
    denominator = min(len(left_tokens), len(right_tokens))
    if denominator == 0:
        return 0.0
    return len(left_tokens & right_tokens) / denominator


def _section_path(candidate: Mapping[str, Any]) -> tuple[str, ...]:
    raw = candidate.get("section_path") or []
    if isinstance(raw, (str, bytes)):
        text = str(raw).strip()
        return (text,) if text else ()
    return tuple(str(item).strip() for item in raw if str(item).strip())


def assign_evidence_groups(
    candidates: Sequence[Mapping[str, Any]],
    *,
    settings: Settings | None = None,
) -> list[dict[str, Any]]:
    resolved = settings if settings is not None else get_settings()
    overlap_threshold = resolved.CHUNK_OVERLAP_TOKENS / max(1, resolved.CHUNK_SIZE_TOKENS)
    groups: list[list[dict[str, Any]]] = []
    output: list[dict[str, Any]] = []

    for raw_candidate in candidates:
        candidate = dict(raw_candidate)
        existing_group = str(candidate.get("evidence_group_id") or "").strip()
        if existing_group:
            output.append(candidate)
            continue

        document_id = str(candidate.get("document_id") or "")
        chunk_index = int(candidate.get("chunk_index") or 0)
        section_path = _section_path(candidate)
        matched_group: int | None = None

        for group_index, group in enumerate(groups):
            representative = group[-1]
            if str(representative.get("document_id") or "") != document_id:
                continue
            representative_index = int(representative.get("chunk_index") or 0)
            if abs(chunk_index - representative_index) > resolved.RETRIEVAL_CONTEXT_WINDOW:
                continue
            same_section = bool(section_path) and section_path == _section_path(representative)
            overlaps = _overlap_coefficient(
                candidate.get("content"), representative.get("content")
            ) >= overlap_threshold
            if same_section or overlaps:
                matched_group = group_index
                break

        if matched_group is None:
            matched_group = len(groups)
            groups.append([])
        candidate["evidence_group_id"] = f"evidence-{matched_group + 1}"
        groups[matched_group].append(candidate)
        output.append(candidate)

    return output


def select_group_diverse(
    candidates: Sequence[Mapping[str, Any]],
    *,
    limit: int,
) -> list[dict[str, Any]]:
    if limit <= 0:
        return []
    ordered = [dict(candidate) for candidate in candidates]
    selected: list[dict[str, Any]] = []
    selected_ids: set[str] = set()
    covered_groups: set[str] = set()

    for candidate in ordered:
        chunk_id = str(candidate.get("chunk_id") or candidate.get("id") or "")
        group_id = str(candidate.get("evidence_group_id") or chunk_id)
        if not chunk_id or chunk_id in selected_ids or group_id in covered_groups:
            continue
        selected.append(candidate)
        selected_ids.add(chunk_id)
        covered_groups.add(group_id)
        if len(selected) >= limit:
            return selected

    for candidate in ordered:
        chunk_id = str(candidate.get("chunk_id") or candidate.get("id") or "")
        if not chunk_id or chunk_id in selected_ids:
            continue
        selected.append(candidate)
        selected_ids.add(chunk_id)
        if len(selected) >= limit:
            break
    return selected
