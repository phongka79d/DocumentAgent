from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import get_type_hints
from uuid import UUID, uuid4

import pytest

from app.core.config import Settings
from app.graphs import ingestion_nodes
from app.graphs.ingestion_graph import build_ingestion_graph
from app.graphs.ingestion_state import IngestionState


FIXED_DOCUMENT_ID = "11111111-1111-1111-1111-111111111111"
SECOND_DOCUMENT_ID = "22222222-2222-2222-2222-222222222222"
FIXED_STORAGE_PATH = f"documents/{FIXED_DOCUMENT_ID}/original/report.pdf"


def _test_settings(*, chunking_strategy: str = "smart_section") -> Settings:
    return Settings(
        _env_file=None,
        SUPABASE_URL="https://example.supabase.co",
        SUPABASE_SERVICE_ROLE_KEY="service-role-key",
        SUPABASE_STORAGE_BUCKET="documents",
        SHOPAIKEY_API_KEY="shopai-key",
        SHOPAIKEY_BASE_URL="https://api.shopaikey.com/v1",
        SHOPAIKEY_EMBEDDING_MODEL="text-embedding-3-small",
        SHOPAIKEY_CHAT_MODEL="gpt-5-mini",
        SHOPAIKEY_INPUT_MODEL="gpt-5-mini",
        QDRANT_URL="https://qdrant.example.com",
        QDRANT_API_KEY="qdrant-key",
        QDRANT_COLLECTION="document_chunks_v1",
        JINA_API_KEY="jina-key",
        JINA_RERANK_MODEL="jina-reranker-v2-base-multilingual",
        CHUNKING_STRATEGY=chunking_strategy,
    )


def _patch_settings(monkeypatch: pytest.MonkeyPatch, settings: Settings) -> None:
    monkeypatch.setattr(ingestion_nodes, "get_settings", lambda: settings)


def _document_row(
    *,
    document_id: str = FIXED_DOCUMENT_ID,
    file_name: str = "report.pdf",
    status: str = "uploaded",
    storage_path: str = FIXED_STORAGE_PATH,
    file_hash: str = "file-hash",
    qdrant_collection: str | None = None,
) -> dict[str, object]:
    now = datetime(2026, 6, 18, 8, 0, tzinfo=timezone.utc)
    return {
        "id": document_id,
        "title": "Quarterly report",
        "file_name": file_name,
        "mime_type": "application/pdf",
        "file_size": 123,
        "file_hash": file_hash,
        "storage_path": storage_path,
        "status": status,
        "total_pages": 5,
        "total_chunks": 0,
        "parser_name": None,
        "parser_version": None,
        "chunking_strategy": None,
        "chunking_version": None,
        "embedding_model": None,
        "embedding_dimension": None,
        "qdrant_collection": qdrant_collection,
        "indexed_at": None,
        "error_message": None,
        "created_at": now,
        "updated_at": now,
    }


def _parsed_document(
    *,
    text: str = "Page one text\n\nPage two text",
    parser_name: str = "pymupdf",
    parser_version: str = "1.0.0",
) -> dict[str, object]:
    return {
        "text": text,
        "pages": [
            {"page_number": 1, "text": "Page one text"},
            {"page_number": 2, "text": "Page two text"},
        ],
        "metadata": {
            "parser_name": parser_name,
            "parser_version": parser_version,
        },
    }


def _chunk_record(
    *,
    chunk_index: int,
    content: str,
    content_hash: str | None = None,
    chunk_type: str = "fixed",
    heading: str | None = None,
    section_path: list[str] | None = None,
    page_start: int = 1,
    page_end: int = 1,
    token_start: int | None = None,
    token_end: int | None = None,
) -> dict[str, object]:
    resolved_token_start = chunk_index * 10 if token_start is None else token_start
    resolved_token_end = resolved_token_start + 10 if token_end is None else token_end
    return {
        "chunk_index": chunk_index,
        "content": content,
        "content_hash": content_hash or f"hash-{chunk_index}",
        "token_count": len(content.split()),
        "chunk_type": chunk_type,
        "heading": heading,
        "section_path": list(section_path or []),
        "page_start": page_start,
        "page_end": page_end,
        "token_start": resolved_token_start,
        "token_end": resolved_token_end,
    }


@dataclass
class FakeResponse:
    data: list[dict[str, object]] | dict[str, object] | None = None


@dataclass
class FakeStorageBucket:
    downloads: dict[str, bytes] = field(default_factory=dict)
    download_calls: list[str] = field(default_factory=list)
    remove_calls: list[list[str]] = field(default_factory=list)

    def download(self, path: str) -> bytes:
        self.download_calls.append(path)
        return self.downloads[path]

    def remove(self, paths: list[str]) -> list[dict[str, object]]:
        self.remove_calls.append(paths)
        return [{"path": path} for path in paths]


class FakeStorageNamespace:
    def __init__(self, bucket: FakeStorageBucket, bucket_name: str) -> None:
        self.bucket = bucket
        self.bucket_name = bucket_name

    def from_(self, bucket_name: str) -> FakeStorageBucket:
        assert bucket_name == self.bucket_name
        return self.bucket


class FakeTableQuery:
    def __init__(self, client: "FakeSupabaseClient", table_name: str) -> None:
        self.client = client
        self.table_name = table_name
        self.operation = "select"
        self.payload: dict[str, object] | list[dict[str, object]] | None = None
        self.filters: list[tuple[str, object]] = []
        self.limit_count: int | None = None
        self.order_clause: tuple[str, bool] | None = None

    def select(self, *columns: str, count=None, head=None):
        self.operation = "select"
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

    def update(self, json, *, count=None, returning=None, upsert=False, default_to_null=True):
        self.operation = "update"
        self.payload = dict(json)
        return self

    def delete(self, *, count=None, returning=None):
        self.operation = "delete"
        return self

    def eq(self, column: str, value):
        self.filters.append((column, value))
        return self

    def limit(self, size: int, *, foreign_table=None):
        self.limit_count = size
        return self

    def order(self, column: str, *, desc=False, nullsfirst=None, foreign_table=None):
        self.order_clause = (column, desc)
        return self

    def execute(self) -> FakeResponse:
        rows = list(self.client.tables.get(self.table_name, []))
        for column, expected in self.filters:
            rows = [row for row in rows if row.get(column) == expected]

        if self.operation == "select":
            if self.order_clause is not None:
                column, desc = self.order_clause
                rows.sort(key=lambda row: row.get(column), reverse=desc)
            if self.limit_count is not None:
                rows = rows[: self.limit_count]
            return FakeResponse(data=rows)

        if self.operation == "insert":
            assert self.payload is not None
            payload_rows = self.payload if isinstance(self.payload, list) else [self.payload]
            inserted_rows: list[dict[str, object]] = []
            for payload in payload_rows:
                row = dict(payload)
                row.setdefault("id", str(uuid4()))
                inserted_rows.append(row)
            self.client.events.append(("insert", self.table_name, inserted_rows))
            self.client.tables.setdefault(self.table_name, []).extend(inserted_rows)
            return FakeResponse(data=inserted_rows)

        if self.operation == "update":
            assert self.payload is not None
            updated_rows: list[dict[str, object]] = []
            for row in self.client.tables.get(self.table_name, []):
                if all(row.get(column) == expected for column, expected in self.filters):
                    row.update(self.payload)
                    updated_rows.append(dict(row))
            self.client.events.append(
                ("update", self.table_name, dict(self.payload), list(self.filters))
            )
            return FakeResponse(data=updated_rows)

        if self.operation == "delete":
            deleted_rows = [
                row
                for row in self.client.tables.get(self.table_name, [])
                if all(row.get(column) == expected for column, expected in self.filters)
            ]
            self.client.tables[self.table_name] = [
                row
                for row in self.client.tables.get(self.table_name, [])
                if row not in deleted_rows
            ]
            self.client.events.append(("delete", self.table_name, list(self.filters)))
            return FakeResponse(data=deleted_rows)

        raise AssertionError(f"Unsupported fake operation: {self.operation}")


class FakeSupabaseClient:
    def __init__(
        self,
        *,
        documents: list[dict[str, object]] | None = None,
        document_chunks: list[dict[str, object]] | None = None,
        bucket_name: str = "documents",
        downloads: dict[str, bytes] | None = None,
    ) -> None:
        self.tables: dict[str, list[dict[str, object]]] = {
            "documents": list(documents or []),
            "document_chunks": list(document_chunks or []),
        }
        self.events: list[tuple[object, ...]] = []
        self._bucket = FakeStorageBucket(downloads=downloads or {})
        self.storage = FakeStorageNamespace(self._bucket, bucket_name)

    def table(self, table_name: str) -> FakeTableQuery:
        return FakeTableQuery(self, table_name)


class FakeQdrantClient:
    def __init__(self) -> None:
        self.upsert_calls: list[dict[str, object]] = []
        self.delete_calls: list[dict[str, object]] = []

    def upsert(self, *, collection_name, points, wait=True, ordering=None, **kwargs):
        self.upsert_calls.append(
            {
                "collection_name": collection_name,
                "points": list(points),
                "wait": wait,
                "ordering": ordering,
                "kwargs": kwargs,
            }
        )
        return {"status": "ok"}

    def delete(
        self,
        *,
        collection_name,
        points_selector,
        wait=True,
        ordering=None,
        shard_key_selector=None,
        timeout=None,
        **kwargs,
    ):
        self.delete_calls.append(
            {
                "collection_name": collection_name,
                "points_selector": points_selector,
                "wait": wait,
                "ordering": ordering,
                "shard_key_selector": shard_key_selector,
                "timeout": timeout,
                "kwargs": kwargs,
            }
        )
        return {"status": "ok"}


class FakeEmbeddingEndpoint:
    def __init__(self, vectors: list[list[float]]) -> None:
        self.vectors = vectors
        self.calls: list[tuple[str, list[str]]] = []

    def create(self, *, model: str, input: list[str]):
        self.calls.append((model, list(input)))
        return SimpleNamespace(
            data=[SimpleNamespace(embedding=vector) for vector in self.vectors]
        )


class FakeShopAIKeyClient:
    def __init__(self, vectors: list[list[float]]) -> None:
        self.embeddings = FakeEmbeddingEndpoint(vectors)


class FakeParser:
    def __init__(self, parsed_document: dict[str, object]) -> None:
        self.parsed_document = parsed_document
        self.parser_name = "fake-parser"
        self.parser_version = "1.0.0"

    def parse(self, file_bytes: bytes, *, file_name: str | None = None, mime_type: str | None = None):
        _ = file_bytes, file_name, mime_type
        return self.parsed_document


class FakeChunker:
    def __init__(self, *args, **kwargs) -> None:
        self.args = args
        self.kwargs = kwargs
        self.chunk_calls: list[dict[str, object]] = []
        self.chunks = [
            _chunk_record(chunk_index=0, content="chunk zero"),
            _chunk_record(chunk_index=1, content="chunk one"),
        ]

    def chunk(self, parsed_document: dict[str, object]) -> list[dict[str, object]]:
        self.chunk_calls.append(parsed_document)
        return list(self.chunks)


def test_ingestion_state_contains_required_fields_and_excludes_binary_fields():
    hints = get_type_hints(IngestionState)

    assert set(hints) == {
        "document_id",
        "document_record",
        "storage_path",
        "file_name",
        "mime_type",
        "file_size",
        "file_hash",
        "parsed_document",
        "total_pages",
        "parser_name",
        "parser_version",
        "chunks",
        "total_chunks",
        "chunking_strategy",
        "chunking_version",
        "embeddings",
        "embedding_model",
        "embedding_dimension",
        "qdrant_collection",
        "summary_records",
        "relation_update_result",
        "trace_id",
        "workflow_trace",
        "retry_attempts",
        "status",
        "error_message",
    }
    assert "original_file_bytes" not in hints
    assert "upload_file_path" not in hints
    assert "large_binary_data" not in hints
    assert all("prompt" not in field for field in hints)


def test_load_document_record_node_populates_small_state_fields(monkeypatch):
    settings = _test_settings()
    fake_client = FakeSupabaseClient(
        documents=[
            _document_row(
                status="uploaded",
                qdrant_collection=None,
            )
        ]
    )

    _patch_settings(monkeypatch, settings)
    monkeypatch.setattr(ingestion_nodes, "create_supabase_client", lambda settings=None: fake_client)

    result = ingestion_nodes.load_document_record_node({"document_id": FIXED_DOCUMENT_ID})

    assert result["document_id"] == FIXED_DOCUMENT_ID
    assert result["status"] == "uploaded"
    assert result["document_record"]["id"] == FIXED_DOCUMENT_ID
    assert result["storage_path"] == FIXED_STORAGE_PATH
    assert result["file_name"] == "report.pdf"
    assert result["mime_type"] == "application/pdf"
    assert result["file_size"] == 123
    assert result["file_hash"] == "file-hash"
    assert result["qdrant_collection"] == settings.QDRANT_COLLECTION
    assert "original_file_bytes" not in result


def test_mark_processing_node_sets_processing_and_clears_error_message(monkeypatch):
    settings = _test_settings()
    fake_client = FakeSupabaseClient(documents=[_document_row(status="uploaded")])

    _patch_settings(monkeypatch, settings)
    monkeypatch.setattr(ingestion_nodes, "create_supabase_client", lambda settings=None: fake_client)

    result = ingestion_nodes.mark_processing_node(
        {
            "document_id": FIXED_DOCUMENT_ID,
            "status": "uploaded",
            "error_message": "previous failure",
        }
    )

    assert result == {"status": "processing", "error_message": None}
    assert fake_client.events[0][0] == "update"
    payload = fake_client.events[0][2]
    assert payload["status"] == "processing"
    assert payload["error_message"] is None
    assert isinstance(payload["updated_at"], str)


def test_parse_document_node_downloads_and_parses_normalized_document(monkeypatch):
    settings = _test_settings()
    parsed_document = _parsed_document()
    fake_client = FakeSupabaseClient(
        documents=[_document_row()],
        downloads={FIXED_STORAGE_PATH: b"fake pdf bytes"},
    )
    fake_parser = FakeParser(parsed_document)

    _patch_settings(monkeypatch, settings)
    monkeypatch.setattr(ingestion_nodes, "create_supabase_client", lambda settings=None: fake_client)
    monkeypatch.setattr(ingestion_nodes, "get_parser_for_file", lambda file_name, mime_type=None: fake_parser)

    result = ingestion_nodes.parse_document_node(
        {
            "document_id": FIXED_DOCUMENT_ID,
            "storage_path": FIXED_STORAGE_PATH,
            "file_name": "report.pdf",
            "mime_type": "application/pdf",
        }
    )

    assert fake_client._bucket.download_calls == [FIXED_STORAGE_PATH]
    assert result["parsed_document"] == parsed_document
    assert result["total_pages"] == 2
    assert result["parser_name"] == "pymupdf"
    assert result["parser_version"] == "1.0.0"


def test_chunk_document_node_uses_fixed_token_chunker_and_stores_v1_metadata(monkeypatch):
    settings = _test_settings(chunking_strategy="fixed_token")
    fake_chunker = FakeChunker()

    _patch_settings(monkeypatch, settings)
    monkeypatch.setattr(
        ingestion_nodes.ingestion_payloads,
        "SmartSectionChunker",
        lambda *args, **kwargs: pytest.fail(
            "SmartSectionChunker should not be used when fixed_token is configured"
        ),
    )
    monkeypatch.setattr(
        ingestion_nodes.ingestion_payloads,
        "FixedTokenChunker",
        lambda *args, **kwargs: fake_chunker,
    )

    result = ingestion_nodes.chunk_document_node(
        {
            "document_id": FIXED_DOCUMENT_ID,
            "parsed_document": _parsed_document(),
            "parser_name": "fake-parser",
            "parser_version": "1.0.0",
        }
    )

    assert fake_chunker.chunk_calls == [_parsed_document()]
    assert result["chunks"] == fake_chunker.chunks
    assert result["total_chunks"] == 2
    assert result["chunking_strategy"] == "fixed_token"
    assert result["chunking_version"] == "v1"


def test_chunk_document_node_uses_smart_section_chunker_and_stores_v2_metadata(monkeypatch):
    settings = _test_settings(chunking_strategy="smart_section")
    fake_chunker = FakeChunker()
    fake_chunker.chunks = [
        _chunk_record(
            chunk_index=0,
            content="smart section chunk",
            chunk_type="smart_section",
            heading="Overview",
            section_path=["Overview"],
            page_start=1,
            page_end=2,
            token_start=0,
            token_end=3,
        )
    ]

    _patch_settings(monkeypatch, settings)
    monkeypatch.setattr(
        ingestion_nodes.ingestion_payloads,
        "FixedTokenChunker",
        lambda *args, **kwargs: pytest.fail(
            "FixedTokenChunker should not be used when smart_section is configured"
        ),
    )
    monkeypatch.setattr(
        ingestion_nodes.ingestion_payloads,
        "SmartSectionChunker",
        lambda *args, **kwargs: fake_chunker,
    )

    result = ingestion_nodes.chunk_document_node(
        {
            "document_id": FIXED_DOCUMENT_ID,
            "parsed_document": _parsed_document(),
            "parser_name": "fake-parser",
            "parser_version": "1.0.0",
        }
    )

    assert fake_chunker.chunk_calls == [_parsed_document()]
    assert result["chunks"] == fake_chunker.chunks
    assert result["total_chunks"] == 1
    assert result["chunking_strategy"] == "smart_section"
    assert result["chunking_version"] == "v2"


def test_save_chunks_node_deletes_old_rows_inserts_new_rows_and_attaches_ids(monkeypatch):
    settings = _test_settings()
    existing_chunk = {
        "id": "existing-chunk-id",
        "document_id": FIXED_DOCUMENT_ID,
        "chunk_index": 99,
        "content": "stale chunk",
    }
    fake_client = FakeSupabaseClient(
        documents=[_document_row()],
        document_chunks=[existing_chunk],
    )

    _patch_settings(monkeypatch, settings)
    monkeypatch.setattr(ingestion_nodes, "create_supabase_client", lambda settings=None: fake_client)

    result = ingestion_nodes.save_chunks_node(
        {
            "document_id": FIXED_DOCUMENT_ID,
            "file_name": "report.pdf",
            "parser_name": "fake-parser",
            "parser_version": "1.0.0",
            "chunking_strategy": "smart_section",
            "chunking_version": "v2",
            "chunks": [
                _chunk_record(
                    chunk_index=0,
                    content="chunk zero",
                    chunk_type="smart_section",
                    heading="Overview",
                    section_path=["Overview"],
                    page_start=1,
                    page_end=2,
                ),
                _chunk_record(
                    chunk_index=1,
                    content="chunk one",
                    chunk_type="smart_section",
                    heading="Details",
                    section_path=["Overview", "Details"],
                    page_start=2,
                    page_end=3,
                ),
            ],
        }
    )

    assert fake_client.events[0][0] == "delete"
    assert fake_client.events[1][0] == "insert"
    inserted_rows = fake_client.events[1][2]
    approved_chunk_keys = {
        "id",
        "document_id",
        "chunk_index",
        "content",
        "content_hash",
        "token_count",
        "chunk_type",
        "heading",
        "section_path",
        "page_start",
        "page_end",
        "token_start",
        "token_end",
        "metadata",
        "qdrant_point_id",
    }
    assert all("text" not in row for row in inserted_rows)
    assert all("file_name" not in row for row in inserted_rows)
    assert all(set(row).issubset(approved_chunk_keys) for row in inserted_rows)
    assert all(
        row["metadata"]
        == {
            "parser_name": "fake-parser",
            "parser_version": "1.0.0",
            "chunking_strategy": "smart_section",
            "chunking_version": "v2",
        }
        for row in inserted_rows
    )
    assert len(fake_client.tables["document_chunks"]) == 2
    assert all("id" in chunk for chunk in result["chunks"])
    assert [chunk["chunk_index"] for chunk in result["chunks"]] == [0, 1]
    assert [chunk["content"] for chunk in result["chunks"]] == ["chunk zero", "chunk one"]


def test_embed_chunks_node_generates_embeddings_and_metadata(monkeypatch):
    settings = _test_settings()
    fake_client = FakeShopAIKeyClient(vectors=[[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]])

    _patch_settings(monkeypatch, settings)
    monkeypatch.setattr(ingestion_nodes, "create_shopaikey_client", lambda settings=None: fake_client)

    result = ingestion_nodes.embed_chunks_node(
        {
            "document_id": FIXED_DOCUMENT_ID,
            "chunks": [
                {"id": "chunk-1", "content": "first chunk"},
                {"id": "chunk-2", "content": "second chunk"},
            ],
        }
    )

    assert fake_client.embeddings.calls == [
        (settings.SHOPAIKEY_EMBEDDING_MODEL, ["first chunk", "second chunk"])
    ]
    assert result["embeddings"] == [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
    assert result["embedding_model"] == settings.SHOPAIKEY_EMBEDDING_MODEL
    assert result["embedding_dimension"] == 3


def test_embed_chunks_node_retries_transient_embedding_failure(monkeypatch):
    settings = _test_settings().model_copy(
        update={
            "WORKFLOW_MAX_ATTEMPTS": 2,
            "WORKFLOW_RETRY_BASE_DELAY_SECONDS": 0.0,
            "WORKFLOW_RETRY_MAX_DELAY_SECONDS": 0.0,
        }
    )

    class FlakyEmbeddingEndpoint:
        def __init__(self) -> None:
            self.calls = 0

        def create(self, *, model: str, input: list[str]):
            self.calls += 1
            if self.calls == 1:
                raise TimeoutError("temporary embedding timeout")
            return SimpleNamespace(
                data=[SimpleNamespace(embedding=[0.1, 0.2, 0.3])]
            )

    endpoint = FlakyEmbeddingEndpoint()
    fake_client = SimpleNamespace(embeddings=endpoint)

    _patch_settings(monkeypatch, settings)
    monkeypatch.setattr(
        ingestion_nodes,
        "create_shopaikey_client",
        lambda settings=None: fake_client,
    )

    result = ingestion_nodes.embed_chunks_node(
        {
            "document_id": FIXED_DOCUMENT_ID,
            "chunks": [{"id": "chunk-1", "content": "first chunk"}],
        }
    )

    assert endpoint.calls == 2
    assert result["embeddings"] == [[0.1, 0.2, 0.3]]
    assert result["retry_attempts"] == {"embed_chunks": 2}


def test_upsert_qdrant_node_rejects_chunks_without_saved_ids(monkeypatch):
    settings = _test_settings()
    fake_qdrant_client = FakeQdrantClient()

    _patch_settings(monkeypatch, settings)
    monkeypatch.setattr(ingestion_nodes, "create_qdrant_client", lambda settings=None: fake_qdrant_client)

    result = ingestion_nodes.upsert_qdrant_node(
        {
            "document_id": FIXED_DOCUMENT_ID,
            "file_name": "report.pdf",
            "qdrant_collection": settings.QDRANT_COLLECTION,
            "embeddings": [[0.1, 0.2, 0.3]],
            "chunks": [
                _chunk_record(chunk_index=0, content="chunk zero"),
            ],
        }
    )

    assert result["status"] == "failed"
    assert "chunk ids" in result["error_message"].lower()
    assert fake_qdrant_client.upsert_calls == []


def test_upsert_qdrant_node_upserts_points_with_smart_section_chunk_payloads(monkeypatch):
    settings = _test_settings()
    fake_qdrant_client = FakeQdrantClient()
    fake_supabase_client = FakeSupabaseClient(document_chunks=[])

    _patch_settings(monkeypatch, settings)
    monkeypatch.setattr(ingestion_nodes, "create_qdrant_client", lambda settings=None: fake_qdrant_client)
    monkeypatch.setattr(
        ingestion_nodes,
        "create_supabase_client",
        lambda settings=None: fake_supabase_client,
    )

    result = ingestion_nodes.upsert_qdrant_node(
        {
            "document_id": FIXED_DOCUMENT_ID,
            "file_name": "report.pdf",
            "qdrant_collection": settings.QDRANT_COLLECTION,
            "embeddings": [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]],
            "chunks": [
                {
                    "id": "chunk-1",
                    "chunk_index": 0,
                    "content": "first chunk",
                    "heading": "Overview",
                    "section_path": ["Overview"],
                    "page_start": 1,
                    "page_end": 1,
                    "chunk_type": "smart_section",
                    "token_count": 2,
                },
                {
                    "id": "chunk-2",
                    "chunk_index": 1,
                    "content": "second chunk",
                    "heading": "Details",
                    "section_path": ["Overview", "Details"],
                    "page_start": 2,
                    "page_end": 3,
                    "chunk_type": "smart_section",
                    "token_count": 2,
                },
            ],
        }
    )

    assert len(fake_qdrant_client.upsert_calls) == 1
    upsert_call = fake_qdrant_client.upsert_calls[0]
    assert upsert_call["collection_name"] == settings.QDRANT_COLLECTION
    assert len(upsert_call["points"]) == 2
    first_point = upsert_call["points"][0]
    assert first_point.id == "chunk-1"
    assert first_point.vector == [0.1, 0.2, 0.3]
    assert first_point.payload["document_id"] == FIXED_DOCUMENT_ID
    assert first_point.payload["chunk_id"] == "chunk-1"
    assert first_point.payload["file_name"] == "report.pdf"
    assert first_point.payload["heading"] == "Overview"
    assert first_point.payload["section_path"] == ["Overview"]
    assert first_point.payload["page_start"] == 1
    assert first_point.payload["page_end"] == 1
    assert first_point.payload["chunk_type"] == "smart_section"
    assert first_point.payload["token_count"] == 2
    assert first_point.payload["text"] == "first chunk"
    second_point = upsert_call["points"][1]
    assert second_point.payload["heading"] == "Details"
    assert second_point.payload["section_path"] == ["Overview", "Details"]
    assert second_point.payload["page_start"] == 2
    assert second_point.payload["page_end"] == 3
    assert second_point.payload["chunk_type"] == "smart_section"
    assert second_point.payload["token_count"] == 2
    assert second_point.payload["text"] == "second chunk"
    assert result["qdrant_collection"] == settings.QDRANT_COLLECTION
    assert result["chunks"][0]["qdrant_point_id"] == "chunk-1"


def test_summarize_document_node_generates_summary_records(monkeypatch):
    settings = _test_settings()
    generated = [
        {
            "summary_type": "document",
            "content": "Document summary",
            "source_chunk_ids": ["chunk-1"],
            "model": settings.SHOPAIKEY_CHAT_MODEL,
        }
    ]

    _patch_settings(monkeypatch, settings)
    monkeypatch.setattr(
        ingestion_nodes.summaries,
        "generate_document_summaries",
        lambda document_id, chunks, settings=None, **kwargs: generated,
    )

    result = ingestion_nodes.summarize_document_node(
        {
            "document_id": FIXED_DOCUMENT_ID,
            "chunks": [
                {
                    "id": "chunk-1",
                    "chunk_index": 0,
                    "content": "chunk zero",
                    "heading": "Overview",
                    "section_path": ["Overview"],
                }
            ],
        }
    )

    assert result == {"summary_records": generated}


def test_summarize_document_node_returns_empty_records_when_disabled(monkeypatch):
    settings = _test_settings()
    settings.ENABLE_SUMMARIES = False

    _patch_settings(monkeypatch, settings)
    monkeypatch.setattr(
        ingestion_nodes.summaries,
        "generate_document_summaries",
        lambda *args, **kwargs: pytest.fail("summary service should not be called"),
    )

    result = ingestion_nodes.summarize_document_node(
        {
            "document_id": FIXED_DOCUMENT_ID,
            "chunks": [
                {
                    "id": "chunk-1",
                    "chunk_index": 0,
                    "content": "chunk zero",
                }
            ],
        }
    )

    assert result == {"summary_records": []}


def test_update_document_relations_node_skips_when_disabled(monkeypatch):
    settings = _test_settings()
    settings.ENABLE_RELATION_RETRIEVAL = False

    _patch_settings(monkeypatch, settings)
    monkeypatch.setattr(
        ingestion_nodes.relations,
        "update_document_relations",
        lambda *args, **kwargs: pytest.fail("relation service should not be called"),
    )

    result = ingestion_nodes.update_document_relations_node(
        {
            "document_id": FIXED_DOCUMENT_ID,
            "summary_records": [
                {
                    "summary_type": "document",
                    "content": "Document summary",
                }
            ],
        }
    )

    assert result == {
        "relation_update_result": {
            "status": "skipped",
            "reason": "relation retrieval disabled",
        }
    }


def test_update_document_relations_node_records_warning_without_failing_indexing(monkeypatch):
    settings = _test_settings()

    _patch_settings(monkeypatch, settings)

    def _raise(*args, **kwargs):
        raise RuntimeError("relation provider unavailable")

    monkeypatch.setattr(ingestion_nodes.relations, "update_document_relations", _raise)

    result = ingestion_nodes.update_document_relations_node(
        {
            "document_id": FIXED_DOCUMENT_ID,
            "summary_records": [
                {
                    "summary_type": "document",
                    "content": "Document summary",
                }
            ],
        }
    )

    assert result.get("status") != "failed"
    assert result["relation_update_result"]["status"] == "warning"
    assert "relation provider unavailable" in result["relation_update_result"]["warning"]


def test_update_document_relations_node_keeps_index_ready_after_retry_exhaustion(monkeypatch):
    settings = _test_settings().model_copy(
        update={
            "WORKFLOW_MAX_ATTEMPTS": 2,
            "WORKFLOW_RETRY_BASE_DELAY_SECONDS": 0.0,
            "WORKFLOW_RETRY_MAX_DELAY_SECONDS": 0.0,
        }
    )
    calls = 0

    def _raise(*args, **kwargs):
        nonlocal calls
        calls += 1
        raise TimeoutError("relation update timed out")

    _patch_settings(monkeypatch, settings)
    monkeypatch.setattr(ingestion_nodes.relations, "update_document_relations", _raise)

    result = ingestion_nodes.update_document_relations_node(
        {
            "document_id": FIXED_DOCUMENT_ID,
            "summary_records": [
                {
                    "summary_type": "document",
                    "content": "Document summary",
                }
            ],
        }
    )

    assert calls == 2
    assert result.get("status") != "failed"
    assert result["relation_update_result"]["status"] == "warning"
    assert result["relation_update_result"]["error_code"] == "relation_update_retry_exhausted"
    assert result["retry_attempts"] == {"update_document_relations": 2}


def test_mark_ready_node_updates_completion_metadata(monkeypatch):
    settings = _test_settings()
    fake_client = FakeSupabaseClient(documents=[_document_row(status="processing")])

    _patch_settings(monkeypatch, settings)
    monkeypatch.setattr(ingestion_nodes, "create_supabase_client", lambda settings=None: fake_client)

    result = ingestion_nodes.mark_ready_node(
        {
            "document_id": FIXED_DOCUMENT_ID,
            "status": "processing",
            "total_pages": 2,
            "total_chunks": 2,
            "parser_name": "fake-parser",
            "parser_version": "1.0.0",
            "chunking_strategy": "fixed_token",
            "chunking_version": "v1",
            "embedding_model": settings.SHOPAIKEY_EMBEDDING_MODEL,
            "embedding_dimension": 3,
            "qdrant_collection": settings.QDRANT_COLLECTION,
        }
    )

    assert fake_client.events[0][0] == "update"
    payload = fake_client.events[0][2]
    assert payload["status"] == "ready"
    assert payload["error_message"] is None
    assert isinstance(payload["indexed_at"], str)
    assert isinstance(payload["updated_at"], str)
    assert payload["indexed_at"] is not None
    assert result["status"] == "ready"
    assert result["error_message"] is None


def test_mark_failed_node_updates_failed_status_and_error_message(monkeypatch):
    settings = _test_settings()
    fake_client = FakeSupabaseClient(documents=[_document_row(status="processing")])

    _patch_settings(monkeypatch, settings)
    monkeypatch.setattr(ingestion_nodes, "create_supabase_client", lambda settings=None: fake_client)

    result = ingestion_nodes.mark_failed_node(
        {"document_id": FIXED_DOCUMENT_ID, "status": "processing"},
        error_message="Parser failed on page 2",
    )

    assert fake_client.events[0][0] == "update"
    payload = fake_client.events[0][2]
    assert payload["status"] == "failed"
    assert payload["error_message"] == "Parser failed on page 2"
    assert result["status"] == "failed"
    assert result["error_message"] == "Parser failed on page 2"


def test_build_ingestion_graph_invokes_nodes_in_required_order(monkeypatch):
    settings = _test_settings()
    call_order: list[str] = []
    initial_state: dict[str, object] = {}

    def _record_node(
        node_name: str,
        output: dict[str, object],
    ):
        def _node(state: IngestionState) -> dict[str, object]:
            call_order.append(node_name)
            if node_name == "load_document_record":
                initial_state.update(dict(state))
            return output

        return _node

    monkeypatch.setattr(
        ingestion_nodes,
        "load_document_record_node",
        _record_node(
            "load_document_record",
            {
                "document_id": FIXED_DOCUMENT_ID,
                "status": "uploaded",
                "document_record": _document_row(),
            },
        ),
    )
    monkeypatch.setattr(
        ingestion_nodes,
        "mark_processing_node",
        _record_node("mark_processing", {"status": "processing"}),
    )
    monkeypatch.setattr(
        ingestion_nodes,
        "parse_document_node",
        _record_node("parse_document", {"parsed_document": _parsed_document()}),
    )
    monkeypatch.setattr(
        ingestion_nodes,
        "chunk_document_node",
        _record_node("chunk_document", {"chunks": [_chunk_record(chunk_index=0, content="chunk zero")]})
    )
    monkeypatch.setattr(
        ingestion_nodes,
        "save_chunks_node",
        _record_node(
            "save_chunks",
            {
                "chunks": [
                    {
                        "id": "chunk-1",
                        "chunk_index": 0,
                        "content": "chunk zero",
                    }
                ],
                "total_chunks": 1,
            },
        ),
    )
    monkeypatch.setattr(
        ingestion_nodes,
        "summarize_document_node",
        _record_node(
            "summarize_document",
            {
                "summary_records": [
                    {
                        "summary_type": "document",
                        "content": "Document summary",
                    }
                ]
            },
        ),
    )
    monkeypatch.setattr(
        ingestion_nodes,
        "embed_chunks_node",
        _record_node("embed_chunks", {"embeddings": [[0.1, 0.2, 0.3]], "embedding_model": "model", "embedding_dimension": 3}),
    )
    monkeypatch.setattr(
        ingestion_nodes,
        "upsert_qdrant_node",
        _record_node(
            "upsert_qdrant",
            {
                "chunks": [
                    {
                        "id": "chunk-1",
                        "chunk_index": 0,
                        "content": "chunk zero",
                        "qdrant_point_id": "chunk-1",
                    }
                ],
                "qdrant_collection": settings.QDRANT_COLLECTION,
            },
        ),
    )
    monkeypatch.setattr(
        ingestion_nodes,
        "update_document_relations_node",
        _record_node(
            "update_document_relations",
            {
                "relation_update_result": {
                    "status": "updated",
                    "accepted_relation_count": 0,
                }
            },
        ),
    )
    monkeypatch.setattr(
        ingestion_nodes,
        "mark_ready_node",
        _record_node(
            "mark_ready",
            {
                "status": "ready",
                "error_message": None,
                "qdrant_collection": settings.QDRANT_COLLECTION,
            },
        ),
    )
    monkeypatch.setattr(
        ingestion_nodes,
        "mark_failed_node",
        lambda state, error_message=None: pytest.fail("mark_failed should not run on the success path"),
    )

    graph = build_ingestion_graph(settings=settings)
    result = graph.invoke({"document_id": FIXED_DOCUMENT_ID})

    assert initial_state == {"document_id": FIXED_DOCUMENT_ID}
    assert call_order == [
        "load_document_record",
        "mark_processing",
        "parse_document",
        "chunk_document",
        "save_chunks",
        "summarize_document",
        "embed_chunks",
        "upsert_qdrant",
        "update_document_relations",
        "mark_ready",
    ]
    assert result["status"] == "ready"
    assert result["qdrant_collection"] == settings.QDRANT_COLLECTION
    assert [event["node_name"] for event in result["workflow_trace"]] == call_order
    assert all(event["attempt"] == 1 for event in result["workflow_trace"])
    assert all("duration_ms" in event for event in result["workflow_trace"])
    assert "chunk zero" not in str(result["workflow_trace"])


def test_build_ingestion_graph_routes_parse_failure_to_mark_failed(monkeypatch):
    settings = _test_settings()
    call_order: list[str] = []
    mark_failed_input: dict[str, object] = {}

    def _record_node(
        node_name: str,
        output: dict[str, object],
    ):
        def _node(state: IngestionState) -> dict[str, object]:
            call_order.append(node_name)
            return output

        return _node

    monkeypatch.setattr(
        ingestion_nodes,
        "load_document_record_node",
        _record_node(
            "load_document_record",
            {
                "document_id": FIXED_DOCUMENT_ID,
                "status": "uploaded",
                "document_record": _document_row(),
            },
        ),
    )
    monkeypatch.setattr(
        ingestion_nodes,
        "mark_processing_node",
        _record_node("mark_processing", {"status": "processing"}),
    )
    monkeypatch.setattr(
        ingestion_nodes,
        "parse_document_node",
        _record_node(
            "parse_document",
            {"status": "failed", "error_message": "parse exploded"},
        ),
    )
    monkeypatch.setattr(
        ingestion_nodes,
        "chunk_document_node",
        lambda state: pytest.fail("chunk_document should not run after a fatal parse failure"),
    )
    monkeypatch.setattr(
        ingestion_nodes,
        "save_chunks_node",
        lambda state: pytest.fail("save_chunks should not run after a fatal parse failure"),
    )
    monkeypatch.setattr(
        ingestion_nodes,
        "embed_chunks_node",
        lambda state: pytest.fail("embed_chunks should not run after a fatal parse failure"),
    )
    monkeypatch.setattr(
        ingestion_nodes,
        "upsert_qdrant_node",
        lambda state: pytest.fail("upsert_qdrant should not run after a fatal parse failure"),
    )
    monkeypatch.setattr(
        ingestion_nodes,
        "mark_ready_node",
        lambda state: pytest.fail("mark_ready should not run after a fatal parse failure"),
    )

    def _mark_failed(state: IngestionState, error_message: str | None = None) -> dict[str, object]:
        call_order.append("mark_failed")
        mark_failed_input.update(dict(state))
        return {
            "status": "failed",
            "error_message": error_message or state.get("error_message"),
        }

    monkeypatch.setattr(ingestion_nodes, "mark_failed_node", _mark_failed)

    graph = build_ingestion_graph(settings=settings)
    result = graph.invoke({"document_id": FIXED_DOCUMENT_ID})

    assert call_order == [
        "load_document_record",
        "mark_processing",
        "parse_document",
        "mark_failed",
    ]
    assert mark_failed_input["error_message"] == "parse exploded"
    assert result["status"] == "failed"
    assert result["error_message"] == "parse exploded"
    assert [event["node_name"] for event in result["workflow_trace"]] == [
        "load_document_record",
        "mark_processing",
        "parse_document",
        "mark_failed",
    ]
    assert result["workflow_trace"][2]["status"] == "failed"
    assert result["workflow_trace"][2]["error_code"] == "parse_document_failed"
    assert "parse exploded" not in str(result["workflow_trace"])


def test_ingestion_nodes_public_surface_remains_available():
    public_names = {
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
    }

    for name in public_names:
        assert callable(getattr(ingestion_nodes, name))
