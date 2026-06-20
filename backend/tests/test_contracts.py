from app.core.contracts import (
    ChunkingStrategy,
    ChunkingVersion,
    ContextMode,
    DocumentStatus,
    QdrantPayloadKey,
    RetrievalBoundary,
    SOURCE_PREVIEW_CHARS,
    TableName,
)


def test_shared_contract_literals_match_database_and_api_values():
    assert TableName.DOCUMENTS == "documents"
    assert TableName.DOCUMENT_CHUNKS == "document_chunks"
    assert TableName.MESSAGES == "messages"

    assert DocumentStatus.FAILED == "failed"
    assert DocumentStatus.PROCESSING == "processing"
    assert DocumentStatus.READY == "ready"
    assert DocumentStatus.UPLOADED == "uploaded"

    assert ChunkingStrategy.FIXED_TOKEN == "fixed_token"
    assert ChunkingStrategy.SMART_SECTION == "smart_section"
    assert ChunkingVersion.FIXED_TOKEN == "v1"
    assert ChunkingVersion.SMART_SECTION == "v2"

    assert ContextMode.NEIGHBOR == "neighbor"
    assert ContextMode.SECTION_AWARE == "section_aware"
    assert RetrievalBoundary.BEGINNING == "beginning"
    assert RetrievalBoundary.END == "end"

    assert QdrantPayloadKey.ID == "id"
    assert QdrantPayloadKey.CHUNK_ID == "chunk_id"
    assert QdrantPayloadKey.DOCUMENT_ID == "document_id"
    assert QdrantPayloadKey.FILE_NAME == "file_name"
    assert QdrantPayloadKey.CHUNK_INDEX == "chunk_index"
    assert QdrantPayloadKey.CONTENT == "content"
    assert QdrantPayloadKey.TEXT == "text"
    assert QdrantPayloadKey.HEADING == "heading"
    assert QdrantPayloadKey.SECTION_PATH == "section_path"
    assert QdrantPayloadKey.PAGE_START == "page_start"
    assert QdrantPayloadKey.PAGE_END == "page_end"
    assert QdrantPayloadKey.CHUNK_TYPE == "chunk_type"
    assert QdrantPayloadKey.TOKEN_COUNT == "token_count"
    assert SOURCE_PREVIEW_CHARS == 240
