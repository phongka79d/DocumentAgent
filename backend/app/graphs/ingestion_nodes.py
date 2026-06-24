from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.core.config import Settings, get_settings
from app.graphs.ingestion_state import IngestionState
from app.graphs.ingestion_steps.dependencies import IngestionStepDependencies
from app.graphs.ingestion_steps import (
    records as _record_steps,
    parsing as _parsing_steps,
    chunking as _chunking_steps,
    persistence as _persistence_steps,
    summaries as _summaries_steps,
    indexing as _indexing_steps,
    relations as _relations_steps,
    finalization as _finalization_steps,
)

# Compatibility imports for monkeypatching in tests
from app.graphs import ingestion_payloads
from app.services import relations
from app.services import summaries
from app.services.supabase_client import create_supabase_client
from app.services.shopaikey_client import create_shopaikey_client
from app.services.qdrant_client import create_qdrant_client
from app.parsing import get_parser_for_file

DEFAULT_INGESTION_ERROR = "Ingestion failed"


def _resolve_settings(settings: Settings | None = None) -> Settings:
    return settings if settings is not None else get_settings()


def _ingestion_step_dependencies() -> IngestionStepDependencies:
    return IngestionStepDependencies(
        create_supabase_client=create_supabase_client,
        create_shopaikey_client=create_shopaikey_client,
        create_qdrant_client=create_qdrant_client,
        get_parser_for_file=get_parser_for_file,
        relations=relations,
    )


def load_document_record_node(
    state: IngestionState,
    *,
    settings: Settings | None = None,
) -> dict[str, Any]:
    return _record_steps.load_document_record_node(
        state,
        settings=_resolve_settings(settings),
        deps=_ingestion_step_dependencies(),
    )


def mark_processing_node(
    state: IngestionState,
    *,
    settings: Settings | None = None,
) -> dict[str, Any]:
    return _record_steps.mark_processing_node(
        state,
        settings=_resolve_settings(settings),
        deps=_ingestion_step_dependencies(),
    )


def parse_document_node(
    state: IngestionState,
    *,
    settings: Settings | None = None,
) -> dict[str, Any]:
    return _parsing_steps.parse_document_node(
        state,
        settings=_resolve_settings(settings),
        deps=_ingestion_step_dependencies(),
    )


def chunk_document_node(
    state: IngestionState,
    *,
    settings: Settings | None = None,
) -> dict[str, Any]:
    return _chunking_steps.chunk_document_node(
        state,
        settings=_resolve_settings(settings),
        deps=_ingestion_step_dependencies(),
    )


def save_chunks_node(
    state: IngestionState,
    *,
    settings: Settings | None = None,
) -> dict[str, Any]:
    return _persistence_steps.save_chunks_node(
        state,
        settings=_resolve_settings(settings),
        deps=_ingestion_step_dependencies(),
    )


def summarize_document_node(
    state: IngestionState,
    *,
    settings: Settings | None = None,
) -> dict[str, Any]:
    return _summaries_steps.summarize_document_node(
        state,
        settings=_resolve_settings(settings),
        deps=_ingestion_step_dependencies(),
    )


def embed_chunks_node(
    state: IngestionState,
    *,
    settings: Settings | None = None,
) -> dict[str, Any]:
    return _indexing_steps.embed_chunks_node(
        state,
        settings=_resolve_settings(settings),
        deps=_ingestion_step_dependencies(),
    )


def upsert_qdrant_node(
    state: IngestionState,
    *,
    settings: Settings | None = None,
) -> dict[str, Any]:
    return _indexing_steps.upsert_qdrant_node(
        state,
        settings=_resolve_settings(settings),
        deps=_ingestion_step_dependencies(),
    )


def update_document_relations_node(
    state: IngestionState,
    *,
    settings: Settings | None = None,
) -> dict[str, Any]:
    return _relations_steps.update_document_relations_node(
        state,
        settings=_resolve_settings(settings),
        deps=_ingestion_step_dependencies(),
    )


def mark_ready_node(
    state: IngestionState,
    *,
    settings: Settings | None = None,
) -> dict[str, Any]:
    return _finalization_steps.mark_ready_node(
        state,
        settings=_resolve_settings(settings),
        deps=_ingestion_step_dependencies(),
    )


def mark_failed_node(
    state: IngestionState,
    error_message: str | None = None,
    *,
    settings: Settings | None = None,
) -> dict[str, Any]:
    return _finalization_steps.mark_failed_node(
        state,
        error_message=error_message,
        settings=_resolve_settings(settings),
        deps=_ingestion_step_dependencies(),
    )


__all__ = [
    "DEFAULT_INGESTION_ERROR",
    "load_document_record_node",
    "mark_processing_node",
    "parse_document_node",
    "chunk_document_node",
    "save_chunks_node",
    "summarize_document_node",
    "embed_chunks_node",
    "upsert_qdrant_node",
    "update_document_relations_node",
    "mark_ready_node",
    "mark_failed_node",
]
