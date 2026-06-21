from enum import StrEnum


class TableName(StrEnum):
    DOCUMENTS = "documents"
    DOCUMENT_CHUNKS = "document_chunks"
    MESSAGES = "messages"
    DOCUMENT_SUMMARIES = "document_summaries"
    DOCUMENT_RELATIONS = "document_relations"
    WORKFLOW_RUNS = "workflow_runs"


class DocumentStatus(StrEnum):
    UPLOADED = "uploaded"
    FAILED = "failed"
    PROCESSING = "processing"
    READY = "ready"


class ChunkingStrategy(StrEnum):
    FIXED_TOKEN = "fixed_token"
    SMART_SECTION = "smart_section"


class ChunkingVersion(StrEnum):
    FIXED_TOKEN = "v1"
    SMART_SECTION = "v2"


class ContextMode(StrEnum):
    NEIGHBOR = "neighbor"
    SECTION_AWARE = "section_aware"


class RetrievalBoundary(StrEnum):
    BEGINNING = "beginning"
    END = "end"


class RetrievalStrategy(StrEnum):
    SEMANTIC = "semantic"
    KEYWORD = "keyword"
    HYBRID = "hybrid"
    METADATA = "metadata"
    RELATION = "relation"


class RetrievalPath(StrEnum):
    SEMANTIC = "semantic"
    KEYWORD = "keyword"
    RELATION = "relation"


class SummaryType(StrEnum):
    SECTION = "section"
    DOCUMENT = "document"


class RelationType(StrEnum):
    SAME_TOPIC = "same_topic"
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    REFERENCES = "references"


class WorkflowStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ChunkField(StrEnum):
    ID = "id"
    DOCUMENT_ID = "document_id"
    CHUNK_INDEX = "chunk_index"
    CONTENT = "content"
    CONTENT_HASH = "content_hash"
    TOKEN_COUNT = "token_count"
    CHUNK_TYPE = "chunk_type"
    HEADING = "heading"
    SECTION_PATH = "section_path"
    PAGE_START = "page_start"
    PAGE_END = "page_end"
    TOKEN_START = "token_start"
    TOKEN_END = "token_end"
    QDRANT_POINT_ID = "qdrant_point_id"
    METADATA = "metadata"
    CREATED_AT = "created_at"


class QdrantPayloadKey(StrEnum):
    ID = "id"
    CHUNK_ID = "chunk_id"
    DOCUMENT_ID = "document_id"
    FILE_NAME = "file_name"
    MIME_TYPE = "mime_type"
    CHUNK_INDEX = "chunk_index"
    CONTENT = "content"
    TEXT = "text"
    HEADING = "heading"
    SECTION_PATH = "section_path"
    PAGE_START = "page_start"
    PAGE_END = "page_end"
    CHUNK_TYPE = "chunk_type"
    TOKEN_COUNT = "token_count"


class MessageField(StrEnum):
    QUESTION = "question"
    ANSWER = "answer"
    SOURCES = "sources"
    METADATA = "metadata"


SOURCE_PREVIEW_CHARS = 240
