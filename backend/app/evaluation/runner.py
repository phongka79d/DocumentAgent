from __future__ import annotations

import json
import time
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import UUID

from app.core.config import Settings
from app.evaluation.dataset import EvaluationCase
from app.evaluation.metrics import calculate_metrics
from app.services import documents as document_service


DEFAULT_RESULTS_DIRECTORY = Path(__file__).resolve().parents[2] / "evaluation" / "results"


class EvaluationRunnerError(RuntimeError):
    """Raised when the live evaluation corpus cannot be resolved safely."""


def _json_value(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return _json_value(value.model_dump(mode="json"))
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _mapping_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return []
    return [
        _json_value(item)
        for item in value
        if isinstance(item, Mapping) or hasattr(item, "model_dump")
    ]


def resolve_document_ids(
    cases: Sequence[EvaluationCase],
    *,
    settings: Settings | None = None,
    document_lister: Callable[..., Sequence[Any]] = document_service.list_documents,
) -> dict[str, str]:
    required_titles = {title for case in cases for title in case.document_titles}
    if not required_titles:
        return {}
    documents = document_lister(settings=settings)
    ready_by_title = {
        document.title: str(document.id)
        for document in documents
        if document.title in required_titles and str(document.status) in {"ready", "DocumentStatus.READY"}
    }
    missing = sorted(required_titles - set(ready_by_title))
    if missing:
        raise EvaluationRunnerError(
            "Seeded ready documents are missing for titles: " + ", ".join(missing)
        )
    return ready_by_title


def run_evaluation(
    cases: Sequence[EvaluationCase],
    *,
    document_ids_by_title: Mapping[str, str],
    graph: Any | None = None,
    settings: Settings | None = None,
    k: int = 5,
    clock: Callable[[], float] = time.perf_counter,
) -> dict[str, Any]:
    if graph is None:
        from app.graphs.query_graph import build_query_graph

        query_graph = build_query_graph(settings=settings)
    else:
        query_graph = graph
    outcomes: list[dict[str, Any]] = []
    for case in cases:
        missing_titles = [
            title for title in case.document_titles if title not in document_ids_by_title
        ]
        if missing_titles:
            raise EvaluationRunnerError(
                f"Case {case.case_id} has unresolved titles: " + ", ".join(missing_titles)
            )
        payload = {
            "question": case.question,
            "document_ids": [document_ids_by_title[title] for title in case.document_titles],
            "save_message": False,
            "filters": case.filters.model_dump(mode="json", exclude_none=True),
        }
        started = clock()
        try:
            state = query_graph.invoke(payload)
        except Exception:
            state = {"error_message": "query workflow invocation failed"}
        latency_ms = (clock() - started) * 1000.0
        citation_validation = _json_value(
            state.get("citation_validation_result") or {}
        )
        grounding = _json_value(state.get("grounding_result") or {})
        outcome = {
            "case_id": case.case_id,
            "question": case.question,
            "document_titles": list(case.document_titles),
            "document_ids": list(payload["document_ids"]),
            "expected_no_result": case.expected_no_result,
            "expected_chunk_contains": list(case.expected_chunk_contains),
            "required_answer_terms": list(case.required_answer_terms),
            "forbidden_answer_terms": list(case.forbidden_answer_terms),
            "pre_rerank": _mapping_list(state.get("retrieved_chunks")),
            "post_rerank": _mapping_list(state.get("reranked_chunks")),
            "context": _mapping_list(state.get("context_chunks")),
            "answer": str(state.get("answer") or ""),
            "sources": _mapping_list(state.get("sources")),
            "citation_validation": citation_validation,
            "grounding": grounding,
            "grounding_passed": bool(state.get("answer_verified")),
            "route": _json_value(state.get("route")),
            "latency_ms": latency_ms,
            "error": state.get("error_message"),
        }
        outcomes.append(outcome)
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "k": k,
        "case_count": len(outcomes),
        "metrics": calculate_metrics(outcomes, k=k),
        "cases": outcomes,
    }


def write_report(
    report: Mapping[str, Any], *, output: str | Path | None = None
) -> Path:
    target = Path(output) if output is not None else DEFAULT_RESULTS_DIRECTORY
    if target.suffix.lower() != ".json":
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ")
        target = target / f"rag-evaluation-{timestamp}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(_json_value(report), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return target


__all__ = [
    "DEFAULT_RESULTS_DIRECTORY",
    "EvaluationRunnerError",
    "resolve_document_ids",
    "run_evaluation",
    "write_report",
]
