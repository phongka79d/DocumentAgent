from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_serializer,
    model_validator,
)

from app.core.contracts import (
    RelationType,
    RetrievalPath,
    RetrievalStrategy,
    SummaryType,
    WorkflowStatus,
)


DocumentStatus = Literal["uploaded", "processing", "ready", "failed"]


class APIModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        from_attributes=True,
        str_strip_whitespace=True,
    )


class RetrievalFilters(APIModel):
    mime_types: list[str] = Field(default_factory=list)
    heading: str | None = None
    section_path: list[str] = Field(default_factory=list)
    page_start: int | None = Field(default=None, ge=0)
    page_end: int | None = Field(default=None, ge=0)

    @field_validator("mime_types", "section_path", mode="before")
    @classmethod
    def normalize_string_list(cls, value: Any) -> Any:
        if value is None:
            return []
        if not isinstance(value, (list, tuple, set)):
            return value
        normalized: list[Any] = []
        for item in value:
            if isinstance(item, str):
                item = item.strip()
                if not item or item in normalized:
                    continue
            normalized.append(item)
        return normalized

    @field_validator("heading", mode="before")
    @classmethod
    def normalize_heading(cls, value: Any) -> Any:
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value

    @model_validator(mode="after")
    def validate_page_range(self) -> RetrievalFilters:
        if (
            self.page_start is not None
            and self.page_end is not None
            and self.page_start > self.page_end
        ):
            raise ValueError("page_start must be less than or equal to page_end")
        return self


class QuerySubquery(APIModel):
    id: str = Field(min_length=1)
    text: str = Field(min_length=1)


class QueryPlan(APIModel):
    is_complex: bool
    strategy: RetrievalStrategy
    subqueries: list[QuerySubquery] = Field(min_length=1)
    inferred_filters: RetrievalFilters = Field(default_factory=RetrievalFilters)
    needs_relations: bool = False


class RetrievalCandidate(APIModel):
    chunk_id: str = Field(min_length=1)
    document_id: str = Field(min_length=1)
    file_name: str = Field(min_length=1)
    chunk_index: int = Field(ge=0)
    content: str = Field(min_length=1)
    heading: str | None = None
    section_path: list[str] = Field(default_factory=list)
    page_start: int | None = Field(default=None, ge=0)
    page_end: int | None = Field(default=None, ge=0)
    chunk_type: str | None = None
    token_count: int | None = Field(default=None, ge=0)
    qdrant_score: float | None = None
    rerank_score: float | None = None
    semantic_rank: int | None = Field(default=None, ge=1)
    semantic_score: float | None = None
    keyword_rank: int | None = Field(default=None, ge=1)
    keyword_score: float | None = None
    fusion_score: float | None = None
    retrieval_paths: list[RetrievalPath] = Field(default_factory=list)
    subquery_ids: list[str] = Field(default_factory=list)


class GroundingResult(APIModel):
    grounded: bool
    score: float = Field(ge=0.0, le=1.0)
    unsupported_claims: list[str] = Field(default_factory=list)
    missing_citations: list[str] = Field(default_factory=list)


class CitationValidationResult(APIModel):
    valid: bool
    cited_keys: list[str] = Field(default_factory=list)
    cited_chunk_ids: list[str] = Field(default_factory=list)
    invalid_keys: list[str] = Field(default_factory=list)
    missing_citations: bool = False


class WorkflowTraceEvent(APIModel):
    node_name: str = Field(min_length=1)
    status: WorkflowStatus
    attempt: int = Field(default=1, ge=1)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_ms: int | None = Field(default=None, ge=0)
    provider: str | None = None
    input_count: int | None = Field(default=None, ge=0)
    output_count: int | None = Field(default=None, ge=0)
    route: str | None = None
    fallback: str | None = None
    error_code: str | None = None


class DocumentResponse(APIModel):
    id: UUID
    title: str | None = None
    file_name: str = Field(min_length=1)
    mime_type: str | None = None
    file_size: int | None = None
    file_hash: str | None = None
    storage_path: str = Field(min_length=1)
    status: DocumentStatus
    total_pages: int | None = None
    total_chunks: int = 0
    parser_name: str | None = None
    parser_version: str | None = None
    chunking_strategy: str | None = None
    chunking_version: str | None = None
    embedding_model: str | None = None
    embedding_dimension: int | None = None
    qdrant_collection: str | None = None
    indexed_at: datetime | None = None
    error_message: str | None = None
    error_code: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class DocumentListResponse(APIModel):
    documents: list[DocumentResponse] = Field(default_factory=list)


class DocumentChunkResponse(APIModel):
    id: str = Field(min_length=1)
    document_id: str = Field(min_length=1)
    chunk_index: int
    content: str = Field(min_length=1)
    content_hash: str | None = None
    token_count: int | None = None
    chunk_type: str | None = None
    heading: str | None = None
    section_path: list[str] = Field(default_factory=list)
    page_start: int | None = None
    page_end: int | None = None
    token_start: int | None = None
    token_end: int | None = None
    qdrant_point_id: str | None = None
    metadata: dict[str, Any] | None = None
    created_at: datetime | None = None


class DocumentChunkListResponse(APIModel):
    document_id: str = Field(min_length=1)
    chunks: list[DocumentChunkResponse] = Field(default_factory=list)


class DocumentSummaryResponse(APIModel):
    id: str | None = None
    document_id: str = Field(min_length=1)
    summary_type: SummaryType
    heading: str | None = None
    section_path: list[str] = Field(default_factory=list)
    content: str = Field(min_length=1)
    source_chunk_ids: list[str] = Field(default_factory=list)
    model: str = Field(min_length=1)
    created_at: datetime | None = None
    updated_at: datetime | None = None


class DocumentSummaryListResponse(APIModel):
    document_id: str = Field(min_length=1)
    summaries: list[DocumentSummaryResponse] = Field(default_factory=list)


class DocumentRelationResponse(APIModel):
    id: str | None = None
    source_document_id: str = Field(min_length=1)
    target_document_id: str = Field(min_length=1)
    related_document_id: str = Field(min_length=1)
    relation_type: RelationType
    description: str = Field(min_length=1)
    evidence_chunk_ids: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    model: str = Field(min_length=1)
    created_at: datetime | None = None
    updated_at: datetime | None = None


class DocumentRelationListResponse(APIModel):
    document_id: str = Field(min_length=1)
    relations: list[DocumentRelationResponse] = Field(default_factory=list)


class UploadDocumentResponse(APIModel):
    document_id: UUID
    status: DocumentStatus
    duplicate: bool


class SourceCitation(APIModel):
    document_id: UUID
    chunk_id: UUID
    file_name: str = Field(min_length=1)
    chunk_index: int
    page_start: int | None = None
    page_end: int | None = None
    heading: str | None = None
    qdrant_score: float | None = None
    rerank_score: float | None = None
    section_path: list[str] = Field(default_factory=list)
    content_preview: str = ""
    is_neighbor_context: bool = False
    fusion_score: float | None = None
    retrieval_paths: list[RetrievalPath] | None = None
    citation_key: str | None = None

    @model_serializer(mode="wrap")
    def serialize_optional_phase3_fields(self, handler: Any) -> dict[str, Any]:
        data = handler(self)
        for field_name in ("fusion_score", "retrieval_paths", "citation_key"):
            if data.get(field_name) is None:
                data.pop(field_name, None)
        return data


class ChatRequest(APIModel):
    question: str = Field(min_length=1)
    document_ids: list[UUID] = Field(default_factory=list)
    save_message: bool = False
    filters: RetrievalFilters | None = None


class ChatResponse(APIModel):
    answer: str = Field(min_length=1)
    sources: list[SourceCitation] = Field(default_factory=list)
    trace_id: UUID | None = None

    @model_serializer(mode="wrap")
    def serialize_optional_trace_id(self, handler: Any) -> dict[str, Any]:
        data = handler(self)
        if data.get("trace_id") is None:
            data.pop("trace_id", None)
        return data


class MessageResponse(APIModel):
    id: UUID
    question: str = Field(min_length=1)
    answer: str = Field(min_length=1)
    sources: list[SourceCitation] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None


class MessageListResponse(APIModel):
    messages: list[MessageResponse] = Field(default_factory=list)
