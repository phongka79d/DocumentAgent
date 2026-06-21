from __future__ import annotations

from pathlib import Path
import traceback
from uuid import UUID

import pytest

from app.core.config import Settings
from app.core.contracts import RetrievalPath
from app.models.schemas import RetrievalCandidate, RetrievalFilters
from app.services import keyword_search


DOCUMENT_A = UUID("11111111-1111-1111-1111-111111111111")
DOCUMENT_B = UUID("22222222-2222-2222-2222-222222222222")


class FakeRpcResponse:
    def __init__(self, data=None):
        self.data = data


class FakeRpcRequest:
    def __init__(self, client, function_name, params):
        self.client = client
        self.function_name = function_name
        self.params = params

    def execute(self):
        self.client.calls.append((self.function_name, self.params))
        if self.client.error is not None:
            raise self.client.error
        return FakeRpcResponse(self.client.rows)


class FakeSupabaseClient:
    def __init__(self, rows=None, *, error: Exception | None = None):
        self.rows = rows if rows is not None else []
        self.error = error
        self.calls = []

    def rpc(self, function_name, params):
        return FakeRpcRequest(self, function_name, params)


def _settings() -> Settings:
    return Settings(RETRIEVAL_KEYWORD_TOP_K=3)


def _row(**overrides):
    row = {
        "chunk_id": "chunk-c",
        "document_id": str(DOCUMENT_A),
        "file_name": "alpha.pdf",
        "chunk_index": 2,
        "content": "Alpha keyword content",
        "heading": "Intro",
        "section_path": ["Intro", "Scope"],
        "page_start": 3,
        "page_end": 4,
        "chunk_type": "text",
        "token_count": 42,
        "keyword_score": 0.5,
    }
    row.update(overrides)
    return row


def test_search_keyword_chunks_passes_all_explicit_filters_to_rpc():
    client = FakeSupabaseClient([_row()])

    keyword_search.search_keyword_chunks(
        "  refund policy  ",
        document_ids=(DOCUMENT_A, str(DOCUMENT_B)),
        filters=RetrievalFilters(
            mime_types=["application/pdf", "text/plain"],
            heading="  Intro  ",
            section_path=["Policies", "Refunds"],
            page_start=2,
            page_end=8,
        ),
        settings=_settings(),
        supabase_client=client,
    )

    assert client.calls == [
        (
            "search_document_chunks_keyword",
            {
                "query_text": "refund policy",
                "result_limit": 3,
                "document_ids": [str(DOCUMENT_A), str(DOCUMENT_B)],
                "mime_types": ["application/pdf", "text/plain"],
                "filter_heading": "Intro",
                "filter_section_path": ["Policies", "Refunds"],
                "filter_page_start": 2,
                "filter_page_end": 8,
            },
        )
    ]


def test_search_keyword_chunks_normalizes_rows_into_shared_candidate_contract():
    client = FakeSupabaseClient(
        [
            _row(
                chunk_id="chunk-b",
                document_id=str(DOCUMENT_A),
                file_name="alpha.pdf",
                chunk_index=1,
                keyword_score="0.75",
            )
        ]
    )

    results = keyword_search.search_keyword_chunks(
        "alpha", settings=_settings(), supabase_client=client
    )

    assert len(results) == 1
    candidate = RetrievalCandidate.model_validate(results[0])
    assert candidate.chunk_id == "chunk-b"
    assert candidate.document_id == str(DOCUMENT_A)
    assert candidate.file_name == "alpha.pdf"
    assert candidate.keyword_score == 0.75
    assert candidate.keyword_rank == 1
    assert candidate.retrieval_paths == [RetrievalPath.KEYWORD]
    assert candidate.qdrant_score is None
    assert candidate.semantic_rank is None
    assert candidate.semantic_score is None


def test_search_keyword_chunks_orders_ties_deterministically_and_enforces_top_k():
    client = FakeSupabaseClient(
        [
            _row(chunk_id="third", document_id=str(DOCUMENT_B), chunk_index=1, keyword_score=0.8),
            _row(chunk_id="first", document_id=str(DOCUMENT_A), chunk_index=2, keyword_score=0.8),
            _row(chunk_id="fourth", document_id=str(DOCUMENT_B), chunk_index=2, keyword_score=0.8),
            _row(chunk_id="second", document_id=str(DOCUMENT_A), chunk_index=3, keyword_score=0.8),
        ]
    )

    results = keyword_search.search_keyword_chunks(
        "alpha", settings=_settings(), supabase_client=client
    )

    assert [candidate["chunk_id"] for candidate in results] == ["first", "second", "third"]
    assert [candidate["keyword_rank"] for candidate in results] == [1, 2, 3]


def test_search_keyword_chunks_rejects_empty_query_without_rpc_call():
    client = FakeSupabaseClient([])

    with pytest.raises(keyword_search.KeywordSearchValidationError, match="query is required"):
        keyword_search.search_keyword_chunks("  ", settings=_settings(), supabase_client=client)

    assert client.calls == []


def test_search_keyword_chunks_raises_safe_recoverable_error_for_rpc_failure():
    client = FakeSupabaseClient(
        error=RuntimeError(
            "database password=super-secret failed calling https://project.supabase.co/rpc"
        )
    )

    with pytest.raises(keyword_search.KeywordSearchError) as exc_info:
        keyword_search.search_keyword_chunks(
            "alpha", settings=_settings(), supabase_client=client
        )

    assert exc_info.value.recoverable is True
    assert exc_info.value.code == "keyword_rpc_unavailable"
    assert exc_info.value.__cause__ is None
    assert exc_info.value.__suppress_context__ is True
    message = str(exc_info.value)
    assert "keyword retrieval is unavailable" in message
    assert "super-secret" not in message
    assert "password" not in message
    assert "supabase.co" not in message
    sensitive_markers = ("super-secret", "password", "supabase.co")
    formatted_traceback = "".join(
        traceback.format_exception(
            type(exc_info.value),
            exc_info.value,
            exc_info.value.__traceback__,
        )
    )
    formatted_visible_chain = "".join(traceback.format_exception(exc_info.value))
    for marker in sensitive_markers:
        assert marker not in formatted_traceback
        assert marker not in formatted_visible_chain


def test_sql_artifacts_define_keyword_index_and_rpc_contract():
    root = Path(__file__).resolve().parents[2]
    migration = (root / "docs/database/phase3_migration.sql").read_text().lower()
    fresh = (root / "docs/database/supabase_schema.sql").read_text().lower()

    required_fragments = (
        "using gin (to_tsvector('simple', coalesce(heading, '') || ' ' || content))",
        "search_document_chunks_keyword",
        "websearch_to_tsquery('simple', query_text)",
        "ts_rank_cd(",
        "join documents",
        "documents.mime_type",
        "document_ids is null",
        "mime_types is null",
        "filter_section_path is null",
        "page_start <= page_end",
        "keyword_score desc, document_id asc, chunk_index asc",
        "limit result_limit",
    )
    for fragment in required_fragments:
        assert fragment in migration
        assert fragment in fresh
