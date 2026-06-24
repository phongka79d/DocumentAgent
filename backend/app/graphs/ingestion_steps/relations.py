from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.core.config import Settings, get_settings
from app.core.contracts import DocumentStatus
from app.core.errors import safe_detail
from app.core.retry import RetryAttempt, RetryExhaustedError, retry_sync
from app.graphs import ingestion_inputs
from app.graphs.ingestion_state import IngestionState
from app.graphs.ingestion_steps.dependencies import IngestionStepDependencies

DEFAULT_INGESTION_ERROR = "Ingestion failed"


def _resolve_settings(settings: Settings | None = None) -> Settings:
    return settings if settings is not None else get_settings()


def _resolve_document_id(state: Mapping[str, Any]) -> str | None:
    return ingestion_inputs.resolve_document_id(state)


def _failure_state(
    document_id: str | None,
    error_message: str | None,
    *,
    fallback: str = DEFAULT_INGESTION_ERROR,
    error_code: str | None = None,
    retry_attempts: dict[str, int] | None = None,
) -> dict[str, Any]:
    message = safe_detail(error_message, fallback=fallback)
    result: dict[str, Any] = {
        "status": DocumentStatus.FAILED,
        "error_message": message,
        "error_code": error_code or "ingestion_failed",
    }
    if document_id is not None:
        result["document_id"] = document_id
    if retry_attempts:
        result["retry_attempts"] = retry_attempts
    return result


def _attempt_count(attempts: list[RetryAttempt]) -> int:
    if not attempts:
        return 1
    return max(attempt.attempt for attempt in attempts)


def _retry_attempts_for(
    node_name: str,
    attempts: list[RetryAttempt],
) -> dict[str, int]:
    attempt_count = _attempt_count(attempts)
    return {node_name: attempt_count} if attempt_count > 1 else {}


def _with_retry_attempts(
    result: dict[str, Any],
    node_name: str,
    attempts: list[RetryAttempt],
) -> dict[str, Any]:
    retry_attempts = _retry_attempts_for(node_name, attempts)
    if retry_attempts:
        return {**result, "retry_attempts": retry_attempts}
    return result


def update_document_relations_node(
    state: IngestionState,
    *,
    settings: Settings | None = None,
    deps: IngestionStepDependencies,
) -> dict[str, Any]:
    resolved_settings = _resolve_settings(settings)
    document_id = _resolve_document_id(state)
    if document_id is None:
        return _failure_state(None, "document_id is required")

    if not resolved_settings.ENABLE_RELATION_RETRIEVAL:
        return {
            "relation_update_result": {
                "status": "skipped",
                "reason": "relation retrieval disabled",
            }
        }

    summary_records = state.get("summary_records") or []
    document_summary = next(
        (
            record
            for record in summary_records
            if isinstance(record, Mapping) and record.get("summary_type") == "document"
        ),
        None,
    )
    if document_summary is None or not str(document_summary.get("content") or "").strip():
        return {
            "relation_update_result": {
                "status": "skipped",
                "reason": "document summary missing",
            }
        }

    try:
        attempts: list[RetryAttempt] = []
        result = retry_sync(
            "relation_update",
            lambda: deps.relations.update_document_relations(
                document_id,
                summary_records=summary_records,
                settings=resolved_settings,
            ),
            settings=resolved_settings,
            on_attempt=attempts.append,
        )
        return _with_retry_attempts(
            {"relation_update_result": result},
            "update_document_relations",
            attempts,
        )
    except RetryExhaustedError as exc:
        return {
            "relation_update_result": {
                "status": "warning",
                "warning": "Relation update failed after retry exhaustion",
                "error_code": "relation_update_retry_exhausted",
                "attempts": exc.attempts,
            },
            "retry_attempts": {"update_document_relations": exc.attempts},
        }
    except Exception as exc:
        return {
            "relation_update_result": {
                "status": "warning",
                "warning": safe_detail(
                    f"Relation update failed: {exc}",
                    fallback="Relation update failed",
                ),
            }
        }
