from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.core.config import Settings, get_settings
from app.core.contracts import DocumentStatus
from app.core.errors import safe_detail
from app.graphs import ingestion_inputs, ingestion_payloads
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
) -> dict[str, Any]:
    message = safe_detail(error_message, fallback=fallback)
    result: dict[str, Any] = {
        "status": DocumentStatus.FAILED,
        "error_message": message,
        "error_code": error_code or "ingestion_failed",
    }
    if document_id is not None:
        result["document_id"] = document_id
    return result


def chunk_document_node(
    state: IngestionState,
    *,
    settings: Settings | None = None,
    deps: IngestionStepDependencies,
) -> dict[str, Any]:
    resolved_settings = _resolve_settings(settings)
    document_id = _resolve_document_id(state)
    if document_id is None:
        return _failure_state(None, "document_id is required")

    parsed_document = state.get("parsed_document")
    if not isinstance(parsed_document, Mapping):
        return _failure_state(document_id, "parsed_document is required")

    try:
        chunker, chunking_strategy, chunking_version = (
            ingestion_payloads.resolve_chunker_for_settings(resolved_settings)
        )
        chunks = chunker.chunk(dict(parsed_document))
        if not chunks:
            return _failure_state(document_id, "Chunking produced no chunks")
        return {
            "chunks": [dict(chunk) for chunk in chunks],
            "total_chunks": len(chunks),
            "chunking_strategy": chunking_strategy,
            "chunking_version": chunking_version,
        }
    except ValueError as exc:
        return _failure_state(document_id, str(exc))
    except Exception as exc:  # pragma: no cover
        return _failure_state(document_id, str(exc))
