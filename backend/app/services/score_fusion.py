from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from app.core.config import Settings, get_settings
from app.core.contracts import RetrievalPath


def _resolve_settings(settings: Settings | None = None) -> Settings:
    return settings if settings is not None else get_settings()


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


def _path_value(value: Any) -> str | None:
    if isinstance(value, RetrievalPath):
        return value.value
    text = _normalize_text(value)
    if text in {path.value for path in RetrievalPath}:
        return text
    return None


def _candidate_paths(candidate: Mapping[str, Any]) -> list[str]:
    paths: list[str] = []
    for value in candidate.get("retrieval_paths") or []:
        path = _path_value(value)
        if path is not None and path not in paths:
            paths.append(path)

    if not paths:
        if (
            candidate.get("semantic_rank") is not None
            or candidate.get("semantic_score") is not None
            or candidate.get("qdrant_score") is not None
        ):
            paths.append(RetrievalPath.SEMANTIC.value)
        if candidate.get("keyword_rank") is not None or candidate.get("keyword_score") is not None:
            paths.append(RetrievalPath.KEYWORD.value)

    return paths


def _best_score(current: Any, incoming: Any) -> float | None:
    current_score = _normalize_float(current)
    incoming_score = _normalize_float(incoming)
    if incoming_score is None:
        return current_score
    if current_score is None or incoming_score > current_score:
        return incoming_score
    return current_score


def _best_rank(current: Any, incoming: Any) -> int | None:
    current_rank = _normalize_int(current)
    incoming_rank = _normalize_int(incoming)
    if incoming_rank is None:
        return current_rank
    if current_rank is None or incoming_rank < current_rank:
        return incoming_rank
    return current_rank


def _append_unique(values: list[str], incoming: Sequence[Any]) -> None:
    for item in incoming:
        text = _normalize_text(item)
        if text is not None and text not in values:
            values.append(text)


def _merge_metadata(target: dict[str, Any], incoming: Mapping[str, Any]) -> None:
    for key, value in incoming.items():
        if key in {
            "fusion_score",
            "retrieval_paths",
            "subquery_ids",
            "semantic_rank",
            "semantic_score",
            "qdrant_score",
            "keyword_rank",
            "keyword_score",
        }:
            continue
        if target.get(key) is None and value is not None:
            target[key] = value


def _contribution_rank(
    candidate: Mapping[str, Any],
    path: str,
    fallback_rank: int,
) -> int:
    if path == RetrievalPath.KEYWORD.value:
        return _normalize_int(candidate.get("keyword_rank")) or fallback_rank
    return _normalize_int(candidate.get("semantic_rank")) or fallback_rank


def fuse_candidates(
    candidate_groups: Sequence[Sequence[Mapping[str, Any]]],
    *,
    settings: Settings | None = None,
) -> list[dict[str, Any]]:
    """Fuse retrieval candidates by chunk id using deterministic RRF ordering."""

    resolved_settings = _resolve_settings(settings)
    fused_by_chunk: dict[str, dict[str, Any]] = {}

    for group in candidate_groups:
        for fallback_rank, candidate in enumerate(group, start=1):
            chunk_id = _normalize_text(candidate.get("chunk_id") or candidate.get("id"))
            if chunk_id is None:
                continue

            merged = fused_by_chunk.get(chunk_id)
            if merged is None:
                merged = dict(candidate)
                merged["chunk_id"] = chunk_id
                merged.setdefault("id", chunk_id)
                merged["retrieval_paths"] = []
                merged["subquery_ids"] = []
                merged["fusion_score"] = 0.0
                merged["_best_rank"] = None
                fused_by_chunk[chunk_id] = merged
            else:
                _merge_metadata(merged, candidate)

            paths = _candidate_paths(candidate)
            for path in paths:
                if path not in merged["retrieval_paths"]:
                    merged["retrieval_paths"].append(path)
                rank = _contribution_rank(candidate, path, fallback_rank)
                merged["fusion_score"] += 1 / (
                    resolved_settings.RETRIEVAL_RRF_CONSTANT + rank
                )
                merged["_best_rank"] = _best_rank(merged.get("_best_rank"), rank)

            _append_unique(merged["subquery_ids"], candidate.get("subquery_ids") or [])

            merged["semantic_rank"] = _best_rank(
                merged.get("semantic_rank"), candidate.get("semantic_rank")
            )
            merged["keyword_rank"] = _best_rank(
                merged.get("keyword_rank"), candidate.get("keyword_rank")
            )
            merged["semantic_score"] = _best_score(
                merged.get("semantic_score"), candidate.get("semantic_score")
            )
            merged["qdrant_score"] = _best_score(
                merged.get("qdrant_score"), candidate.get("qdrant_score")
            )
            merged["keyword_score"] = _best_score(
                merged.get("keyword_score"), candidate.get("keyword_score")
            )

    ordered = sorted(
        fused_by_chunk.values(),
        key=lambda candidate: (
            -(_normalize_float(candidate.get("fusion_score")) or 0.0),
            _normalize_int(candidate.get("_best_rank")) or 1_000_000,
            str(candidate.get("chunk_id") or ""),
        ),
    )

    results: list[dict[str, Any]] = []
    for candidate in ordered[: resolved_settings.RETRIEVAL_FUSION_TOP_K]:
        cleaned = dict(candidate)
        cleaned.pop("_best_rank", None)
        results.append(cleaned)
    return results


def _path_suffix(path_key: str) -> str:
    return path_key.split(":", 1)[-1] if ":" in path_key else path_key


def _is_semantic_path(path_key: str) -> bool:
    return _path_suffix(path_key) == RetrievalPath.SEMANTIC.value


def _is_keyword_path(path_key: str) -> bool:
    return _path_suffix(path_key) == RetrievalPath.KEYWORD.value


def _fused_by_chunk_id(
    fused_candidates: Sequence[Mapping[str, Any]],
) -> dict[str, dict[str, Any]]:
    mapping: dict[str, dict[str, Any]] = {}
    for candidate in fused_candidates:
        chunk_id = _normalize_text(
            candidate.get("chunk_id") or candidate.get("id")
        )
        if chunk_id is not None:
            mapping[chunk_id] = dict(candidate)
    return mapping


def select_rerank_candidates(
    path_candidates: Mapping[str, Sequence[Mapping[str, Any]]],
    fused_candidates: Sequence[Mapping[str, Any]],
    *,
    settings: Settings | None = None,
) -> list[dict[str, Any]]:
    """Build a diverse rerank candidate pool from path-specific and fused candidates.

    The pool is constructed from three sources:
    1. Top fused candidates in RRF order (configurable via RETRIEVAL_RERANK_FUSED_TOP_K)
    2. Top semantic candidates from each semantic path (configurable via RETRIEVAL_RERANK_SEMANTIC_PER_PATH_TOP_K)
    3. Top keyword candidates from each keyword path (configurable via RETRIEVAL_RERANK_KEYWORD_PER_PATH_TOP_K)

    Deduplication is by chunk ID. When a candidate is present in both a path and the fused
    representation, the fused representation (with merged metadata) is preferred. The total
    pool is capped at RETRIEVAL_RERANK_CANDIDATE_TOP_K.
    """
    resolved_settings = _resolve_settings(settings)

    # Build fused representation lookup
    fused_map = _fused_by_chunk_id(fused_candidates)

    ordered: list[dict[str, Any]] = []
    seen: set[str] = set()

    # 1. Take top fused candidates in RRF order
    for candidate in fused_candidates[
        : resolved_settings.RETRIEVAL_RERANK_FUSED_TOP_K
    ]:
        chunk_id = _normalize_text(
            candidate.get("chunk_id") or candidate.get("id")
        )
        if chunk_id is not None and chunk_id not in seen:
            ordered.append(dict(candidate))
            seen.add(chunk_id)

    # 2. Take top semantic candidates from each semantic path
    for path_key, candidates in path_candidates.items():
        if not _is_semantic_path(path_key) or not candidates:
            continue
        for candidate in candidates[: resolved_settings.RETRIEVAL_RERANK_SEMANTIC_PER_PATH_TOP_K]:
            chunk_id = _normalize_text(
                candidate.get("chunk_id") or candidate.get("id")
            )
            if chunk_id is None or chunk_id in seen:
                continue
            # Prefer fused representation when available
            if chunk_id in fused_map:
                ordered.append(dict(fused_map[chunk_id]))
            else:
                ordered.append(dict(candidate))
            seen.add(chunk_id)

    # 3. Take top keyword candidates from each keyword path
    for path_key, candidates in path_candidates.items():
        if not _is_keyword_path(path_key) or not candidates:
            continue
        for candidate in candidates[: resolved_settings.RETRIEVAL_RERANK_KEYWORD_PER_PATH_TOP_K]:
            chunk_id = _normalize_text(
                candidate.get("chunk_id") or candidate.get("id")
            )
            if chunk_id is None or chunk_id in seen:
                continue
            if chunk_id in fused_map:
                ordered.append(dict(fused_map[chunk_id]))
            else:
                ordered.append(dict(candidate))
            seen.add(chunk_id)

    # 4. Keep the current pool to calculate the no-growth budget
    legacy_pool = ordered[: resolved_settings.RETRIEVAL_RERANK_CANDIDATE_TOP_K]
    pool_budget = len(legacy_pool)

    # 5. Build a deduplicated universe: legacy pool first, then all fused
    universe: list[dict[str, Any]] = []
    universe_seen: set[str] = set()
    for candidate in [*legacy_pool, *fused_candidates]:
        chunk_id = _normalize_text(candidate.get("chunk_id") or candidate.get("id"))
        if chunk_id is None or chunk_id in universe_seen:
            continue
        universe.append(dict(candidate))
        universe_seen.add(chunk_id)

    # 6. Assign evidence groups and select diverse candidates
    from app.services import retrieval_diversity

    grouped = retrieval_diversity.assign_evidence_groups(
        universe,
        settings=resolved_settings,
    )
    return retrieval_diversity.select_group_diverse(grouped, limit=pool_budget)
