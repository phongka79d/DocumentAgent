from __future__ import annotations

from typing import Any, TypedDict

from app.models.schemas import DocumentStatus


class IngestionState(TypedDict, total=False):
    document_id: str

    document_record: dict[str, Any]
    storage_path: str
    file_name: str
    mime_type: str | None
    file_size: int | None
    file_hash: str | None

    parsed_document: dict[str, Any]
    total_pages: int | None
    parser_name: str | None
    parser_version: str | None

    chunks: list[dict[str, Any]]
    total_chunks: int | None
    chunking_strategy: str | None
    chunking_version: str | None

    embeddings: list[list[float]]
    embedding_model: str | None
    embedding_dimension: int | None
    qdrant_collection: str | None

    summary_records: list[dict[str, Any]]
    relation_update_result: dict[str, Any]
    trace_id: str
    workflow_trace: list[dict[str, Any]]
    retry_attempts: dict[str, int]

    status: DocumentStatus
    error_message: str | None
