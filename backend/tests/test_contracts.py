from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.core.contracts import (
    ChunkField,
    ChunkingStrategy,
    ChunkingVersion,
    ContextMode,
    DocumentStatus,
    MessageField,
    QdrantPayloadKey,
    RelationType,
    RetrievalBoundary,
    RetrievalPath,
    RetrievalStrategy,
    SOURCE_PREVIEW_CHARS,
    SummaryType,
    TableName,
    WorkflowStatus,
)
from app.models.schemas import (
    ChatRequest,
    CitationValidationResult,
    GroundingResult,
    QueryPlan,
    RetrievalCandidate,
    RetrievalFilters,
    WorkflowTraceEvent,
)
from app.services import retrieval


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

    assert ChunkField.ID == "id"
    assert ChunkField.DOCUMENT_ID == "document_id"
    assert ChunkField.CHUNK_INDEX == "chunk_index"
    assert ChunkField.CONTENT == "content"
    assert ChunkField.CONTENT_HASH == "content_hash"
    assert ChunkField.TOKEN_COUNT == "token_count"
    assert ChunkField.CHUNK_TYPE == "chunk_type"
    assert ChunkField.HEADING == "heading"
    assert ChunkField.SECTION_PATH == "section_path"
    assert ChunkField.PAGE_START == "page_start"
    assert ChunkField.PAGE_END == "page_end"
    assert ChunkField.TOKEN_START == "token_start"
    assert ChunkField.TOKEN_END == "token_end"
    assert ChunkField.QDRANT_POINT_ID == "qdrant_point_id"
    assert ChunkField.METADATA == "metadata"
    assert ChunkField.CREATED_AT == "created_at"

    assert MessageField.QUESTION == "question"
    assert MessageField.ANSWER == "answer"
    assert MessageField.SOURCES == "sources"
    assert MessageField.METADATA == "metadata"

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


def test_retrieval_uses_qdrant_payload_key_contract(monkeypatch):
    contract_keys = SimpleNamespace(
        CHUNK_ID="contract_chunk_id",
        DOCUMENT_ID="contract_document_id",
        FILE_NAME="contract_file_name",
        CHUNK_INDEX="contract_chunk_index",
        TEXT="contract_text",
        HEADING="contract_heading",
        SECTION_PATH="contract_section_path",
        PAGE_START="contract_page_start",
        PAGE_END="contract_page_end",
        CHUNK_TYPE="contract_chunk_type",
        TOKEN_COUNT="contract_token_count",
    )
    monkeypatch.setattr(retrieval, "QdrantPayloadKey", contract_keys, raising=False)

    query_filter = retrieval.build_document_id_filter(["doc-1"])
    assert query_filter.must[0].key == contract_keys.DOCUMENT_ID

    class QdrantClient:
        def query_points(self, **kwargs):
            return SimpleNamespace(
                points=[
                    {
                        "id": "point-1",
                        "score": 0.8,
                        "payload": {
                            contract_keys.CHUNK_ID: "chunk-1",
                            contract_keys.DOCUMENT_ID: "doc-1",
                            contract_keys.FILE_NAME: "contract.pdf",
                            contract_keys.CHUNK_INDEX: 2,
                            contract_keys.TEXT: "contract text",
                            contract_keys.HEADING: "Contract",
                            contract_keys.SECTION_PATH: ["Contract"],
                            contract_keys.PAGE_START: 3,
                            contract_keys.PAGE_END: 4,
                            contract_keys.CHUNK_TYPE: "text",
                            contract_keys.TOKEN_COUNT: 5,
                        },
                    }
                ]
            )

    chunks = retrieval.search_semantic_chunks(
        [0.1],
        settings=Settings(_env_file=None),
        qdrant_client=QdrantClient(),
    )

    assert chunks[0] == {
        "id": "chunk-1",
        "chunk_id": "chunk-1",
        "document_id": "doc-1",
        "file_name": "contract.pdf",
        "chunk_index": 2,
        "content": "contract text",
        "text": "contract text",
        "heading": "Contract",
        "section_path": ["Contract"],
        "page_start": 3,
        "page_end": 4,
        "chunk_type": "text",
        "token_count": 5,
        "qdrant_score": 0.8,
        "rerank_score": None,
    }


def test_phase3_enums_use_exact_values_and_reject_unknown_values():
    assert [item.value for item in RetrievalStrategy] == [
        "semantic", "keyword", "hybrid", "metadata", "relation"
    ]
    assert [item.value for item in RetrievalPath] == ["semantic", "keyword", "relation"]
    assert [item.value for item in SummaryType] == ["section", "document"]
    assert [item.value for item in RelationType] == [
        "same_topic", "supports", "contradicts", "references"
    ]
    assert [item.value for item in WorkflowStatus] == ["running", "completed", "failed"]

    with pytest.raises(ValueError):
        RetrievalStrategy("vector")


def test_retrieval_filters_normalize_empty_values_and_validate_pages():
    filters = RetrievalFilters(
        mime_types=[" application/pdf ", "", "application/pdf"],
        heading="   ",
        section_path=[" Policies ", "", "Leave"],
        page_start=0,
        page_end=4,
    )

    assert filters.mime_types == ["application/pdf"]
    assert filters.heading is None
    assert filters.section_path == ["Policies", "Leave"]

    with pytest.raises(ValidationError):
        RetrievalFilters(page_start=-1)
    with pytest.raises(ValidationError):
        RetrievalFilters(page_start=5, page_end=4)


def test_old_chat_request_payload_remains_valid():
    request = ChatRequest(question="What is the policy?")

    assert request.document_ids == []
    assert request.save_message is False
    assert request.filters is None


def test_phase3_internal_models_validate_required_metadata():
    plan = QueryPlan.model_validate(
        {
            "is_complex": True,
            "strategy": "hybrid",
            "subqueries": [{"id": "q1", "text": "Compare policies"}],
            "inferred_filters": {},
            "needs_relations": False,
        }
    )
    assert plan.strategy is RetrievalStrategy.HYBRID

    candidate = RetrievalCandidate.model_validate(
        {
            "chunk_id": "chunk-1",
            "document_id": "doc-1",
            "file_name": "policy.pdf",
            "chunk_index": 0,
            "content": "Policy text",
            "semantic_rank": 1,
            "semantic_score": 0.9,
            "keyword_rank": 2,
            "keyword_score": 0.8,
            "fusion_score": 0.04,
            "retrieval_paths": ["semantic", "keyword"],
            "subquery_ids": ["q1"],
        }
    )
    assert candidate.retrieval_paths == [RetrievalPath.SEMANTIC, RetrievalPath.KEYWORD]

    grounding = GroundingResult(
        grounded=True,
        score=0.95,
        unsupported_claims=[],
        missing_citations=[],
    )
    citation = CitationValidationResult(
        valid=True,
        cited_keys=["S1"],
        cited_chunk_ids=["chunk-1"],
    )
    trace = WorkflowTraceEvent(
        node_name="retrieve",
        status="completed",
        attempt=1,
        duration_ms=12,
        input_count=1,
        output_count=3,
    )
    assert grounding.score == 0.95
    assert citation.invalid_keys == []
    assert trace.status is WorkflowStatus.COMPLETED

    with pytest.raises(ValidationError):
        GroundingResult(
            grounded=True,
            score=1.1,
            unsupported_claims=[],
            missing_citations=[],
        )
