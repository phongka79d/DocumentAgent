from __future__ import annotations

from app.core.config import Settings
from app.core.contracts import (
    ChunkField,
    ChunkingStrategy,
    ChunkingVersion,
    DocumentStatus,
    QdrantPayloadKey,
)
from app.graphs import ingestion_payloads


def _settings(*, chunking_strategy: str = ChunkingStrategy.FIXED_TOKEN) -> Settings:
    return Settings(
        SUPABASE_URL="https://example.supabase.co",
        SUPABASE_ANON_KEY="anon",
        SHOPAIKEY_API_KEY="shop",
        JINA_API_KEY="jina",
        CHUNKING_STRATEGY=chunking_strategy,
    )


def _chunk() -> dict[str, object]:
    return {
        ChunkField.ID: "chunk-1",
        ChunkField.CHUNK_INDEX: 3,
        ChunkField.CONTENT: "chunk content",
        ChunkField.CONTENT_HASH: "hash-1",
        ChunkField.TOKEN_COUNT: 2,
        ChunkField.CHUNK_TYPE: ChunkingStrategy.SMART_SECTION,
        ChunkField.HEADING: "Overview",
        ChunkField.SECTION_PATH: ["Root", "Overview"],
        ChunkField.PAGE_START: 1,
        ChunkField.PAGE_END: 2,
        ChunkField.TOKEN_START: 10,
        ChunkField.TOKEN_END: 12,
    }


def test_document_chunk_insert_payload_uses_chunk_field_contracts():
    payload = ingestion_payloads.document_chunk_insert_payload(
        "doc-1",
        chunk=_chunk(),
        metadata={"parser_name": "pdf"},
    )

    assert payload == {
        ChunkField.DOCUMENT_ID: "doc-1",
        ChunkField.CHUNK_INDEX: 3,
        ChunkField.CONTENT: "chunk content",
        ChunkField.CONTENT_HASH: "hash-1",
        ChunkField.TOKEN_COUNT: 2,
        ChunkField.CHUNK_TYPE: ChunkingStrategy.SMART_SECTION,
        ChunkField.HEADING: "Overview",
        ChunkField.SECTION_PATH: ["Root", "Overview"],
        ChunkField.PAGE_START: 1,
        ChunkField.PAGE_END: 2,
        ChunkField.TOKEN_START: 10,
        ChunkField.TOKEN_END: 12,
        ChunkField.METADATA: {"parser_name": "pdf"},
    }


def test_qdrant_payload_uses_payload_key_contracts():
    payload = ingestion_payloads.qdrant_payload(
        "doc-1",
        chunk=_chunk(),
        file_name="report.pdf",
    )

    assert payload == {
        QdrantPayloadKey.DOCUMENT_ID: "doc-1",
        QdrantPayloadKey.CHUNK_ID: "chunk-1",
        QdrantPayloadKey.CHUNK_INDEX: 3,
        QdrantPayloadKey.FILE_NAME: "report.pdf",
        QdrantPayloadKey.HEADING: "Overview",
        QdrantPayloadKey.SECTION_PATH: ["Root", "Overview"],
        QdrantPayloadKey.PAGE_START: 1,
        QdrantPayloadKey.PAGE_END: 2,
        QdrantPayloadKey.CHUNK_TYPE: ChunkingStrategy.SMART_SECTION,
        QdrantPayloadKey.TOKEN_COUNT: 2,
        QdrantPayloadKey.TEXT: "chunk content",
    }


def test_build_qdrant_point_uses_payload_and_vector():
    point = ingestion_payloads.build_qdrant_point(
        chunk_id="chunk-1",
        vector=[0.1, 0.2],
        payload={"document_id": "doc-1"},
    )

    assert point.id == "chunk-1"
    assert point.vector == [0.1, 0.2]
    assert point.payload == {"document_id": "doc-1"}


def test_document_status_payloads_use_status_contracts():
    processing = ingestion_payloads.processing_document_payload(now="now")
    ready = ingestion_payloads.ready_document_payload(
        {
            "total_pages": 2,
            "total_chunks": 4,
            "parser_name": "pdf",
            "parser_version": "1",
            "chunking_strategy": ChunkingStrategy.FIXED_TOKEN,
            "chunking_version": ChunkingVersion.FIXED_TOKEN,
            "embedding_model": "embedding-model",
            "embedding_dimension": 3,
        },
        qdrant_collection="collection",
        now="now",
    )
    failed = ingestion_payloads.failed_document_payload("bad", now="now")

    assert processing["status"] == DocumentStatus.PROCESSING
    assert ready["status"] == DocumentStatus.READY
    assert ready["qdrant_collection"] == "collection"
    assert failed["status"] == DocumentStatus.FAILED
    assert failed["error_message"] == "bad"


def test_resolve_chunker_for_settings_returns_contract_values():
    _, strategy, version = ingestion_payloads.resolve_chunker_for_settings(
        _settings(chunking_strategy=ChunkingStrategy.SMART_SECTION)
    )

    assert strategy == ChunkingStrategy.SMART_SECTION
    assert version == ChunkingVersion.SMART_SECTION
