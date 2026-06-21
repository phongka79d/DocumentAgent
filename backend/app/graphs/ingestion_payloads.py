from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from qdrant_client.http import models as qdrant_models

from app.chunking.section_chunker import SmartSectionChunker
from app.chunking.token_chunker import FixedTokenChunker
from app.core.config import Settings
from app.core.contracts import (
    ChunkField,
    ChunkingStrategy,
    ChunkingVersion,
    DocumentStatus,
    QdrantPayloadKey,
)


def chunk_metadata(state: Mapping[str, Any]) -> dict[str, Any]:
    metadata = {
        "parser_name": state.get("parser_name"),
        "parser_version": state.get("parser_version"),
        "chunking_strategy": state.get("chunking_strategy"),
        "chunking_version": state.get("chunking_version"),
    }
    return {key: value for key, value in metadata.items() if value is not None}


def document_chunk_insert_payload(
    document_id: str,
    *,
    chunk: Mapping[str, Any],
    metadata: dict[str, Any],
) -> dict[str, Any]:
    return {
        ChunkField.DOCUMENT_ID: document_id,
        ChunkField.CHUNK_INDEX: chunk.get(ChunkField.CHUNK_INDEX),
        ChunkField.CONTENT: chunk.get(ChunkField.CONTENT),
        ChunkField.CONTENT_HASH: chunk.get(ChunkField.CONTENT_HASH),
        ChunkField.TOKEN_COUNT: chunk.get(ChunkField.TOKEN_COUNT),
        ChunkField.CHUNK_TYPE: chunk.get(ChunkField.CHUNK_TYPE),
        ChunkField.HEADING: chunk.get(ChunkField.HEADING),
        ChunkField.SECTION_PATH: list(chunk.get(ChunkField.SECTION_PATH) or []),
        ChunkField.PAGE_START: chunk.get(ChunkField.PAGE_START),
        ChunkField.PAGE_END: chunk.get(ChunkField.PAGE_END),
        ChunkField.TOKEN_START: chunk.get(ChunkField.TOKEN_START),
        ChunkField.TOKEN_END: chunk.get(ChunkField.TOKEN_END),
        ChunkField.METADATA: metadata or None,
    }


def qdrant_payload(
    document_id: str,
    *,
    chunk: Mapping[str, Any],
    file_name: str,
    mime_type: str | None,
) -> dict[str, Any]:
    return {
        QdrantPayloadKey.DOCUMENT_ID: document_id,
        QdrantPayloadKey.CHUNK_ID: str(
            chunk.get(ChunkField.ID) or chunk.get(ChunkField.QDRANT_POINT_ID) or ""
        ),
        QdrantPayloadKey.CHUNK_INDEX: chunk.get(ChunkField.CHUNK_INDEX),
        QdrantPayloadKey.FILE_NAME: file_name,
        QdrantPayloadKey.MIME_TYPE: mime_type,
        QdrantPayloadKey.HEADING: chunk.get(ChunkField.HEADING),
        QdrantPayloadKey.SECTION_PATH: list(chunk.get(ChunkField.SECTION_PATH) or []),
        QdrantPayloadKey.PAGE_START: chunk.get(ChunkField.PAGE_START),
        QdrantPayloadKey.PAGE_END: chunk.get(ChunkField.PAGE_END),
        QdrantPayloadKey.CHUNK_TYPE: chunk.get(ChunkField.CHUNK_TYPE),
        QdrantPayloadKey.TOKEN_COUNT: chunk.get(ChunkField.TOKEN_COUNT),
        QdrantPayloadKey.TEXT: chunk.get(ChunkField.CONTENT),
    }


def build_qdrant_point(
    *,
    chunk_id: str,
    vector: Sequence[float],
    payload: dict[str, Any],
) -> qdrant_models.PointStruct:
    return qdrant_models.PointStruct(
        id=chunk_id,
        vector=list(vector),
        payload=payload,
    )


def processing_document_payload(*, now: Any) -> dict[str, Any]:
    return {
        "status": DocumentStatus.PROCESSING,
        "error_message": None,
        "updated_at": now,
    }


def ready_document_payload(
    state: Mapping[str, Any],
    *,
    qdrant_collection: str,
    now: Any,
) -> dict[str, Any]:
    return {
        "status": DocumentStatus.READY,
        "total_pages": state.get("total_pages"),
        "total_chunks": state.get("total_chunks"),
        "parser_name": state.get("parser_name"),
        "parser_version": state.get("parser_version"),
        "chunking_strategy": state.get("chunking_strategy"),
        "chunking_version": state.get("chunking_version"),
        "embedding_model": state.get("embedding_model"),
        "embedding_dimension": state.get("embedding_dimension"),
        "qdrant_collection": qdrant_collection,
        "indexed_at": now,
        "error_message": None,
        "updated_at": now,
    }


def failed_document_payload(error_message: str, *, now: Any) -> dict[str, Any]:
    return {
        "status": DocumentStatus.FAILED,
        "error_message": error_message,
        "updated_at": now,
    }


def resolve_chunker_for_settings(
    settings: Settings,
) -> tuple[Any, ChunkingStrategy, ChunkingVersion]:
    strategy = settings.CHUNKING_STRATEGY
    normalized_strategy = strategy.strip().lower() if isinstance(strategy, str) else ""
    if normalized_strategy == ChunkingStrategy.FIXED_TOKEN:
        return (
            FixedTokenChunker(settings=settings),
            ChunkingStrategy.FIXED_TOKEN,
            ChunkingVersion.FIXED_TOKEN,
        )
    if normalized_strategy == ChunkingStrategy.SMART_SECTION:
        return (
            SmartSectionChunker(settings=settings),
            ChunkingStrategy.SMART_SECTION,
            ChunkingVersion.SMART_SECTION,
        )
    raise ValueError(f"Unsupported chunking strategy: {strategy}")
