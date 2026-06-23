from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import get_type_hints
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.core.contracts import RetrievalPath, RetrievalStrategy
from app.graphs import query_nodes
from app.graphs.query_graph import build_query_graph
from app.graphs.query_state import QueryState
from app.models.schemas import (
    CitationValidationResult,
    GroundingResult,
    QueryPlan,
    QuerySubquery,
    RetrievalFilters,
)
from app.services import chunks as chunk_service
from app.services import messages as message_service
from app.services import retrieval


DOC_A = "11111111-1111-1111-1111-111111111111"
DOC_B = "22222222-2222-2222-2222-222222222222"


def _test_settings(
    *,
    context_mode: str = "section_aware",
    context_window: int = 1,
    section_sibling_window: int = 1,
    enable_keyword_search: bool = False,
) -> Settings:
    return Settings(
        _env_file=None,
        SUPABASE_STORAGE_BUCKET="documents",
        QDRANT_COLLECTION="document_chunks_v1",
        RETRIEVAL_SEMANTIC_TOP_K=40,
        RETRIEVAL_FINAL_TOP_K=5,
        RETRIEVAL_CONTEXT_MODE=context_mode,
        RETRIEVAL_CONTEXT_WINDOW=context_window,
        RETRIEVAL_SECTION_SIBLING_WINDOW=section_sibling_window,
        RETRIEVAL_CONTEXT_MAX_CANDIDATES=8,
        ENABLE_RERANK=True,
        ENABLE_KEYWORD_SEARCH=enable_keyword_search,
        SHOPAIKEY_API_KEY="shopai-key",
        SHOPAIKEY_BASE_URL="https://api.shopaikey.com/v1",
        SHOPAIKEY_EMBEDDING_MODEL="text-embedding-3-small",
        JINA_API_KEY="jina-key",
        JINA_RERANK_MODEL="jina-reranker-v2-base-multilingual",
        QDRANT_URL="https://qdrant.example.com",
        QDRANT_API_KEY="qdrant-key",
    )

@dataclass
class FakeQdrantClient:
    points: list[object] = field(default_factory=list)
    query_calls: list[dict[str, object]] = field(default_factory=list)

    def query_points(self, *, collection_name, query, query_filter=None, limit=10, with_payload=True, with_vectors=False, **kwargs):
        self.query_calls.append(
            {
                "collection_name": collection_name,
                "query": query,
                "query_filter": query_filter,
                "limit": limit,
                "with_payload": with_payload,
                "with_vectors": with_vectors,
                "kwargs": kwargs,
            }
        )
        return SimpleNamespace(points=list(self.points)[:limit])

@dataclass
class FakeSupabaseQuery:
    client: "FakeSupabaseClient"
    table_name: str
    operation: str = "select"
    payload: dict[str, object] | list[dict[str, object]] | None = None
    filters: list[tuple[str, object]] = field(default_factory=list)
    sort_order: list[tuple[str, bool]] = field(default_factory=list)
    selected_columns: tuple[str, ...] = ()
    limit_count: int | None = None

    def select(self, *columns: str, count=None, head=None):
        self.operation = "select"
        self.selected_columns = columns
        return self

    def insert(
        self,
        json,
        *,
        count=None,
        returning=None,
        upsert=False,
        default_to_null=True,
    ):
        self.operation = "insert"
        self.payload = json
        return self

    def eq(self, column: str, value):
        self.filters.append((column, value))
        return self

    def in_(self, column: str, values):
        self.filters.append((column, list(values)))
        return self

    def order(self, column: str, *, desc=False, nullsfirst=None, foreign_table=None):
        self.sort_order.append((column, desc))
        return self

    def limit(self, size: int, *, foreign_table=None):
        self.limit_count = size
        return self

    def execute(self):
        rows = list(self.client.tables.get(self.table_name, []))
        for column, expected in self.filters:
            if isinstance(expected, list):
                rows = [row for row in rows if row.get(column) in expected]
            else:
                rows = [row for row in rows if row.get(column) == expected]
        if self.operation == "select":
            for column, desc in reversed(self.sort_order):
                rows.sort(key=lambda row: row.get(column), reverse=desc)
            if self.limit_count is not None:
                rows = rows[: self.limit_count]
            self.client.query_log.append(
                {
                    "table_name": self.table_name,
                    "operation": self.operation,
                    "selected_columns": self.selected_columns,
                    "filters": list(self.filters),
                    "sort_order": list(self.sort_order),
                }
            )
            return SimpleNamespace(data=rows)

        if self.operation == "insert":
            assert self.payload is not None
            payload_rows = self.payload if isinstance(self.payload, list) else [self.payload]
            inserted_rows: list[dict[str, object]] = []
            for payload in payload_rows:
                row = dict(payload)
                row.setdefault("id", str(uuid4()))
                inserted_rows.append(row)
            self.client.tables.setdefault(self.table_name, []).extend(inserted_rows)
            self.client.query_log.append(
                {
                    "table_name": self.table_name,
                    "operation": self.operation,
                    "payload": inserted_rows,
                }
            )
            return SimpleNamespace(data=inserted_rows)

        raise AssertionError(f"Unsupported fake operation: {self.operation}")

@dataclass
class FakeSupabaseClient:
    tables: dict[str, list[dict[str, object]]] = field(default_factory=dict)
    query_log: list[dict[str, object]] = field(default_factory=list)

    def table(self, table_name: str) -> FakeSupabaseQuery:
        return FakeSupabaseQuery(self, table_name)

@dataclass
class FakeHttpResponse:
    payload: dict[str, object]

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


@dataclass
class FakeHttpClient:
    response: object
    post_calls: list[dict[str, object]] = field(default_factory=list)

    def post(self, url: str, json: dict[str, object]):
        self.post_calls.append({"url": url, "json": json})
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


@dataclass
class FakeEmbeddingEndpoint:
    vectors: list[list[float]]
    calls: list[tuple[str, list[str]]] = field(default_factory=list)

    def create(self, *, model: str, input: list[str]):
        self.calls.append((model, list(input)))
        return SimpleNamespace(
            data=[SimpleNamespace(embedding=vector) for vector in self.vectors]
        )

@dataclass
class FakeShopAIKeyClient:
    vectors: list[list[float]] | None = None
    chat_response: object | None = None

    def __post_init__(self):
        self.embeddings = FakeEmbeddingEndpoint(self.vectors or [])
        if self.chat_response is not None:
            self.chat = SimpleNamespace(
                completions=FakeChatCompletionsEndpoint(self.chat_response)
            )

@dataclass
class FakeChatCompletionsEndpoint:
    response: object
    calls: list[dict[str, object]] = field(default_factory=list)

    def create(
        self,
        *,
        model: str,
        messages: list[dict[str, object]],
        temperature: float | None = None,
        max_tokens: int | None = None,
        **kwargs,
    ):
        self.calls.append(
            {
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "kwargs": kwargs,
            }
        )
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def _qdrant_point(
    *,
    chunk_id: str,
    document_id: str,
    chunk_index: int,
    file_name: str,
    score: float,
    text: str,
) -> object:
    return SimpleNamespace(
        id=chunk_id,
        score=score,
        payload={
            "document_id": document_id,
            "chunk_id": chunk_id,
            "chunk_index": chunk_index,
            "file_name": file_name,
            "heading": None,
            "section_path": [],
            "page_start": 1,
            "page_end": 1,
            "chunk_type": "fixed",
            "token_count": 100,
            "text": text,
        },
    )


def test_search_semantic_chunks_applies_document_filter_and_default_top_k():
    settings = _test_settings()
    qdrant_client = FakeQdrantClient(
        points=[
            _qdrant_point(
                chunk_id="chunk-a",
                document_id=DOC_A,
                chunk_index=0,
                file_name="alpha.pdf",
                score=0.9,
                text="alpha chunk",
            )
        ]
    )

    results = retrieval.search_semantic_chunks(
        [0.1, 0.2, 0.3],
        document_ids=[DOC_A, DOC_B],
        settings=settings,
        qdrant_client=qdrant_client,
    )

    assert qdrant_client.query_calls[0]["collection_name"] == settings.QDRANT_COLLECTION
    assert qdrant_client.query_calls[0]["limit"] == settings.RETRIEVAL_SEMANTIC_TOP_K
    assert qdrant_client.query_calls[0]["query_filter"].must[0].key == "document_id"
    assert qdrant_client.query_calls[0]["query_filter"].must[0].match.any == [DOC_A, DOC_B]
    assert results[0]["chunk_id"] == "chunk-a"
    assert results[0]["qdrant_score"] == 0.9


def test_build_qdrant_filter_combines_metadata_conditions_with_document_allow_list():
    query_filter = retrieval.build_qdrant_filter(
        [DOC_A, DOC_B],
        {
            "mime_types": ["application/pdf", "text/markdown"],
            "heading": "Pricing",
            "section_path": ["Plans", "Enterprise"],
            "page_start": 3,
            "page_end": 7,
        },
    )

    assert query_filter is not None
    conditions = query_filter.must
    assert [condition.key for condition in conditions] == [
        "document_id",
        "mime_type",
        "heading",
        "section_path",
        "section_path",
        "page_start",
        "page_end",
    ]
    assert conditions[0].match.any == [DOC_A, DOC_B]
    assert conditions[1].match.any == ["application/pdf", "text/markdown"]
    assert conditions[2].match.text == "Pricing"
    assert [conditions[3].match.value, conditions[4].match.value] == [
        "Plans",
        "Enterprise",
    ]
    assert conditions[5].range.lte == 7
    assert conditions[6].range.gte == 3


def test_build_qdrant_filter_omits_page_conditions_when_page_filter_is_absent():
    query_filter = retrieval.build_qdrant_filter(
        None,
        {
            "heading": "Pricing",
        },
    )

    assert query_filter is not None
    assert [condition.key for condition in query_filter.must] == ["heading"]


def test_search_semantic_chunks_without_document_ids_queries_all_documents():
    settings = _test_settings()
    qdrant_client = FakeQdrantClient(
        points=[
            _qdrant_point(
                chunk_id="chunk-a",
                document_id=DOC_A,
                chunk_index=0,
                file_name="alpha.pdf",
                score=0.9,
                text="alpha chunk",
            )
        ]
    )

    retrieval.search_semantic_chunks(
        [0.1, 0.2, 0.3],
        document_ids=[],
        settings=settings,
        qdrant_client=qdrant_client,
    )

    assert qdrant_client.query_calls[0]["query_filter"] is None


def test_search_semantic_chunks_passes_metadata_filters_to_qdrant():
    settings = _test_settings()
    qdrant_client = FakeQdrantClient(points=[])

    retrieval.search_semantic_chunks(
        [0.1, 0.2, 0.3],
        document_ids=[DOC_A],
        filters={
            "mime_types": ["application/pdf"],
            "heading": "Pricing",
            "section_path": ["Enterprise"],
            "page_start": 2,
            "page_end": 4,
        },
        settings=settings,
        qdrant_client=qdrant_client,
    )

    query_filter = qdrant_client.query_calls[0]["query_filter"]
    assert query_filter is not None
    assert [condition.key for condition in query_filter.must] == [
        "document_id",
        "mime_type",
        "heading",
        "section_path",
        "page_start",
        "page_end",
    ]


def test_retrieve_candidates_node_records_retry_attempts_for_semantic_recovery():
    settings = _test_settings().model_copy(
        update={
            "WORKFLOW_MAX_ATTEMPTS": 2,
            "WORKFLOW_RETRY_BASE_DELAY_SECONDS": 0.0,
            "WORKFLOW_RETRY_MAX_DELAY_SECONDS": 0.0,
        }
    )

    class FlakyQdrantClient(FakeQdrantClient):
        def query_points(self, **kwargs):
            self.query_calls.append(kwargs)
            if len(self.query_calls) == 1:
                raise TimeoutError("qdrant timed out")
            return SimpleNamespace(
                points=[
                    _qdrant_point(
                        chunk_id="chunk-a",
                        document_id=DOC_A,
                        chunk_index=0,
                        file_name="alpha.pdf",
                        score=0.9,
                        text="alpha chunk",
                    )
                ]
            )

    result = query_nodes.retrieve_candidates_node(
        {
            "query_plan": QueryPlan(
                is_complex=False,
                strategy=RetrievalStrategy.SEMANTIC,
                subqueries=[QuerySubquery(id="q1", text="pricing")],
                inferred_filters=RetrievalFilters(),
                needs_relations=False,
            ),
            "subqueries": [QuerySubquery(id="q1", text="pricing")],
            "document_ids": [DOC_A],
        },
        settings=settings,
        qdrant_client=FlakyQdrantClient(),
        shopaikey_client=FakeShopAIKeyClient(vectors=[[0.1, 0.2, 0.3]]),
    )

    assert "error_message" not in result
    assert result["path_candidates"]["q1:semantic"][0]["chunk_id"] == "chunk-a"
    assert result["retrieval_metrics"]["retry_attempts"] == {
        "retrieve_candidates": 2
    }


def test_get_chunks_by_document_and_indexes_uses_supabase_lookup_order():
    settings = _test_settings()
    fake_client = FakeSupabaseClient(
        tables={
            "document_chunks": [
                {
                    "id": "chunk-2",
                    "document_id": DOC_A,
                    "chunk_index": 2,
                    "content": "two",
                },
                {
                    "id": "chunk-0",
                    "document_id": DOC_A,
                    "chunk_index": 0,
                    "content": "zero",
                },
                {
                    "id": "chunk-1",
                    "document_id": DOC_A,
                    "chunk_index": 1,
                    "content": "one",
                },
                {
                    "id": "chunk-other",
                    "document_id": DOC_B,
                    "chunk_index": 0,
                    "content": "other",
                },
            ]
        }
    )

    rows = chunk_service.get_chunks_by_document_and_indexes(
        DOC_A,
        [2, 0, 2, 1],
        settings=settings,
        supabase_client=fake_client,
    )

    assert [row["id"] for row in rows] == ["chunk-0", "chunk-1", "chunk-2"]
    assert fake_client.query_log[-1]["table_name"] == "document_chunks"
    assert fake_client.query_log[-1]["filters"] == [
        ("document_id", DOC_A),
        ("chunk_index", [0, 1, 2]),
    ]
    assert fake_client.query_log[-1]["sort_order"] == [("chunk_index", False)]


def test_rerank_chunks_falls_back_to_qdrant_score_sort_when_jina_fails():
    settings = _test_settings()
    chunks = [
        {
            "chunk_id": "chunk-a",
            "document_id": DOC_A,
            "file_name": "alpha.pdf",
            "chunk_index": 0,
            "content": "alpha",
            "qdrant_score": 0.4,
        },
        {
            "chunk_id": "chunk-b",
            "document_id": DOC_A,
            "file_name": "alpha.pdf",
            "chunk_index": 1,
            "content": "beta",
            "qdrant_score": 0.9,
        },
        {
            "chunk_id": "chunk-c",
            "document_id": DOC_B,
            "file_name": "bravo.pdf",
            "chunk_index": 0,
            "content": "gamma",
            "qdrant_score": 0.7,
        },
        {
            "chunk_id": "chunk-d",
            "document_id": DOC_B,
            "file_name": "bravo.pdf",
            "chunk_index": 1,
            "content": "delta",
            "qdrant_score": 0.6,
        },
        {
            "chunk_id": "chunk-e",
            "document_id": DOC_B,
            "file_name": "bravo.pdf",
            "chunk_index": 2,
            "content": "epsilon",
            "qdrant_score": 0.8,
        },
        {
            "chunk_id": "chunk-f",
            "document_id": DOC_B,
            "file_name": "bravo.pdf",
            "chunk_index": 3,
            "content": "zeta",
            "qdrant_score": 0.1,
        },
    ]
    jina_client = SimpleNamespace(
        http_client=FakeHttpClient(response=RuntimeError("jina unavailable")),
        model=settings.JINA_RERANK_MODEL,
    )

    results = retrieval.rerank_chunks(
        "What does the document say?",
        chunks,
        settings=settings,
        jina_client=jina_client,
    )

    assert [chunk["chunk_id"] for chunk in results] == [
        "chunk-b",
        "chunk-e",
        "chunk-c",
        "chunk-d",
        "chunk-a",
    ]


def test_extract_retrieval_hints_uses_llm_json_without_hardcoded_query_phrase():
    settings = _test_settings()
    fake_shopaikey_client = FakeShopAIKeyClient(
        chat_response=SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content='{"boundary_positions":["beginning"]}'
                    )
                )
            ]
        )
    )

    hints = retrieval.extract_retrieval_hints(
        "Who is Alice, and what happens at the opening of the story?",
        settings=settings,
        shopaikey_client=fake_shopaikey_client,
    )

    assert hints == {"boundary_positions": ["beginning"]}
    chat_call = fake_shopaikey_client.chat.completions.calls[0]
    assert chat_call["model"] == settings.SHOPAIKEY_INPUT_MODEL
    assert "opening" in chat_call["messages"][1]["content"]


def test_retrieve_context_chunks_orchestrates_search_rerank_and_neighbor_expansion():
    settings = _test_settings()
    fake_supabase_client = FakeSupabaseClient(
        tables={
            "document_chunks": [
                {
                    "id": "chunk-1",
                    "document_id": DOC_A,
                    "chunk_index": 1,
                    "content": "neighbor one",
                },
                {
                    "id": "chunk-3",
                    "document_id": DOC_A,
                    "chunk_index": 3,
                    "content": "neighbor three",
                },
                {
                    "id": "chunk-5",
                    "document_id": DOC_A,
                    "chunk_index": 5,
                    "content": "neighbor five",
                },
                {
                    "id": "chunk-7",
                    "document_id": DOC_A,
                    "chunk_index": 7,
                    "content": "neighbor seven",
                },
            ]
        }
    )
    fake_qdrant_client = FakeQdrantClient(
        points=[
            _qdrant_point(
                chunk_id="chunk-2",
                document_id=DOC_A,
                chunk_index=2,
                file_name="alpha.pdf",
                score=0.95,
                text="retrieved two",
            ),
            _qdrant_point(
                chunk_id="chunk-4",
                document_id=DOC_A,
                chunk_index=4,
                file_name="alpha.pdf",
                score=0.9,
                text="retrieved four",
            ),
            _qdrant_point(
                chunk_id="chunk-6",
                document_id=DOC_A,
                chunk_index=6,
                file_name="alpha.pdf",
                score=0.85,
                text="retrieved six",
            ),
            _qdrant_point(
                chunk_id="chunk-8",
                document_id=DOC_A,
                chunk_index=8,
                file_name="alpha.pdf",
                score=0.8,
                text="retrieved eight",
            ),
            _qdrant_point(
                chunk_id="chunk-10",
                document_id=DOC_A,
                chunk_index=10,
                file_name="alpha.pdf",
                score=0.75,
                text="retrieved ten",
            ),
        ]
    )
    fake_shopaikey_client = FakeShopAIKeyClient(vectors=[[0.1, 0.2, 0.3]])
    fake_jina_client = SimpleNamespace(
        http_client=FakeHttpClient(
            response=FakeHttpResponse(
                {
                    "results": [
                        {"index": 0, "relevance_score": 0.99},
                        {"index": 1, "relevance_score": 0.98},
                        {"index": 2, "relevance_score": 0.97},
                        {"index": 3, "relevance_score": 0.96},
                        {"index": 4, "relevance_score": 0.95},
                    ]
                }
            )
        ),
        model=settings.JINA_RERANK_MODEL,
    )

    result = retrieval.retrieve_context_chunks(
        "What does the document say?",
        document_ids=[DOC_A],
        settings=settings,
        supabase_client=fake_supabase_client,
        qdrant_client=fake_qdrant_client,
        shopaikey_client=fake_shopaikey_client,
        jina_client=fake_jina_client,
    )

    assert result["question"] == "What does the document say?"
    assert result["document_ids"] == [DOC_A]
    assert result["query_embedding"] == [0.1, 0.2, 0.3]
    assert fake_qdrant_client.query_calls[0]["query_filter"].must[0].match.any == [DOC_A]
    assert fake_shopaikey_client.embeddings.calls == [
        (settings.SHOPAIKEY_EMBEDDING_MODEL, ["What does the document say?"])
    ]
    assert [chunk["chunk_id"] for chunk in result["retrieved_chunks"]] == [
        "chunk-2",
        "chunk-4",
        "chunk-6",
        "chunk-8",
        "chunk-10",
    ]
    assert [chunk["chunk_id"] for chunk in result["reranked_chunks"]] == [
        "chunk-2",
        "chunk-4",
        "chunk-6",
        "chunk-8",
        "chunk-10",
    ]
    assert len(result["context_chunks"]) == settings.RETRIEVAL_CONTEXT_MAX_CANDIDATES
    assert [chunk["chunk_id"] for chunk in result["context_chunks"][:5]] == [
        "chunk-2",
        "chunk-4",
        "chunk-6",
        "chunk-8",
        "chunk-10",
    ]
    assert [chunk["chunk_id"] for chunk in result["context_chunks"][5:]] == [
        "chunk-1",
        "chunk-3",
        "chunk-5",
    ]
    assert len(fake_supabase_client.query_log) == 2
    assert fake_supabase_client.query_log[0]["filters"] == [
        ("document_id", DOC_A),
        ("chunk_index", [1, 3]),
    ]
    assert fake_supabase_client.query_log[1]["filters"] == [
        ("document_id", DOC_A),
        ("chunk_index", [3, 5]),
    ]


def test_retrieve_context_chunks_adds_llm_requested_beginning_boundary_chunk():
    settings = _test_settings()
    fake_supabase_client = FakeSupabaseClient(
        tables={
            "document_chunks": [
                {
                    "id": "chunk-0",
                    "document_id": DOC_A,
                    "chunk_index": 0,
                    "content": "Alice was sitting by her sister when the White Rabbit ran by.",
                },
                {
                    "id": "chunk-56",
                    "document_id": DOC_A,
                    "chunk_index": 56,
                    "content": "neighbor identity setup",
                },
                {
                    "id": "chunk-58",
                    "document_id": DOC_A,
                    "chunk_index": 58,
                    "content": "neighbor identity follow-up",
                },
            ]
        }
    )
    fake_qdrant_client = FakeQdrantClient(
        points=[
            _qdrant_point(
                chunk_id="chunk-57",
                document_id=DOC_A,
                chunk_index=57,
                file_name="alice-in-wonderland.txt",
                score=0.99,
                text="Alice says she hardly knows who she is after changing several times.",
            ),
            _qdrant_point(
                chunk_id="chunk-59",
                document_id=DOC_A,
                chunk_index=59,
                file_name="alice-in-wonderland.txt",
                score=0.98,
                text="More later identity confusion.",
            ),
        ]
    )
    fake_shopaikey_client = FakeShopAIKeyClient(
        vectors=[[0.1, 0.2, 0.3]],
        chat_response=SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content='{"boundary_positions":["beginning"]}'
                    )
                )
            ]
        ),
    )
    fake_jina_client = SimpleNamespace(
        http_client=FakeHttpClient(
            response=FakeHttpResponse(
                {
                    "results": [
                        {"index": 0, "relevance_score": 0.99},
                        {"index": 1, "relevance_score": 0.98},
                    ]
                }
            )
        ),
        model=settings.JINA_RERANK_MODEL,
    )

    result = retrieval.retrieve_context_chunks(
        "Who is Alice, and what happens at the opening of the story?",
        document_ids=[DOC_A],
        settings=settings,
        supabase_client=fake_supabase_client,
        qdrant_client=fake_qdrant_client,
        shopaikey_client=fake_shopaikey_client,
        jina_client=fake_jina_client,
    )

    assert [chunk["chunk_id"] for chunk in result["reranked_chunks"]] == [
        "chunk-57",
        "chunk-59",
    ]
    assert "chunk-0" in [chunk["chunk_id"] for chunk in result["context_chunks"]]
    assert result["retrieval_hints"] == {"boundary_positions": ["beginning"]}


def test_expand_neighbor_context_adds_llm_requested_end_boundary_chunk():
    settings = _test_settings()
    fake_supabase_client = FakeSupabaseClient(
        tables={
            "document_chunks": [
                {
                    "id": "chunk-2",
                    "document_id": DOC_A,
                    "chunk_index": 2,
                    "content": "middle chunk",
                },
                {
                    "id": "chunk-99",
                    "document_id": DOC_A,
                    "chunk_index": 99,
                    "content": "Alice woke up on the bank.",
                },
            ]
        }
    )
    reranked_chunks = [
        {
            "chunk_id": "chunk-2",
            "document_id": DOC_A,
            "file_name": "alice-in-wonderland.txt",
            "chunk_index": 2,
            "content": "middle chunk",
            "qdrant_score": 0.95,
            "rerank_score": 0.99,
        }
    ]

    context_chunks = retrieval.expand_neighbor_context(
        reranked_chunks,
        settings=settings,
        supabase_client=fake_supabase_client,
        retrieval_hints={"boundary_positions": ["end"]},
        document_ids=[DOC_A],
    )

    assert [chunk["chunk_id"] for chunk in context_chunks] == [
        "chunk-2",
        "chunk-99",
    ]



def test_expand_neighbor_context_section_aware_prefers_same_section_neighbors_before_generic_neighbors():
    settings = _test_settings(context_window=2, section_sibling_window=1)
    fake_client = FakeSupabaseClient(
        tables={
            "document_chunks": [
                {
                    "id": "chunk-0",
                    "document_id": DOC_A,
                    "chunk_index": 0,
                    "content": "intro chunk",
                    "section_path": ["Intro"],
                    "file_name": "alpha.pdf",
                },
                {
                    "id": "chunk-1",
                    "document_id": DOC_A,
                    "chunk_index": 1,
                    "content": "same section previous",
                    "section_path": ["Pricing"],
                    "file_name": "alpha.pdf",
                },
                {
                    "id": "chunk-3",
                    "document_id": DOC_A,
                    "chunk_index": 3,
                    "content": "same section next",
                    "section_path": ["Pricing"],
                    "file_name": "alpha.pdf",
                },
                {
                    "id": "chunk-4",
                    "document_id": DOC_A,
                    "chunk_index": 4,
                    "content": "generic later",
                    "section_path": ["Appendix"],
                    "file_name": "alpha.pdf",
                },
            ]
        }
    )
    reranked_chunks = [
        {
            "chunk_id": "chunk-2",
            "document_id": DOC_A,
            "file_name": "alpha.pdf",
            "chunk_index": 2,
            "section_path": ["Pricing"],
            "content": "anchor chunk",
            "qdrant_score": 0.95,
            "rerank_score": 0.99,
        }
    ]

    context_chunks = retrieval.expand_neighbor_context(
        reranked_chunks,
        settings=settings,
        supabase_client=fake_client,
    )

    assert [chunk["chunk_id"] for chunk in context_chunks] == [
        "chunk-2",
        "chunk-1",
        "chunk-3",
        "chunk-0",
        "chunk-4",
    ]
    assert context_chunks[0].get("is_neighbor_context") is None
    assert all(chunk["is_neighbor_context"] is True for chunk in context_chunks[1:])
    assert len(fake_client.query_log) == 1
    assert fake_client.query_log[0]["filters"] == [
        ("document_id", DOC_A),
        ("chunk_index", [0, 1, 3, 4]),
    ]

def test_expand_neighbor_context_keeps_reranked_chunks_first_deduplicates_and_caps_context(
    monkeypatch,
):
    settings = _test_settings(context_mode="neighbor")
    reranked_chunks = [
        {
            "chunk_id": "chunk-1",
            "document_id": DOC_A,
            "file_name": "alpha.pdf",
            "chunk_index": 1,
            "content": "chunk 1",
            "qdrant_score": 0.95,
            "rerank_score": 0.99,
            "fusion_score": 0.42,
            "retrieval_paths": [RetrievalPath.SEMANTIC, RetrievalPath.KEYWORD],
            "citation_key": "S1",
        },
        {
            "chunk_id": "chunk-2",
            "document_id": DOC_A,
            "file_name": "alpha.pdf",
            "chunk_index": 2,
            "content": "chunk 2",
            "qdrant_score": 0.9,
            "rerank_score": 0.96,
        },
        {
            "chunk_id": "chunk-3",
            "document_id": DOC_A,
            "file_name": "alpha.pdf",
            "chunk_index": 3,
            "content": "chunk 3",
            "qdrant_score": 0.85,
            "rerank_score": 0.94,
        },
        {
            "chunk_id": "chunk-4",
            "document_id": DOC_B,
            "file_name": "bravo.pdf",
            "chunk_index": 0,
            "content": "chunk 4",
            "qdrant_score": 0.8,
            "rerank_score": 0.93,
        },
        {
            "chunk_id": "chunk-5",
            "document_id": DOC_B,
            "file_name": "bravo.pdf",
            "chunk_index": 1,
            "content": "chunk 5",
            "qdrant_score": 0.75,
            "rerank_score": 0.92,
        },
    ]

    def _neighbor_lookup(document_id, chunk_indexes, **kwargs):
        lookup = {
            (DOC_A, (0, 2)): [
                {
                    "id": "chunk-0",
                    "document_id": DOC_A,
                    "chunk_index": 0,
                    "content": "chunk 0",
                },
                {
                    "id": "chunk-2",
                    "document_id": DOC_A,
                    "chunk_index": 2,
                    "content": "duplicate chunk 2",
                },
            ],
            (DOC_A, (1, 3)): [
                {
                    "id": "chunk-4",
                    "document_id": DOC_A,
                    "chunk_index": 4,
                    "content": "chunk 4",
                }
            ],
            (DOC_A, (2, 4)): [
                {
                    "id": "chunk-6",
                    "document_id": DOC_A,
                    "chunk_index": 6,
                    "content": "chunk 6",
                },
                {
                    "id": "chunk-7",
                    "document_id": DOC_A,
                    "chunk_index": 7,
                    "content": "chunk 7",
                },
            ],
            (DOC_B, (0, 2)): [],
            (DOC_B, (1,)): [],
        }
        return lookup.get((str(document_id), tuple(chunk_indexes)), [])

    monkeypatch.setattr(chunk_service, "get_chunks_by_document_and_indexes", _neighbor_lookup)

    context_chunks = retrieval.expand_neighbor_context(
        reranked_chunks,
        settings=settings,
    )

    assert len(context_chunks) == settings.RETRIEVAL_CONTEXT_MAX_CANDIDATES
    assert [chunk["chunk_id"] for chunk in context_chunks[:5]] == [
        "chunk-1",
        "chunk-2",
        "chunk-3",
        "chunk-4",
        "chunk-5",
    ]
    assert context_chunks[0]["fusion_score"] == 0.42
    assert context_chunks[0]["retrieval_paths"] == ["semantic", "keyword"]
    assert context_chunks[0]["citation_key"] == "S1"
    assert len({chunk["chunk_id"] for chunk in context_chunks}) == len(context_chunks)
    assert [chunk["chunk_id"] for chunk in context_chunks[5:]] == [
        "chunk-0",
        "chunk-6",
        "chunk-7",
    ]


def test_jina_rerank_node_limits_jina_documents_to_candidate_top_k_and_requests_final_top_k():
    settings = _test_settings()
    retrieved_chunks = [
        {
            "chunk_id": f"chunk-{index}",
            "document_id": DOC_A,
            "file_name": "alpha.pdf",
            "chunk_index": index,
            "content": f"chunk {index}",
            "qdrant_score": 1.0 - (index * 0.1),
            "fusion_score": 1.0 - (index * 0.1),
            "retrieval_paths": [RetrievalPath.SEMANTIC],
        }
        for index in range(5)
    ]
    fake_jina_client = SimpleNamespace(
        http_client=FakeHttpClient(
            response=FakeHttpResponse(
                {
                    "results": [
                        {"index": 2, "relevance_score": 0.97},
                        {"index": 0, "relevance_score": 0.94},
                    ]
                }
            )
        ),
        model=settings.JINA_RERANK_MODEL,
    )
    candidate_settings = settings.model_copy(
        update={
            "RETRIEVAL_RERANK_CANDIDATE_TOP_K": 3,
            "RETRIEVAL_FINAL_TOP_K": 2,
        }
    )

    result = query_nodes.jina_rerank_node(
        {
            "prepared_query": "What is pricing?",
            "retrieved_chunks": retrieved_chunks,
            "retrieval_metrics": {},
        },
        settings=candidate_settings,
        jina_client=fake_jina_client,
    )

    assert [chunk["chunk_id"] for chunk in result["reranked_chunks"]] == [
        "chunk-2",
        "chunk-0",
    ]
    assert [chunk["rerank_score"] for chunk in result["reranked_chunks"]] == [
        0.97,
        0.94,
    ]
    assert fake_jina_client.http_client.post_calls[0]["json"]["documents"] == [
        "chunk 0",
        "chunk 1",
        "chunk 2",
    ]
    assert fake_jina_client.http_client.post_calls[0]["json"]["top_n"] == 2
    assert result["retrieval_metrics"] == {
        "rerank_candidate_count": 3,
        "final_reranked_count": 2,
    }


def test_jina_rerank_node_preserves_subquery_covered_candidate_order_before_fallback_sort():
    settings = _test_settings()
    retrieved_chunks = [
        {
            "chunk_id": "chunk-left",
            "document_id": DOC_A,
            "file_name": "alpha.pdf",
            "chunk_index": 0,
            "content": "left coverage",
            "qdrant_score": 0.1,
            "fusion_score": 0.1,
            "keyword_score": 0.1,
            "subquery_ids": ["q1"],
        },
        {
            "chunk_id": "chunk-right",
            "document_id": DOC_A,
            "file_name": "alpha.pdf",
            "chunk_index": 1,
            "content": "right coverage",
            "qdrant_score": 0.9,
            "fusion_score": 0.9,
            "keyword_score": 0.9,
            "subquery_ids": ["q2"],
        },
        {
            "chunk_id": "chunk-bridge",
            "document_id": DOC_A,
            "file_name": "alpha.pdf",
            "chunk_index": 2,
            "content": "bridge coverage",
            "qdrant_score": 0.5,
            "fusion_score": 0.5,
            "keyword_score": 0.5,
            "subquery_ids": ["q1", "q2"],
        },
        {
            "chunk_id": "chunk-ignored",
            "document_id": DOC_A,
            "file_name": "alpha.pdf",
            "chunk_index": 3,
            "content": "ignored tail",
            "qdrant_score": 0.8,
            "fusion_score": 0.8,
            "keyword_score": 0.8,
            "subquery_ids": ["q3"],
        },
    ]
    fake_jina_client = SimpleNamespace(
        http_client=FakeHttpClient(
            response=FakeHttpResponse(
                {
                    "results": [
                        {"index": 1, "relevance_score": 0.9},
                        {"index": 0, "relevance_score": 0.8},
                    ]
                }
            )
        ),
        model=settings.JINA_RERANK_MODEL,
    )
    candidate_settings = settings.model_copy(
        update={
            "RETRIEVAL_RERANK_CANDIDATE_TOP_K": 3,
            "RETRIEVAL_FINAL_TOP_K": 2,
        }
    )

    result = query_nodes.jina_rerank_node(
        {
            "prepared_query": "What is pricing?",
            "retrieved_chunks": retrieved_chunks,
            "retrieval_metrics": {},
        },
        settings=candidate_settings,
        jina_client=fake_jina_client,
    )

    assert fake_jina_client.http_client.post_calls[0]["json"]["documents"] == [
        "left coverage",
        "right coverage",
        "bridge coverage",
    ]
    assert [chunk["chunk_id"] for chunk in result["reranked_chunks"]] == [
        "chunk-right",
        "chunk-left",
    ]
    assert [chunk["rerank_score"] for chunk in result["reranked_chunks"]] == [
        0.9,
        0.8,
    ]
    assert result["retrieval_metrics"] == {
        "rerank_candidate_count": 3,
        "final_reranked_count": 2,
    }


def test_rerank_chunks_falls_back_to_fusion_qdrant_keyword_chunk_id_sort_when_jina_returns_invalid_indexes():
    settings = _test_settings().model_copy(update={"RETRIEVAL_FINAL_TOP_K": 5})
    chunks = [
        {
            "chunk_id": "chunk-a",
            "document_id": DOC_A,
            "file_name": "alpha.pdf",
            "chunk_index": 0,
            "content": "alpha",
            "fusion_score": 0.9,
            "qdrant_score": 0.4,
            "keyword_score": 0.1,
        },
        {
            "chunk_id": "chunk-b",
            "document_id": DOC_A,
            "file_name": "alpha.pdf",
            "chunk_index": 1,
            "content": "beta",
            "fusion_score": 0.9,
            "qdrant_score": 0.4,
            "keyword_score": 0.2,
        },
        {
            "chunk_id": "chunk-c",
            "document_id": DOC_A,
            "file_name": "alpha.pdf",
            "chunk_index": 2,
            "content": "gamma",
            "fusion_score": 0.8,
            "qdrant_score": 0.9,
            "keyword_score": 0.9,
        },
        {
            "chunk_id": "chunk-d",
            "document_id": DOC_A,
            "file_name": "alpha.pdf",
            "chunk_index": 3,
            "content": "delta",
            "qdrant_score": 0.95,
            "keyword_score": 0.3,
        },
        {
            "chunk_id": "chunk-e",
            "document_id": DOC_A,
            "file_name": "alpha.pdf",
            "chunk_index": 4,
            "content": "epsilon",
            "qdrant_score": 0.95,
            "keyword_score": 0.8,
        },
        {
            "chunk_id": "chunk-f",
            "document_id": DOC_A,
            "file_name": "alpha.pdf",
            "chunk_index": 5,
            "content": "zeta",
            "qdrant_score": 0.95,
            "keyword_score": 0.8,
        },
    ]
    jina_client = SimpleNamespace(
        http_client=FakeHttpClient(
            response=FakeHttpResponse(
                {
                    "results": [
                        {"index": 99, "relevance_score": 0.99},
                        {"index": 1, "relevance_score": 0.88},
                    ]
                }
            )
        ),
        model=settings.JINA_RERANK_MODEL,
    )

    results = retrieval.rerank_chunks(
        "What does the document say?",
        chunks,
        settings=settings,
        jina_client=jina_client,
    )

    assert [chunk["chunk_id"] for chunk in results] == [
        "chunk-b",
        "chunk-a",
        "chunk-c",
        "chunk-e",
        "chunk-f",
    ]


def test_query_state_contains_required_fields_and_no_extra_fields():
    hints = get_type_hints(QueryState)

    assert set(hints) == {
        "question",
        "document_ids",
        "save_message",
        "filters",
        "prepared_query",
        "query_embedding",
        "retrieval_hints",
        "query_plan",
        "subqueries",
        "route",
        "relation_document_ids",
        "path_candidates",
        "fused_candidates",
        "retrieved_chunks",
        "reranked_chunks",
        "context_chunks",
        "answer",
        "sources",
        "citation_validation_result",
        "grounding_result",
        "verification_attempt_count",
        "answer_verified",
        "grounding_provider_failed",
        "trace_id",
        "workflow_trace",
        "retrieval_metrics",
        "error_message",
    }
    assert all("prompt" not in field for field in hints)
    assert all("binary" not in field and "bytes" not in field for field in hints)


def test_prepare_query_node_trims_question_and_normalizes_document_ids():
    result = query_nodes.prepare_query_node(
        {
            "question": "  What is pricing?  ",
            "document_ids": [DOC_A, "  ", DOC_A, DOC_B, "DOC-C"],
            "save_message": 1,
        }
    )

    assert result == {
        "question": "What is pricing?",
        "prepared_query": "What is pricing?",
        "document_ids": [DOC_A, DOC_B, "DOC-C"],
        "save_message": True,
    }


def test_prepare_query_node_preserves_explicit_filters_with_empty_fields_normalized():
    result = query_nodes.prepare_query_node(
        {
            "question": "  What is pricing?  ",
            "document_ids": [DOC_A],
            "filters": {
                "mime_types": [" application/pdf ", "", "application/pdf"],
                "heading": "  Pricing  ",
                "section_path": [" Plans ", "", "Enterprise"],
                "page_start": 2,
                "page_end": 5,
            },
        }
    )

    assert result["filters"] == {
        "mime_types": ["application/pdf"],
        "heading": "Pricing",
        "section_path": ["Plans", "Enterprise"],
        "page_start": 2,
        "page_end": 5,
    }


def test_prepare_query_node_returns_validation_error_for_blank_question():
    result = query_nodes.prepare_query_node(
        {
            "question": "   ",
            "document_ids": [DOC_A],
            "save_message": True,
        }
    )

    assert result == {"error_message": "question is required"}


def test_retrieve_qdrant_node_embeds_prepared_query_and_applies_document_filter():
    settings = _test_settings()
    fake_qdrant_client = FakeQdrantClient(
        points=[
            _qdrant_point(
                chunk_id="chunk-a",
                document_id=DOC_A,
                chunk_index=0,
                file_name="alpha.pdf",
                score=0.91,
                text="alpha chunk",
            )
        ]
    )
    fake_shopaikey_client = FakeShopAIKeyClient(vectors=[[0.1, 0.2, 0.3]])

    result = query_nodes.retrieve_qdrant_node(
        {
            "prepared_query": "  What is pricing?  ",
            "document_ids": [DOC_A, DOC_B],
        },
        settings=settings,
        qdrant_client=fake_qdrant_client,
        shopaikey_client=fake_shopaikey_client,
    )

    assert result["prepared_query"] == "What is pricing?"
    assert result["document_ids"] == [DOC_A, DOC_B]
    assert result["query_embedding"] == [0.1, 0.2, 0.3]
    assert [chunk["chunk_id"] for chunk in result["retrieved_chunks"]] == ["chunk-a"]
    assert fake_shopaikey_client.embeddings.calls == [
        (settings.SHOPAIKEY_EMBEDDING_MODEL, ["What is pricing?"])
    ]
    assert fake_qdrant_client.query_calls[0]["collection_name"] == settings.QDRANT_COLLECTION
    assert fake_qdrant_client.query_calls[0]["query_filter"].must[0].key == "document_id"
    assert fake_qdrant_client.query_calls[0]["query_filter"].must[0].match.any == [
        DOC_A,
        DOC_B,
    ]


def test_retrieve_qdrant_node_passes_filters_to_semantic_search(monkeypatch):
    settings = _test_settings()
    captured: dict[str, object] = {}
    fake_shopaikey_client = FakeShopAIKeyClient(vectors=[[0.1, 0.2, 0.3]])

    def _search_semantic_chunks(query_embedding, **kwargs):
        captured["query_embedding"] = query_embedding
        captured.update(kwargs)
        return []

    monkeypatch.setattr(retrieval, "search_semantic_chunks", _search_semantic_chunks)

    result = query_nodes.retrieve_qdrant_node(
        {
            "prepared_query": "What is pricing?",
            "document_ids": [DOC_A],
            "filters": {
                "mime_types": ["application/pdf"],
                "heading": "Pricing",
                "section_path": ["Enterprise"],
                "page_start": 2,
                "page_end": 4,
            },
        },
        settings=settings,
        qdrant_client=FakeQdrantClient(points=[]),
        shopaikey_client=fake_shopaikey_client,
    )

    assert result["filters"] == {
        "mime_types": ["application/pdf"],
        "heading": "Pricing",
        "section_path": ["Enterprise"],
        "page_start": 2,
        "page_end": 4,
    }
    assert captured["document_ids"] == [DOC_A]
    assert captured["filters"] == result["filters"]


def test_retrieve_qdrant_node_uses_hybrid_retrieval_when_keyword_enabled(monkeypatch):
    settings = _test_settings(enable_keyword_search=True)
    captured: dict[str, object] = {}

    def _retrieve_hybrid_chunks(question, **kwargs):
        captured["question"] = question
        captured.update(kwargs)
        return {
            "query_embedding": [0.1, 0.2, 0.3],
            "path_candidates": {
                "semantic": [],
                "keyword": [
                    {
                        "chunk_id": "keyword-a",
                        "document_id": DOC_A,
                        "file_name": "alpha.pdf",
                        "chunk_index": 0,
                        "content": "keyword chunk",
                        "keyword_rank": 1,
                        "keyword_score": 0.7,
                        "retrieval_paths": ["keyword"],
                    }
                ],
            },
            "retrieved_chunks": [
                {
                    "chunk_id": "keyword-a",
                    "document_id": DOC_A,
                    "file_name": "alpha.pdf",
                    "chunk_index": 0,
                    "content": "keyword chunk",
                    "keyword_rank": 1,
                    "keyword_score": 0.7,
                    "retrieval_paths": ["keyword"],
                    "fusion_score": 1 / 61,
                }
            ],
            "retrieval_metrics": {
                "semantic_candidate_count": 0,
                "keyword_candidate_count": 1,
                "fused_candidate_count": 1,
                "fallback_path": None,
            },
        }

    monkeypatch.setattr(retrieval, "retrieve_hybrid_chunks", _retrieve_hybrid_chunks)

    result = query_nodes.retrieve_qdrant_node(
        {
            "prepared_query": "What is pricing?",
            "document_ids": [DOC_A],
        },
        settings=settings,
        qdrant_client=object(),
        shopaikey_client=object(),
    )

    assert captured["question"] == "What is pricing?"
    assert captured["document_ids"] == [DOC_A]
    assert captured["settings"] == settings
    assert result["path_candidates"]["keyword"][0]["chunk_id"] == "keyword-a"
    assert result["retrieved_chunks"][0]["retrieval_paths"] == ["keyword"]
    assert result["retrieval_metrics"]["fused_candidate_count"] == 1


def test_jina_rerank_node_uses_prepared_query_and_returns_reranked_chunks():
    settings = _test_settings()
    retrieved_chunks = [
        {
            "chunk_id": "chunk-a",
            "document_id": DOC_A,
            "file_name": "alpha.pdf",
            "chunk_index": 0,
            "content": "alpha",
            "qdrant_score": 0.4,
        },
        {
            "chunk_id": "chunk-b",
            "document_id": DOC_A,
            "file_name": "alpha.pdf",
            "chunk_index": 1,
            "content": "beta",
            "qdrant_score": 0.9,
        },
    ]
    fake_jina_client = SimpleNamespace(
        http_client=FakeHttpClient(
            response=FakeHttpResponse(
                {
                    "results": [
                        {"index": 1, "relevance_score": 0.99},
                        {"index": 0, "relevance_score": 0.88},
                    ]
                }
            )
        ),
        model=settings.JINA_RERANK_MODEL,
    )

    result = query_nodes.jina_rerank_node(
        {
            "prepared_query": "What is pricing?",
            "retrieved_chunks": retrieved_chunks,
        },
        settings=settings,
        jina_client=fake_jina_client,
    )

    assert [chunk["chunk_id"] for chunk in result["reranked_chunks"]] == [
        "chunk-b",
        "chunk-a",
    ]
    assert fake_jina_client.http_client.post_calls[0]["json"]["query"] == "What is pricing?"
    assert fake_jina_client.http_client.post_calls[0]["json"]["top_n"] == 2


def test_expand_neighbor_context_node_adds_neighbors_and_deduplicates():
    settings = _test_settings(context_mode="neighbor")
    fake_client = FakeSupabaseClient(
        tables={
            "document_chunks": [
                {
                    "id": "chunk-1",
                    "document_id": DOC_A,
                    "chunk_index": 1,
                    "content": "neighbor one",
                    "file_name": "alpha.pdf",
                },
                {
                    "id": "chunk-3",
                    "document_id": DOC_A,
                    "chunk_index": 3,
                    "content": "neighbor three",
                    "file_name": "alpha.pdf",
                },
                {
                    "id": "chunk-5",
                    "document_id": DOC_A,
                    "chunk_index": 5,
                    "content": "neighbor five",
                    "file_name": "alpha.pdf",
                },
            ]
        }
    )
    reranked_chunks = [
        {
            "chunk_id": "chunk-2",
            "document_id": DOC_A,
            "file_name": "alpha.pdf",
            "chunk_index": 2,
            "content": "chunk two",
            "qdrant_score": 0.95,
            "rerank_score": 0.99,
        },
        {
            "chunk_id": "chunk-4",
            "document_id": DOC_A,
            "file_name": "alpha.pdf",
            "chunk_index": 4,
            "content": "chunk four",
            "qdrant_score": 0.9,
            "rerank_score": 0.98,
        },
    ]

    result = query_nodes.expand_neighbor_context_node(
        {
            "reranked_chunks": reranked_chunks,
        },
        settings=settings,
        supabase_client=fake_client,
    )

    assert [chunk["chunk_id"] for chunk in result["context_chunks"]] == [
        "chunk-2",
        "chunk-4",
        "chunk-1",
        "chunk-3",
        "chunk-5",
    ]
    assert len(result["context_chunks"]) <= settings.RETRIEVAL_CONTEXT_MAX_CANDIDATES
    assert len({chunk["chunk_id"] for chunk in result["context_chunks"]}) == len(
        result["context_chunks"]
    )


def test_expand_neighbor_context_node_records_context_budget_metrics():
    settings = _test_settings(context_mode="neighbor").model_copy(
        update={"RETRIEVAL_CONTEXT_MAX_TOKENS": 4}
    )
    reranked_chunks = [
        {
            "chunk_id": "chunk-a",
            "document_id": DOC_A,
            "file_name": "alpha.pdf",
            "chunk_index": 2,
            "content": "anchor",
            "token_count": 3,
            "subquery_ids": ["left"],
        },
        {
            "chunk_id": "chunk-b",
            "document_id": DOC_A,
            "file_name": "alpha.pdf",
            "chunk_index": 6,
            "content": "second anchor",
            "token_count": 2,
            "subquery_ids": ["right"],
        },
    ]
    fake_client = FakeSupabaseClient(
        tables={
            "document_chunks": [
                {
                    "id": "neighbor-a",
                    "document_id": DOC_A,
                    "chunk_index": 1,
                    "content": "neighbor a",
                    "token_count": 1,
                    "file_name": "alpha.pdf",
                },
                {
                    "id": "neighbor-b",
                    "document_id": DOC_A,
                    "chunk_index": 3,
                    "content": "neighbor b",
                    "token_count": 1,
                    "file_name": "alpha.pdf",
                },
            ]
        }
    )

    result = query_nodes.expand_neighbor_context_node(
        {
            "reranked_chunks": reranked_chunks,
            "retrieval_metrics": {"existing_metric": 7},
        },
        settings=settings,
        supabase_client=fake_client,
    )

    assert [chunk["chunk_id"] for chunk in result["context_chunks"]] == [
        "chunk-a",
        "neighbor-a",
    ]
    assert result["retrieval_metrics"] == {
        "existing_metric": 7,
        "context_token_count": 4,
        "context_candidate_count": 2,
        "context_neighbor_count": 1,
        "context_subquery_coverage": {
            "left": 1,
            "right": 0,
        },
    }


def test_generate_answer_node_builds_sources_and_uses_only_context():
    settings = _test_settings()
    long_content = ("Pricing is based on usage tiers. " * 10).strip()
    context_chunks = [
        {
            "document_id": DOC_A,
            "chunk_id": "chunk-1",
            "file_name": "alpha.pdf",
            "chunk_index": 1,
            "page_start": 3,
            "page_end": 4,
            "heading": "Pricing",
            "section_path": ["Pricing", "Tier 1"],
            "qdrant_score": 0.91,
            "rerank_score": 0.99,
            "content": long_content,
        },
        {
            "document_id": DOC_A,
            "chunk_id": "chunk-2",
            "file_name": "alpha.pdf",
            "chunk_index": 2,
            "page_start": 5,
            "page_end": 5,
            "heading": None,
            "section_path": ["Pricing", "Enterprise"],
            "is_neighbor_context": True,
            "qdrant_score": 0.87,
            "rerank_score": 0.95,
            "content": "Enterprise pricing is custom.",
        },
    ]
    fake_client = FakeShopAIKeyClient(
        chat_response=SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content="Pricing is based on usage tiers, with custom enterprise pricing."
                    )
                )
            ]
        )
    )

    result = query_nodes.generate_answer_node(
        {
            "question": "What does the document say about pricing?",
            "context_chunks": context_chunks,
        },
        settings=settings,
        shopaikey_client=fake_client,
    )

    assert result["answer"] == (
        "Pricing is based on usage tiers, with custom enterprise pricing."
    )
    assert len(result["sources"]) == 2
    assert {
        "document_id",
        "chunk_id",
        "file_name",
        "chunk_index",
        "page_start",
        "page_end",
        "heading",
        "section_path",
        "content_preview",
        "is_neighbor_context",
        "qdrant_score",
        "rerank_score",
        "citation_key",
    } == set(result["sources"][0])
    assert result["sources"][0]["section_path"] == ["Pricing", "Tier 1"]
    assert result["sources"][0]["content_preview"] == long_content[:240]
    assert result["sources"][0]["is_neighbor_context"] is False
    assert result["sources"][1]["section_path"] == ["Pricing", "Enterprise"]
    assert result["sources"][1]["content_preview"] == "Enterprise pricing is custom."
    assert result["sources"][1]["is_neighbor_context"] is True

    chat_call = fake_client.chat.completions.calls[0]
    assert chat_call["model"] == settings.SHOPAIKEY_CHAT_MODEL
    assert chat_call["temperature"] == settings.TEMPERATURE
    assert chat_call["max_tokens"] == settings.MAX_OUTPUT_TOKENS
    assert chat_call["messages"][0]["content"] == query_nodes.ANSWER_SYSTEM_PROMPT
    assert "Context:\n" in chat_call["messages"][1]["content"]
    assert "Question:\nWhat does the document say about pricing?" in chat_call["messages"][1][
        "content"
    ]
    assert "Pricing is based on usage tiers." in chat_call["messages"][1]["content"]
    assert "Enterprise pricing is custom." in chat_call["messages"][1]["content"]
    assert "Citation key: S1" in chat_call["messages"][1]["content"]
    assert "Chunk ID: chunk-1" in chat_call["messages"][1]["content"]
    assert "Citation key: S2" in chat_call["messages"][1]["content"]
    assert chat_call["messages"][1]["content"].endswith(
        "Answer using only the context and cite factual claims with [S<number>] source keys."
    )


def test_validate_citations_node_filters_sources_to_cited_context_chunks():
    settings = _test_settings()
    result = query_nodes.validate_citations_node(
        {
            "answer": "Enterprise pricing is custom [S2]. Usage pricing applies [S1].",
            "context_chunks": [
                {
                    "document_id": DOC_A,
                    "chunk_id": "chunk-1",
                    "file_name": "alpha.pdf",
                    "chunk_index": 1,
                    "content": "Usage pricing applies.",
                },
                {
                    "document_id": DOC_A,
                    "chunk_id": "chunk-2",
                    "file_name": "alpha.pdf",
                    "chunk_index": 2,
                    "content": "Enterprise pricing is custom.",
                },
                {
                    "document_id": DOC_B,
                    "chunk_id": "chunk-3",
                    "file_name": "bravo.pdf",
                    "chunk_index": 3,
                    "content": "Uncited context.",
                },
            ],
        },
        settings=settings,
    )

    assert result["citation_validation_result"].valid is True
    assert result["citation_validation_result"].cited_keys == ["S2", "S1"]
    assert result["citation_validation_result"].cited_chunk_ids == ["chunk-2", "chunk-1"]
    assert [source["chunk_id"] for source in result["sources"]] == ["chunk-2", "chunk-1"]


def test_validate_citations_node_rejects_substitute_labels_without_valid_marker():
    settings = _test_settings()
    result = query_nodes.validate_citations_node(
        {
            "answer": f"Usage pricing applies according to document {DOC_A} and the Pricing heading.",
            "context_chunks": [
                {
                    "document_id": DOC_A,
                    "chunk_id": "chunk-1",
                    "file_name": "alpha.pdf",
                    "chunk_index": 1,
                    "heading": "Pricing",
                    "content": "Usage pricing applies.",
                }
            ],
        },
        settings=settings,
    )

    assert result["citation_validation_result"].valid is False
    assert result["citation_validation_result"].missing_citations is True
    assert result["sources"] == []


def test_verify_grounding_node_accepts_only_valid_citations_and_grounding_threshold(monkeypatch):
    settings = _test_settings()
    settings.GROUNDING_MIN_SCORE = 0.8
    calls: list[dict[str, object]] = []

    def _verify(answer, *, evidence, settings=None, shopaikey_client=None):
        calls.append({"answer": answer, "evidence": evidence})
        return GroundingResult(
            grounded=True,
            score=0.92,
            unsupported_claims=[],
            missing_citations=[],
        )

    monkeypatch.setattr(query_nodes.grounding, "verify_answer_grounding", _verify)

    result = query_nodes.verify_grounding_node(
        {
            "answer": "Pricing is usage based [S1].",
            "context_chunks": [
                {
                    "document_id": DOC_A,
                    "chunk_id": "chunk-1",
                    "file_name": "alpha.pdf",
                    "chunk_index": 1,
                    "content": "Pricing is usage based.",
                },
                {
                    "document_id": DOC_A,
                    "chunk_id": "chunk-2",
                    "file_name": "alpha.pdf",
                    "chunk_index": 2,
                    "content": "Uncited content.",
                },
            ],
            "citation_validation_result": CitationValidationResult(
                valid=True,
                cited_keys=["S1"],
                cited_chunk_ids=["chunk-1"],
            ),
            "sources": [
                {
                    "document_id": DOC_A,
                    "chunk_id": "chunk-1",
                    "file_name": "alpha.pdf",
                    "chunk_index": 1,
                    "citation_key": "S1",
                }
            ],
        },
        settings=settings,
    )

    assert result["grounding_result"].grounded is True
    assert result["answer_verified"] is True
    assert calls == [
        {
            "answer": "Pricing is usage based [S1].",
            "evidence": [
                {
                    "citation_key": "S1",
                    "chunk_id": "chunk-1",
                    "text": "Pricing is usage based.",
                }
            ],
        }
    ]


def test_verify_grounding_node_fails_closed_on_provider_failure(monkeypatch):
    settings = _test_settings()

    def _verify(*args, **kwargs):
        raise query_nodes.grounding.GroundingProviderError("provider down")

    monkeypatch.setattr(query_nodes.grounding, "verify_answer_grounding", _verify)

    result = query_nodes.verify_grounding_node(
        {
            "answer": "Pricing is usage based [S1].",
            "context_chunks": [
                {
                    "document_id": DOC_A,
                    "chunk_id": "chunk-1",
                    "file_name": "alpha.pdf",
                    "chunk_index": 1,
                    "content": "Pricing is usage based.",
                }
            ],
            "citation_validation_result": CitationValidationResult(
                valid=True,
                cited_keys=["S1"],
                cited_chunk_ids=["chunk-1"],
            ),
            "sources": [
                {
                    "document_id": DOC_A,
                    "chunk_id": "chunk-1",
                    "file_name": "alpha.pdf",
                    "chunk_index": 1,
                    "citation_key": "S1",
                }
            ],
        },
        settings=settings,
    )

    assert result["answer_verified"] is False
    assert result["grounding_provider_failed"] is True


def test_finalize_answer_node_replaces_unverified_draft_with_safe_response():
    result = query_nodes.finalize_answer_node(
        {
            "answer": "Unsupported draft [S1].",
            "sources": [{"chunk_id": "chunk-1"}],
            "answer_verified": False,
        }
    )

    assert result == {
        "answer": query_nodes.SAFE_INSUFFICIENT_CONTEXT_MESSAGE,
        "sources": [],
    }


def test_generate_answer_node_uses_truncated_prompt_copy_without_changing_source_preview():
    settings = _test_settings()
    full_content = "Alpha Beta Gamma Delta Epsilon Zeta Eta Theta"
    fake_client = FakeShopAIKeyClient(
        chat_response=SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="Answer"))]
        )
    )

    result = query_nodes.generate_answer_node(
        {
            "question": "What matters here?",
            "context_chunks": [
                {
                    "document_id": DOC_A,
                    "chunk_id": "chunk-1",
                    "file_name": "alpha.pdf",
                    "chunk_index": 1,
                    "heading": "Pricing",
                    "section_path": ["Pricing"],
                    "content": full_content,
                    "prompt_content": "Alpha Beta",
                    "context_truncated": True,
                    "token_count": 99,
                }
            ],
        },
        settings=settings,
        shopaikey_client=fake_client,
    )

    chat_call = fake_client.chat.completions.calls[0]
    assert "Alpha Beta\n\n" in chat_call["messages"][1]["content"]
    assert full_content not in chat_call["messages"][1]["content"]
    assert result["sources"][0]["content_preview"] == full_content
    assert "context_truncated" not in result["sources"][0]


def test_source_citation_preview_uses_shared_limit():
    long_content = "x" * 300
    citation = query_nodes._build_source_citations(
        [
            {
                "document_id": DOC_A,
                "chunk_id": "chunk-1",
                "chunk_index": 0,
                "content": long_content,
            }
        ]
    )[0]

    assert citation["content_preview"] == "x" * 240


def test_source_citations_carry_optional_phase3_metadata_without_dropping_phase2_fields():
    from app.graphs import query_formatting

    citations = query_formatting.build_source_citations(
        [
            {
                "document_id": DOC_A,
                "chunk_id": "chunk-1",
                "chunk_index": 7,
                "file_name": "alpha.pdf",
                "content": "Pricing is based on usage tiers.",
                "heading": "Pricing",
                "section_path": ["Pricing", "Tier 1"],
                "qdrant_score": 0.91,
                "rerank_score": 0.99,
                "fusion_score": 0.73,
                "retrieval_paths": [
                    "semantic",
                    "keyword",
                ],
                "citation_key": "S1",
            }
        ]
    )

    assert citations == [
        {
            "document_id": DOC_A,
            "chunk_id": "chunk-1",
            "file_name": "alpha.pdf",
            "chunk_index": 7,
            "page_start": None,
            "page_end": None,
            "heading": "Pricing",
            "qdrant_score": 0.91,
            "rerank_score": 0.99,
            "section_path": ["Pricing", "Tier 1"],
            "content_preview": "Pricing is based on usage tiers.",
            "is_neighbor_context": False,
            "fusion_score": 0.73,
            "retrieval_paths": ["semantic", "keyword"],
            "citation_key": "S1",
        }
    ]


def test_query_formatting_exposes_cross_module_helpers_as_public_api():
    from app.graphs import query_formatting

    assert query_formatting.normalize_text("  value  ") == "value"
    assert query_formatting.resolve_context_chunks(
        {"context_chunks": [{"chunk_id": "chunk-1"}]}
    ) == [{"chunk_id": "chunk-1"}]
    assert callable(query_formatting.build_context_prompt)
    assert callable(query_formatting.build_source_citations)
    assert callable(query_formatting.extract_chat_content)
    assert callable(query_formatting.message_metadata)


def test_create_message_passes_custom_settings_to_client_factory(monkeypatch):
    settings = _test_settings()
    fake_client = FakeSupabaseClient(tables={"messages": []})
    received_settings: list[Settings | None] = []

    def _create_client(client_settings=None):
        received_settings.append(client_settings)
        return fake_client

    monkeypatch.setattr(message_service, "create_supabase_client", _create_client)

    message_service.create_message(
        question="What is pricing?",
        answer="Pricing is based on usage tiers.",
        sources=[],
        metadata={},
        settings=settings,
    )

    assert received_settings == [settings]


def test_save_message_optional_node_delegates_to_message_service(monkeypatch):
    settings = _test_settings()
    fake_client = FakeSupabaseClient(tables={"messages": []})
    calls: list[dict[str, object]] = []

    def _create_message(**kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(query_nodes.message_service, "create_message", _create_message)

    result = query_nodes.save_message_optional_node(
        {
            "question": "What is pricing?",
            "prepared_query": "What is pricing?",
            "answer": "Pricing is based on usage tiers.",
            "sources": [{"document_id": DOC_A, "chunk_id": "chunk-1"}],
            "save_message": True,
            "document_ids": [DOC_A],
            "context_chunks": [{"chunk_id": "chunk-1"}],
        },
        settings=settings,
        supabase_client=fake_client,
    )

    assert result == {}
    assert calls == [
        {
            "question": "What is pricing?",
            "answer": "Pricing is based on usage tiers.",
            "sources": [{"document_id": DOC_A, "chunk_id": "chunk-1"}],
            "metadata": {
                "document_ids": [DOC_A],
                "prepared_query": "What is pricing?",
                "retrieved_chunk_count": 0,
                "reranked_chunk_count": 0,
                "context_chunk_count": 1,
            },
            "settings": settings,
            "supabase_client": fake_client,
        }
    ]


def test_save_message_optional_node_inserts_question_answer_sources_and_metadata():
    settings = _test_settings()
    fake_client = FakeSupabaseClient(tables={"messages": []})
    sources = [
        {
            "document_id": DOC_A,
            "chunk_id": "chunk-1",
            "file_name": "alpha.pdf",
            "chunk_index": 1,
            "page_start": 3,
            "page_end": 4,
            "heading": "Pricing",
            "section_path": ["Pricing", "Tier 1"],
            "content_preview": "Pricing is based on usage tiers.",
            "is_neighbor_context": True,
            "qdrant_score": 0.91,
            "rerank_score": 0.99,
        }
    ]

    result = query_nodes.save_message_optional_node(
        {
            "question": "What does the document say about pricing?",
            "prepared_query": "What does the document say about pricing?",
            "answer": "Pricing is based on usage tiers.",
            "sources": sources,
            "save_message": True,
            "document_ids": [DOC_A],
            "context_chunks": [
                {
                    "document_id": DOC_A,
                    "chunk_id": "chunk-1",
                    "file_name": "alpha.pdf",
                    "chunk_index": 1,
                    "page_start": 3,
                    "page_end": 4,
                    "heading": "Pricing",
                    "section_path": ["Pricing", "Tier 1"],
                    "is_neighbor_context": True,
                    "qdrant_score": 0.91,
                    "rerank_score": 0.99,
                    "content": "Pricing is based on usage tiers.",
                }
            ],
            "retrieved_chunks": [
                {
                    "document_id": DOC_A,
                    "chunk_id": "chunk-1",
                    "file_name": "alpha.pdf",
                    "chunk_index": 1,
                    "page_start": 3,
                    "page_end": 4,
                    "heading": "Pricing",
                    "section_path": ["Pricing", "Tier 1"],
                    "is_neighbor_context": True,
                    "qdrant_score": 0.91,
                    "rerank_score": 0.99,
                    "content": "Pricing is based on usage tiers.",
                }
            ],
        },
        settings=settings,
        supabase_client=fake_client,
    )

    assert result == {}
    assert len(fake_client.tables["messages"]) == 1
    saved_row = fake_client.tables["messages"][0]
    assert saved_row["question"] == "What does the document say about pricing?"
    assert saved_row["answer"] == "Pricing is based on usage tiers."
    assert saved_row["sources"] == sources
    assert saved_row["metadata"]["document_ids"] == [DOC_A]
    assert saved_row["metadata"]["prepared_query"] == "What does the document say about pricing?"
    assert saved_row["metadata"]["context_chunk_count"] == 1


def test_save_message_optional_node_uses_validated_empty_sources_without_context_fallback():
    settings = _test_settings()
    fake_client = FakeSupabaseClient(tables={"messages": []})

    result = query_nodes.save_message_optional_node(
        {
            "question": "What does the document say about pricing?",
            "prepared_query": "What does the document say about pricing?",
            "answer": "Pricing is based on usage tiers.",
            "sources": [],
            "save_message": True,
            "document_ids": [DOC_A],
            "context_chunks": [
                {
                    "document_id": DOC_A,
                    "chunk_id": "chunk-1",
                    "file_name": "alpha.pdf",
                    "chunk_index": 1,
                    "content": "Pricing is based on usage tiers.",
                }
            ],
            "citation_validation_result": {
                "valid": False,
                "cited_keys": [],
                "cited_chunk_ids": [],
                "invalid_keys": [],
                "missing_citations": True,
            },
        },
        settings=settings,
        supabase_client=fake_client,
    )

    assert result == {}
    saved_row = fake_client.tables["messages"][0]
    assert saved_row["sources"] == []
    assert saved_row["metadata"]["citation_validation_result"] == {
        "valid": False,
        "cited_keys": [],
        "cited_chunk_ids": [],
        "invalid_keys": [],
        "missing_citations": True,
    }


def test_save_message_optional_node_ignores_insert_failure():
    settings = _test_settings()

    class FailingMessagesQuery:
        def insert(self, *args, **kwargs):
            return self

        def execute(self):
            raise RuntimeError("messages unavailable")

    class FailingMessagesClient:
        def table(self, table_name: str):
            assert table_name == "messages"
            return FailingMessagesQuery()

    result = query_nodes.save_message_optional_node(
        {
            "question": "What does the document say about pricing?",
            "prepared_query": "What does the document say about pricing?",
            "answer": "Pricing is based on usage tiers.",
            "save_message": True,
            "document_ids": [DOC_A],
            "context_chunks": [],
        },
        settings=settings,
        supabase_client=FailingMessagesClient(),
    )

    assert result == {}


def test_build_query_graph_invokes_nodes_in_required_order(monkeypatch):
    settings = _test_settings()
    call_order: list[str] = []

    def _record_node(node_name: str, output: dict[str, object]):
        def _node(state, **kwargs):
            call_order.append(node_name)
            return output

        return _node

    monkeypatch.setattr(
        query_nodes,
        "prepare_query_node",
        _record_node(
            "prepare_query",
            {
                "question": "What does the document say about pricing?",
                "prepared_query": "What does the document say about pricing?",
                "document_ids": [DOC_A],
                "save_message": True,
            },
        ),
    )
    monkeypatch.setattr(
        query_nodes,
        "plan_query_node",
        _record_node(
            "plan_query",
            {
                "query_plan": QueryPlan(
                    is_complex=False,
                    strategy=RetrievalStrategy.SEMANTIC,
                    subqueries=[
                        QuerySubquery(
                            id="q1",
                            text="What does the document say about pricing?",
                        )
                    ],
                    inferred_filters=RetrievalFilters(),
                    needs_relations=False,
                ),
                "subqueries": [
                    QuerySubquery(
                        id="q1",
                        text="What does the document say about pricing?",
                    )
                ],
                "route": RetrievalStrategy.SEMANTIC,
            },
        ),
        raising=False,
    )
    monkeypatch.setattr(
        query_nodes,
        "resolve_relation_scope_node",
        _record_node(
            "resolve_relation_scope",
            {
                "document_ids": [DOC_A],
            },
        ),
        raising=False,
    )
    monkeypatch.setattr(
        query_nodes,
        "retrieve_candidates_node",
        _record_node(
            "retrieve_candidates",
            {
                "path_candidates": {
                    "q1:semantic": [
                        {
                            "document_id": DOC_A,
                            "chunk_id": "chunk-1",
                            "file_name": "alpha.pdf",
                            "chunk_index": 1,
                            "page_start": 3,
                            "page_end": 4,
                            "heading": "Pricing",
                            "qdrant_score": 0.91,
                            "semantic_rank": 1,
                            "content": "Pricing is based on usage tiers.",
                            "retrieval_paths": [RetrievalPath.SEMANTIC],
                            "subquery_ids": ["q1"],
                        }
                    ]
                },
            },
        ),
        raising=False,
    )
    monkeypatch.setattr(
        query_nodes,
        "fuse_candidates_node",
        _record_node(
            "fuse_candidates",
            {
                "fused_candidates": [
                    {
                        "document_id": DOC_A,
                        "chunk_id": "chunk-1",
                        "file_name": "alpha.pdf",
                        "chunk_index": 1,
                        "page_start": 3,
                        "page_end": 4,
                        "heading": "Pricing",
                        "qdrant_score": 0.91,
                        "fusion_score": 0.5,
                        "content": "Pricing is based on usage tiers.",
                    }
                ],
                "retrieved_chunks": [
                    {
                        "document_id": DOC_A,
                        "chunk_id": "chunk-1",
                        "file_name": "alpha.pdf",
                        "chunk_index": 1,
                        "page_start": 3,
                        "page_end": 4,
                        "heading": "Pricing",
                        "qdrant_score": 0.91,
                        "content": "Pricing is based on usage tiers.",
                    }
                ],
            },
        ),
        raising=False,
    )
    monkeypatch.setattr(
        query_nodes,
        "rerank_candidates_node",
        _record_node(
            "rerank_candidates",
            {
                "reranked_chunks": [
                    {
                        "document_id": DOC_A,
                        "chunk_id": "chunk-1",
                        "file_name": "alpha.pdf",
                        "chunk_index": 1,
                        "page_start": 3,
                        "page_end": 4,
                        "heading": "Pricing",
                        "qdrant_score": 0.91,
                        "rerank_score": 0.99,
                        "content": "Pricing is based on usage tiers.",
                    }
                ]
            },
        ),
        raising=False,
    )
    monkeypatch.setattr(
        query_nodes,
        "expand_context_node",
        _record_node(
            "expand_context",
            {
                "context_chunks": [
                    {
                        "document_id": DOC_A,
                        "chunk_id": "chunk-1",
                        "file_name": "alpha.pdf",
                        "chunk_index": 1,
                        "page_start": 3,
                        "page_end": 4,
                        "heading": "Pricing",
                        "qdrant_score": 0.91,
                        "rerank_score": 0.99,
                        "content": "Pricing is based on usage tiers.",
                    }
                ]
            },
        ),
        raising=False,
    )
    monkeypatch.setattr(
        query_nodes,
        "generate_answer_node",
        _record_node(
            "generate_answer",
            {
                "answer": "Pricing is based on usage tiers.",
                "sources": [
                    {
                        "document_id": DOC_A,
                        "chunk_id": "chunk-1",
                        "file_name": "alpha.pdf",
                        "chunk_index": 1,
                        "page_start": 3,
                        "page_end": 4,
                        "heading": "Pricing",
                        "qdrant_score": 0.91,
                        "rerank_score": 0.99,
                    }
                ],
            },
        ),
    )
    monkeypatch.setattr(
        query_nodes,
        "validate_citations_node",
        _record_node("validate_citations", {}),
        raising=False,
    )
    monkeypatch.setattr(
        query_nodes,
        "verify_grounding_node",
        _record_node("verify_grounding", {}),
        raising=False,
    )
    monkeypatch.setattr(
        query_nodes,
        "finalize_answer_node",
        _record_node("finalize_answer", {}),
        raising=False,
    )
    monkeypatch.setattr(
        query_nodes,
        "save_message_optional_node",
        _record_node("save_message_optional", {}),
    )

    graph = build_query_graph(settings=settings)
    result = graph.invoke(
        {
            "question": "  What does the document say about pricing?  ",
            "document_ids": [DOC_A],
            "save_message": True,
        }
    )

    assert call_order == [
        "prepare_query",
        "plan_query",
        "resolve_relation_scope",
        "retrieve_candidates",
        "fuse_candidates",
        "rerank_candidates",
        "expand_context",
        "generate_answer",
        "validate_citations",
        "verify_grounding",
        "finalize_answer",
        "save_message_optional",
    ]
    assert result["answer"] == "Pricing is based on usage tiers."
    assert result["sources"][0]["chunk_id"] == "chunk-1"
    assert [event["node_name"] for event in result["workflow_trace"]] == call_order
    assert all(event["attempt"] == 1 for event in result["workflow_trace"])
    assert all("duration_ms" in event for event in result["workflow_trace"])
    assert "Pricing is based on usage tiers" not in str(result["workflow_trace"])


def test_build_query_graph_regenerates_once_then_persists_only_verified_answer(monkeypatch):
    settings = _test_settings()
    settings.GROUNDING_MAX_REGENERATIONS = 1
    call_order: list[str] = []
    answers = [
        "Unsupported draft [S1].",
        "Pricing is based on usage tiers [S1].",
    ]
    saved: list[dict[str, object]] = []
    verify_attempts = 0

    def _record(node_name: str, output: dict[str, object]):
        def _node(state, **kwargs):
            call_order.append(node_name)
            return output

        return _node

    monkeypatch.setattr(
        query_nodes,
        "prepare_query_node",
        _record(
            "prepare_query",
            {
                "question": "What is pricing?",
                "prepared_query": "What is pricing?",
                "document_ids": [DOC_A],
                "save_message": True,
            },
        ),
    )
    monkeypatch.setattr(
        query_nodes,
        "plan_query_node",
        _record(
            "plan_query",
            {
                "query_plan": QueryPlan(
                    is_complex=False,
                    strategy=RetrievalStrategy.SEMANTIC,
                    subqueries=[QuerySubquery(id="q1", text="What is pricing?")],
                    inferred_filters=RetrievalFilters(),
                    needs_relations=False,
                ),
                "subqueries": [QuerySubquery(id="q1", text="What is pricing?")],
                "route": RetrievalStrategy.SEMANTIC,
            },
        ),
    )
    monkeypatch.setattr(query_nodes, "resolve_relation_scope_node", _record("resolve_relation_scope", {"relation_document_ids": [DOC_A]}))
    monkeypatch.setattr(query_nodes, "retrieve_candidates_node", _record("retrieve_candidates", {"path_candidates": {"q1:semantic": []}, "retrieved_chunks": []}))
    monkeypatch.setattr(query_nodes, "fuse_candidates_node", _record("fuse_candidates", {"fused_candidates": [], "retrieved_chunks": []}))
    monkeypatch.setattr(
        query_nodes,
        "rerank_candidates_node",
        _record(
            "rerank_candidates",
            {
                "reranked_chunks": [
                    {
                        "document_id": DOC_A,
                        "chunk_id": "chunk-1",
                        "file_name": "alpha.pdf",
                        "chunk_index": 1,
                        "content": "Pricing is based on usage tiers.",
                    }
                ]
            },
        ),
    )
    monkeypatch.setattr(
        query_nodes,
        "expand_context_node",
        _record(
            "expand_context",
            {
                "context_chunks": [
                    {
                        "document_id": DOC_A,
                        "chunk_id": "chunk-1",
                        "file_name": "alpha.pdf",
                        "chunk_index": 1,
                        "content": "Pricing is based on usage tiers.",
                    }
                ]
            },
        ),
    )

    def _generate(state, **kwargs):
        call_order.append("generate_answer")
        return {"answer": answers.pop(0), "sources": []}

    def _verify(state, **kwargs):
        nonlocal verify_attempts
        verify_attempts += 1
        call_order.append("verify_grounding")
        verified = state["answer"].startswith("Pricing")
        return {
            "grounding_result": GroundingResult(
                grounded=verified,
                score=0.95 if verified else 0.2,
                unsupported_claims=[] if verified else ["Unsupported draft"],
                missing_citations=[],
            ),
            "answer_verified": verified,
            "verification_attempt_count": verify_attempts,
        }

    def _save(state, **kwargs):
        call_order.append("save_message_optional")
        saved.append({"answer": state["answer"], "sources": state["sources"]})
        return {}

    monkeypatch.setattr(query_nodes, "generate_answer_node", _generate)
    monkeypatch.setattr(query_nodes, "regenerate_answer_node", _generate, raising=False)
    monkeypatch.setattr(query_nodes, "verify_grounding_node", _verify)
    monkeypatch.setattr(query_nodes, "save_message_optional_node", _save)

    result = build_query_graph(settings=settings).invoke(
        {"question": "What is pricing?", "document_ids": [DOC_A], "save_message": True}
    )

    assert call_order == [
        "prepare_query",
        "plan_query",
        "resolve_relation_scope",
        "retrieve_candidates",
        "fuse_candidates",
        "rerank_candidates",
        "expand_context",
        "generate_answer",
        "verify_grounding",
        "generate_answer",
        "verify_grounding",
        "save_message_optional",
    ]
    assert result["answer"] == "Pricing is based on usage tiers [S1]."
    assert "Unsupported draft" not in result["answer"]
    assert saved[0]["answer"] == "Pricing is based on usage tiers [S1]."
    assert saved[0]["sources"][0]["chunk_id"] == "chunk-1"


def test_build_query_graph_repeated_grounding_failure_returns_safe_response_without_draft(monkeypatch):
    settings = _test_settings()
    settings.GROUNDING_MAX_REGENERATIONS = 1

    def _node(output):
        return lambda state, **kwargs: output

    monkeypatch.setattr(query_nodes, "prepare_query_node", _node({"question": "What is pricing?", "prepared_query": "What is pricing?", "document_ids": [DOC_A], "save_message": True}))
    monkeypatch.setattr(query_nodes, "plan_query_node", _node({"query_plan": QueryPlan(is_complex=False, strategy=RetrievalStrategy.SEMANTIC, subqueries=[QuerySubquery(id="q1", text="What is pricing?")], inferred_filters=RetrievalFilters(), needs_relations=False), "subqueries": [QuerySubquery(id="q1", text="What is pricing?")], "route": RetrievalStrategy.SEMANTIC}))
    monkeypatch.setattr(query_nodes, "resolve_relation_scope_node", _node({"relation_document_ids": [DOC_A]}))
    monkeypatch.setattr(query_nodes, "retrieve_candidates_node", _node({"path_candidates": {}, "retrieved_chunks": []}))
    monkeypatch.setattr(query_nodes, "fuse_candidates_node", _node({"fused_candidates": [], "retrieved_chunks": []}))
    monkeypatch.setattr(query_nodes, "rerank_candidates_node", _node({"reranked_chunks": [{"document_id": DOC_A, "chunk_id": "chunk-1", "file_name": "alpha.pdf", "chunk_index": 1, "content": "Pricing is based on usage tiers."}]}))
    monkeypatch.setattr(query_nodes, "expand_context_node", _node({"context_chunks": [{"document_id": DOC_A, "chunk_id": "chunk-1", "file_name": "alpha.pdf", "chunk_index": 1, "content": "Pricing is based on usage tiers."}]}))
    monkeypatch.setattr(query_nodes, "generate_answer_node", _node({"answer": "Unsupported draft [S1].", "sources": [{"chunk_id": "chunk-1"}]}))
    monkeypatch.setattr(query_nodes, "regenerate_answer_node", _node({"answer": "Still unsupported [S1].", "sources": [{"chunk_id": "chunk-1"}]}), raising=False)
    verify_attempts = 0

    def _verify(state, **kwargs):
        nonlocal verify_attempts
        verify_attempts += 1
        return {
            "grounding_result": GroundingResult(
                grounded=False,
                score=0.1,
                unsupported_claims=["draft"],
                missing_citations=[],
            ),
            "answer_verified": False,
            "verification_attempt_count": verify_attempts,
        }

    monkeypatch.setattr(query_nodes, "verify_grounding_node", _verify)
    monkeypatch.setattr(query_nodes, "save_message_optional_node", lambda state, **kwargs: pytest.fail("unverified answer should not be saved"))

    result = build_query_graph(settings=settings).invoke(
        {"question": "What is pricing?", "document_ids": [DOC_A], "save_message": True}
    )

    assert result["answer"] == query_nodes.SAFE_INSUFFICIENT_CONTEXT_MESSAGE
    assert result["sources"] == []
    assert "Unsupported draft" not in result["answer"]
    assert "Still unsupported" not in result["answer"]


def test_retrieve_candidates_node_routes_each_strategy_to_allowed_paths(monkeypatch):
    settings = _test_settings(enable_keyword_search=True)
    calls: list[tuple[str, str, list[str]]] = []

    def _semantic(question, *, document_ids=None, **kwargs):
        calls.append(("semantic", question, list(document_ids or [])))
        return [0.1], [
            {
                "chunk_id": f"{question}-semantic",
                "document_id": (document_ids or [DOC_A])[0],
                "file_name": "alpha.pdf",
                "chunk_index": 0,
                "content": "semantic",
                "semantic_rank": 1,
                "semantic_score": 0.9,
                "qdrant_score": 0.9,
                "retrieval_paths": [RetrievalPath.SEMANTIC],
                "subquery_ids": [],
            }
        ]

    def _keyword(query, *, document_ids=None, **kwargs):
        calls.append(("keyword", query, list(document_ids or [])))
        return [
            {
                "chunk_id": f"{query}-keyword",
                "document_id": (document_ids or [DOC_A])[0],
                "file_name": "alpha.pdf",
                "chunk_index": 0,
                "content": "keyword",
                "keyword_rank": 1,
                "keyword_score": 0.8,
                "retrieval_paths": [RetrievalPath.KEYWORD],
                "subquery_ids": [],
            }
        ]

    monkeypatch.setattr(retrieval, "retrieve_semantic_candidates", _semantic)
    monkeypatch.setattr(retrieval.keyword_search, "search_keyword_chunks", _keyword)

    for strategy, expected_paths, filters in [
        (RetrievalStrategy.SEMANTIC, ["semantic"], RetrievalFilters()),
        (RetrievalStrategy.KEYWORD, ["keyword"], RetrievalFilters()),
        (RetrievalStrategy.HYBRID, ["semantic", "keyword"], RetrievalFilters()),
        (
            RetrievalStrategy.METADATA,
            ["semantic", "keyword"],
            RetrievalFilters(heading="Pricing"),
        ),
        (RetrievalStrategy.RELATION, ["semantic", "keyword"], RetrievalFilters()),
    ]:
        calls.clear()
        result = query_nodes.retrieve_candidates_node(
            {
                "query_plan": QueryPlan(
                    is_complex=False,
                    strategy=strategy,
                    subqueries=[QuerySubquery(id="q1", text="pricing")],
                    inferred_filters=filters,
                    needs_relations=strategy is RetrievalStrategy.RELATION,
                ),
                "subqueries": [QuerySubquery(id="q1", text="pricing")],
                "document_ids": [DOC_A],
            },
            settings=settings,
        )

        assert [call[0] for call in calls] == expected_paths
        assert all(
            candidate["subquery_ids"] == ["q1"]
            for candidates in result["path_candidates"].values()
            for candidate in candidates
        )


def test_retrieve_candidates_node_requires_active_filter_for_metadata(monkeypatch):
    settings = _test_settings(enable_keyword_search=True)
    calls: list[str] = []
    monkeypatch.setattr(
        retrieval,
        "retrieve_semantic_candidates",
        lambda *args, **kwargs: calls.append("semantic") or ([0.1], []),
    )
    monkeypatch.setattr(
        retrieval.keyword_search,
        "search_keyword_chunks",
        lambda *args, **kwargs: calls.append("keyword") or [],
    )

    result = query_nodes.retrieve_candidates_node(
        {
            "query_plan": QueryPlan(
                is_complex=False,
                strategy=RetrievalStrategy.METADATA,
                subqueries=[QuerySubquery(id="q1", text="pricing")],
                inferred_filters=RetrievalFilters(),
                needs_relations=False,
            ),
            "subqueries": [QuerySubquery(id="q1", text="pricing")],
            "document_ids": [DOC_A],
        },
        settings=settings,
    )

    assert result["path_candidates"] == {}
    assert result["retrieval_metrics"]["metadata_skipped_count"] == 1
    assert calls == []


def _query_plan_for_strategy(
    strategy: RetrievalStrategy,
    *,
    filters: RetrievalFilters | None = None,
) -> QueryPlan:
    return QueryPlan(
        is_complex=False,
        strategy=strategy,
        subqueries=[QuerySubquery(id="q1", text="pricing")],
        inferred_filters=filters or RetrievalFilters(),
        needs_relations=strategy is RetrievalStrategy.RELATION,
    )


def _retrieval_state_for_strategy(
    strategy: RetrievalStrategy,
    *,
    filters: RetrievalFilters | None = None,
) -> dict[str, object]:
    plan = _query_plan_for_strategy(strategy, filters=filters)
    return {
        "query_plan": plan,
        "subqueries": plan.subqueries,
        "document_ids": [DOC_A],
    }


def _candidate_for_path(path: RetrievalPath) -> dict[str, object]:
    return {
        "chunk_id": f"{path.value}-chunk",
        "document_id": DOC_A,
        "file_name": "alpha.pdf",
        "chunk_index": 0,
        "content": f"{path.value} content",
        "semantic_rank": 1 if path is RetrievalPath.SEMANTIC else None,
        "semantic_score": 0.9 if path is RetrievalPath.SEMANTIC else None,
        "qdrant_score": 0.9 if path is RetrievalPath.SEMANTIC else None,
        "keyword_rank": 1 if path is RetrievalPath.KEYWORD else None,
        "keyword_score": 0.8 if path is RetrievalPath.KEYWORD else None,
        "retrieval_paths": [path],
        "subquery_ids": [],
    }


@pytest.mark.parametrize(
    ("strategy", "expected_error"),
    [
        (RetrievalStrategy.HYBRID, "hybrid retrieval failed"),
        (RetrievalStrategy.RELATION, "relation retrieval failed"),
    ],
)
def test_retrieve_candidates_node_returns_error_when_both_allowed_paths_fail(
    monkeypatch,
    strategy,
    expected_error,
):
    settings = _test_settings(enable_keyword_search=True)
    monkeypatch.setattr(
        retrieval,
        "retrieve_semantic_candidates",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            retrieval.RetrievalError("semantic unavailable")
        ),
    )
    monkeypatch.setattr(
        retrieval.keyword_search,
        "search_keyword_chunks",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            retrieval.keyword_search.KeywordSearchError("keyword unavailable")
        ),
    )

    result = query_nodes.retrieve_candidates_node(
        _retrieval_state_for_strategy(strategy),
        settings=settings,
    )

    assert result["error_message"] == expected_error
    assert result["retrieval_metrics"]["attempted_paths"] == [
        "q1:semantic",
        "q1:keyword",
    ]
    assert result["retrieval_metrics"]["successful_paths"] == []
    assert sorted(result["retrieval_metrics"]["path_errors"]) == [
        "q1:keyword",
        "q1:semantic",
    ]


@pytest.mark.parametrize(
    ("strategy", "expected_error"),
    [
        (RetrievalStrategy.SEMANTIC, "semantic retrieval failed"),
        (RetrievalStrategy.KEYWORD, "keyword retrieval failed"),
    ],
)
def test_retrieve_candidates_node_returns_error_when_single_allowed_path_fails(
    monkeypatch,
    strategy,
    expected_error,
):
    settings = _test_settings(enable_keyword_search=True)
    monkeypatch.setattr(
        retrieval,
        "retrieve_semantic_candidates",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            retrieval.RetrievalError("semantic unavailable")
        ),
    )
    monkeypatch.setattr(
        retrieval.keyword_search,
        "search_keyword_chunks",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            retrieval.keyword_search.KeywordSearchError("keyword unavailable")
        ),
    )

    result = query_nodes.retrieve_candidates_node(
        _retrieval_state_for_strategy(strategy),
        settings=settings,
    )

    assert result["error_message"] == expected_error
    assert result["retrieval_metrics"]["successful_paths"] == []
    assert len(result["retrieval_metrics"]["attempted_paths"]) == 1


def test_retrieve_candidates_node_preserves_hybrid_one_path_fallback(monkeypatch):
    settings = _test_settings(enable_keyword_search=True)
    monkeypatch.setattr(
        retrieval,
        "retrieve_semantic_candidates",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            retrieval.RetrievalError("semantic unavailable")
        ),
    )
    monkeypatch.setattr(
        retrieval.keyword_search,
        "search_keyword_chunks",
        lambda *args, **kwargs: [_candidate_for_path(RetrievalPath.KEYWORD)],
    )

    result = query_nodes.retrieve_candidates_node(
        _retrieval_state_for_strategy(RetrievalStrategy.HYBRID),
        settings=settings,
    )

    assert "error_message" not in result
    assert result["retrieval_metrics"]["attempted_paths"] == [
        "q1:semantic",
        "q1:keyword",
    ]
    assert result["retrieval_metrics"]["successful_paths"] == ["q1:keyword"]
    assert result["path_candidates"]["q1:keyword"][0]["subquery_ids"] == ["q1"]
    assert result["retrieval_metrics"]["fallback_path"] == "keyword"


def test_retrieve_candidates_node_preserves_empty_no_result_for_successful_paths(
    monkeypatch,
):
    settings = _test_settings(enable_keyword_search=True)
    monkeypatch.setattr(
        retrieval,
        "retrieve_semantic_candidates",
        lambda *args, **kwargs: ([0.1], []),
    )
    monkeypatch.setattr(
        retrieval.keyword_search,
        "search_keyword_chunks",
        lambda *args, **kwargs: [],
    )

    result = query_nodes.retrieve_candidates_node(
        _retrieval_state_for_strategy(RetrievalStrategy.HYBRID),
        settings=settings,
    )

    assert "error_message" not in result
    assert result["path_candidates"] == {"q1:semantic": [], "q1:keyword": []}
    assert result["retrieval_metrics"]["attempted_paths"] == [
        "q1:semantic",
        "q1:keyword",
    ]
    assert result["retrieval_metrics"]["successful_paths"] == [
        "q1:semantic",
        "q1:keyword",
    ]
    assert result["retrieval_metrics"]["candidate_count"] == 0


def test_fuse_candidates_node_deduplicates_and_reserves_subquery_coverage():
    settings = _test_settings(enable_keyword_search=True)
    settings.RETRIEVAL_FUSION_TOP_K = 3
    state = {
        "query_plan": QueryPlan(
            is_complex=True,
            strategy=RetrievalStrategy.HYBRID,
            subqueries=[
                QuerySubquery(id="left", text="left side"),
                QuerySubquery(id="right", text="right side"),
            ],
            inferred_filters=RetrievalFilters(),
            needs_relations=False,
        ),
        "path_candidates": {
            "left:semantic": [
                {
                    "chunk_id": "shared",
                    "document_id": DOC_A,
                    "file_name": "alpha.pdf",
                    "chunk_index": 0,
                    "content": "shared left",
                    "semantic_rank": 1,
                    "semantic_score": 0.9,
                    "retrieval_paths": [RetrievalPath.SEMANTIC],
                    "subquery_ids": ["left"],
                },
                {
                    "chunk_id": "left-only",
                    "document_id": DOC_A,
                    "file_name": "alpha.pdf",
                    "chunk_index": 1,
                    "content": "left",
                    "semantic_rank": 2,
                    "semantic_score": 0.8,
                    "retrieval_paths": [RetrievalPath.SEMANTIC],
                    "subquery_ids": ["left"],
                },
            ],
            "right:keyword": [
                {
                    "chunk_id": "shared",
                    "document_id": DOC_B,
                    "file_name": "bravo.pdf",
                    "chunk_index": 0,
                    "content": "shared right",
                    "keyword_rank": 1,
                    "keyword_score": 0.95,
                    "retrieval_paths": [RetrievalPath.KEYWORD],
                    "subquery_ids": ["right"],
                },
                {
                    "chunk_id": "right-only",
                    "document_id": DOC_B,
                    "file_name": "bravo.pdf",
                    "chunk_index": 1,
                    "content": "right",
                    "keyword_rank": 5,
                    "keyword_score": 0.2,
                    "retrieval_paths": [RetrievalPath.KEYWORD],
                    "subquery_ids": ["right"],
                },
            ],
        },
    }

    result = query_nodes.fuse_candidates_node(state, settings=settings)

    assert len(result["retrieved_chunks"]) == 3
    assert len({chunk["chunk_id"] for chunk in result["retrieved_chunks"]}) == 3
    assert "left" in result["retrieved_chunks"][0]["subquery_ids"]
    assert {chunk["chunk_id"] for chunk in result["retrieved_chunks"]} >= {
        "left-only",
        "right-only",
    }


def test_build_query_graph_routes_blank_question_to_validation_error(monkeypatch):
    settings = _test_settings()

    monkeypatch.setattr(
        query_nodes,
        "retrieve_qdrant_node",
        lambda state, **kwargs: pytest.fail("retrieve_qdrant should not run on blank question"),
    )
    monkeypatch.setattr(
        query_nodes,
        "jina_rerank_node",
        lambda state, **kwargs: pytest.fail("jina_rerank should not run on blank question"),
    )
    monkeypatch.setattr(
        query_nodes,
        "expand_neighbor_context_node",
        lambda state, **kwargs: pytest.fail("expand_neighbor_context should not run on blank question"),
    )
    monkeypatch.setattr(
        query_nodes,
        "generate_answer_node",
        lambda state, **kwargs: pytest.fail("generate_answer should not run on blank question"),
    )
    monkeypatch.setattr(
        query_nodes,
        "save_message_optional_node",
        lambda state, **kwargs: pytest.fail("save_message_optional should not run on blank question"),
    )

    graph = build_query_graph(settings=settings)
    result = graph.invoke({"question": "   "})

    assert result["error_message"] == "question is required"
    assert result["workflow_trace"][0]["error_code"] == "prepare_query_failed"
    assert "question is required" not in str(result["workflow_trace"])


def test_build_query_graph_returns_no_relevant_information_when_retrieval_is_empty(
    monkeypatch,
):
    settings = _test_settings()
    fake_qdrant_client = FakeQdrantClient(points=[])
    fake_shopaikey_client = FakeShopAIKeyClient(vectors=[[0.1, 0.2, 0.3]])

    monkeypatch.setattr(
        retrieval,
        "create_qdrant_client",
        lambda settings=None: fake_qdrant_client,
    )
    monkeypatch.setattr(
        retrieval,
        "create_shopaikey_client",
        lambda settings=None: fake_shopaikey_client,
    )

    graph = build_query_graph(settings=settings)
    result = graph.invoke({"question": "What does the document say about pricing?"})

    assert result["answer"] == query_nodes.NO_RELEVANT_INFORMATION_MESSAGE
    assert result["sources"] == []
    assert fake_shopaikey_client.embeddings.calls == [
        (settings.SHOPAIKEY_EMBEDDING_MODEL, ["What does the document say about pricing?"])
    ]
    assert fake_qdrant_client.query_calls[0]["limit"] == settings.RETRIEVAL_SEMANTIC_TOP_K


def test_fuse_candidates_node_preserves_strong_semantic_candidate_below_fused_cutoff():
    """A strong answer-bearing semantic candidate with a low fused rank
    survives in the diverse pool via select_rerank_candidates."""
    settings = _test_settings().model_copy(
        update={
            "RETRIEVAL_RERANK_SEMANTIC_PER_PATH_TOP_K": 5,
            "RETRIEVAL_RERANK_KEYWORD_PER_PATH_TOP_K": 2,
            "RETRIEVAL_RERANK_FUSED_TOP_K": 1,
            "RETRIEVAL_RERANK_CANDIDATE_TOP_K": 20,
            "RETRIEVAL_FUSION_TOP_K": 1,
        }
    )

    strong_answer = _qdrant_point(
        chunk_id="strong-answer",
        document_id=DOC_A,
        chunk_index=0,
        file_name="alpha.pdf",
        score=0.95,
        text="The answer-bearing passage about pricing details.",
    )
    high_fused = _qdrant_point(
        chunk_id="high-fused",
        document_id=DOC_A,
        chunk_index=1,
        file_name="alpha.pdf",
        score=0.85,
        text="A moderately relevant passage.",
    )

    qdrant_client = FakeQdrantClient(points=[high_fused, strong_answer])

    retrieval_result = query_nodes.retrieve_candidates_node(
        {
            "query_plan": QueryPlan(
                is_complex=False,
                strategy=RetrievalStrategy.SEMANTIC,
                subqueries=[QuerySubquery(id="q1", text="pricing")],
                inferred_filters=RetrievalFilters(),
                needs_relations=False,
            ),
            "subqueries": [QuerySubquery(id="q1", text="pricing")],
            "document_ids": [DOC_A],
        },
        settings=settings,
        qdrant_client=qdrant_client,
        shopaikey_client=FakeShopAIKeyClient(vectors=[[0.1, 0.2, 0.3]]),
    )

    assert "error_message" not in retrieval_result

    # Run fuse_candidates_node which now uses select_rerank_candidates
    fuse_result = query_nodes.fuse_candidates_node(
        retrieval_result,
        settings=settings,
    )

    diverse_pool = fuse_result["retrieved_chunks"]
    pool_ids = [c["chunk_id"] for c in diverse_pool]

    # The strong answer-bearing candidate must survive even though it was
    # below the fused-only cutoff of 1
    assert "strong-answer" in pool_ids, (
        f"strong-answer should be in the diverse pool but was not: {pool_ids}"
    )
    assert "high-fused" in pool_ids
    assert len(pool_ids) == len(set(pool_ids)), "Duplicate chunk IDs in pool"
    assert len(diverse_pool) <= settings.RETRIEVAL_RERANK_CANDIDATE_TOP_K
