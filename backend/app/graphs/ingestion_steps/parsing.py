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


def _resolve_file_name(state: Mapping[str, Any]) -> str | None:
    return ingestion_inputs.resolve_file_name(state)


def _resolve_mime_type(state: Mapping[str, Any]) -> str | None:
    return ingestion_inputs.resolve_mime_type(state)


def _resolve_storage_path(state: Mapping[str, Any]) -> str | None:
    return ingestion_inputs.resolve_storage_path(state)


def _normalize_bytes(downloaded: Any) -> bytes:
    return ingestion_inputs.normalize_bytes(downloaded)


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


def parse_document_node(
    state: IngestionState,
    *,
    settings: Settings | None = None,
    deps: IngestionStepDependencies,
) -> dict[str, Any]:
    resolved_settings = _resolve_settings(settings)
    document_id = _resolve_document_id(state)
    if document_id is None:
        return _failure_state(None, "document_id is required")

    storage_path = _resolve_storage_path(state)
    file_name = _resolve_file_name(state)
    mime_type = _resolve_mime_type(state)
    if storage_path is None:
        return _failure_state(document_id, "Document storage_path is required")
    if file_name is None:
        return _failure_state(document_id, "Document file_name is required")

    try:
        client = deps.create_supabase_client(resolved_settings)
        bucket = client.storage.from_(resolved_settings.SUPABASE_STORAGE_BUCKET)
        attempts: list[RetryAttempt] = []
        downloaded = retry_sync(
            "storage_download",
            lambda: bucket.download(storage_path),
            settings=resolved_settings,
            on_attempt=attempts.append,
        )
        file_bytes = _normalize_bytes(downloaded)
        parser = deps.get_parser_for_file(file_name, mime_type=mime_type)
        parsed_document = parser.parse(
            file_bytes,
            file_name=file_name,
            mime_type=mime_type,
        )
        pages = parsed_document.get("pages") or []
        metadata = parsed_document.get("metadata") or {}
        return _with_retry_attempts(
            {
                "parsed_document": parsed_document,
                "total_pages": len(pages),
                "parser_name": metadata.get("parser_name"),
                "parser_version": metadata.get("parser_version"),
            },
            "parse_document",
            attempts,
        )
    except RetryExhaustedError as exc:
        return _retry_exhausted_failure(document_id, "parse_document", exc)
    except Exception as exc:
        return _failure_state(document_id, str(exc))
