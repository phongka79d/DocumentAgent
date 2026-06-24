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
from app.services import summaries

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


def _retry_exhausted_failure(
    document_id: str | None,
    node_name: str,
    exc: RetryExhaustedError,
) -> dict[str, Any]:
    operation = "".join(
        character.lower() if character.isalnum() else "_"
        for character in exc.operation
    ).strip("_")
    error_code = f"{operation or node_name}_retry_exhausted"
    return _failure_state(
        document_id,
        str(exc),
        error_code=error_code,
        retry_attempts={node_name: exc.attempts},
    )


def summarize_document_node(
    state: IngestionState,
    *,
    settings: Settings | None = None,
    deps: IngestionStepDependencies,
) -> dict[str, Any]:
    resolved_settings = _resolve_settings(settings)
    document_id = _resolve_document_id(state)
    if document_id is None:
        return _failure_state(None, "document_id is required")

    if not resolved_settings.ENABLE_SUMMARIES:
        return {"summary_records": []}

    chunks = state.get("chunks") or []
    if not isinstance(chunks, list) or not chunks:
        return _failure_state(document_id, "chunks are required before summarization")

    attempts: list[RetryAttempt] = []
    try:
        result = retry_sync(
            "summary_generation",
            lambda: summaries.generate_document_summaries(
                document_id,
                chunks,
                settings=resolved_settings,
            ),
            settings=resolved_settings,
            on_attempt=attempts.append,
        )
    except RetryExhaustedError as exc:
        return _retry_exhausted_failure(document_id, "summarize_document", exc)
    if isinstance(result, Mapping) and result.get("status") == DocumentStatus.FAILED:
        return _failure_state(document_id, str(result.get("error_message")))
    if not isinstance(result, list):
        return _failure_state(document_id, "Summary generation returned invalid state")
    return _with_retry_attempts(
        {"summary_records": result},
        "summarize_document",
        attempts,
    )
