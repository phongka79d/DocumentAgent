from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.api.routes import documents as documents_route
from app.core.config import Settings
from app.main import create_app
from app.models.schemas import DocumentChunkResponse, DocumentResponse
from app.services.hashing import compute_sha256
from app.services import chunks as chunk_service
from app.services import documents as document_service
from app.services import relations as relation_service
from app.services import summaries as summary_service


FIXED_DOCUMENT_ID = UUID("11111111-1111-1111-1111-111111111111")
SECOND_DOCUMENT_ID = UUID("22222222-2222-2222-2222-222222222222")
THIRD_DOCUMENT_ID = UUID("33333333-3333-3333-3333-333333333333")


def _test_settings() -> Settings:
    return Settings(
        _env_file=None,
        SUPABASE_STORAGE_BUCKET="documents",
        QDRANT_COLLECTION="document_chunks_v1",
        ENABLE_WORKFLOW_TRACING=False,
        ENSURE_QDRANT_PAYLOAD_INDEXES_ON_STARTUP=False,
    )


def _document_row(
    *,
    document_id: UUID,
    file_hash: str,
    file_name: str = "report.pdf",
    status: str = "uploaded",
    storage_path: str | None = None,
    title: str | None = "Quarterly report",
    created_at: datetime | str | None = None,
    qdrant_collection: str | None = None,
    error_code: str | None = None,
) -> dict[str, object]:
    return {
        "id": str(document_id),
        "title": title,
        "file_name": file_name,
        "mime_type": "application/pdf",
        "file_size": 123,
        "file_hash": file_hash,
        "storage_path": storage_path
        or f"documents/{document_id}/original/{file_name}",
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
        "error_code": error_code,
        "created_at": created_at
        or datetime(2026, 6, 18, 8, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2026, 6, 18, 8, 0, tzinfo=timezone.utc),
    }


def _chunk_row(
    *,
    document_id: UUID,
    chunk_id: UUID,
    chunk_index: int,
    content: str,
    content_hash: str = "chunk-hash",
    token_count: int = 42,
    chunk_type: str = "smart_section",
    heading: str | None = "Overview",
    section_path: list[str] | None = None,
    page_start: int | None = 1,
    page_end: int | None = 1,
    token_start: int | None = 0,
    token_end: int | None = 42,
    qdrant_point_id: str | None = "point-1",
    metadata: dict[str, object] | None = None,
    created_at: datetime | str | None = None,
) -> dict[str, object]:
    return {
        "id": chunk_id,
        "document_id": str(document_id),
        "chunk_index": chunk_index,
        "content": content,
        "content_hash": content_hash,
        "token_count": token_count,
        "chunk_type": chunk_type,
        "heading": heading,
        "section_path": section_path if section_path is not None else ["Overview"],
        "page_start": page_start,
        "page_end": page_end,
        "token_start": token_start,
        "token_end": token_end,
        "qdrant_point_id": qdrant_point_id,
        "metadata": metadata if metadata is not None else {"source": "test"},
        "created_at": created_at
        or datetime(2026, 6, 18, 8, 30, tzinfo=timezone.utc),
    }


@dataclass
class FakeResponse:
    data: list[dict[str, object]] | dict[str, object] | None = None


@dataclass
class FakeStorageBucket:
    upload_calls: list[tuple[str, bytes, dict[str, object] | None]] = field(
        default_factory=list
    )
    remove_calls: list[list[str]] = field(default_factory=list)

    def upload(
        self,
        path: str,
        file: bytes,
        file_options: dict[str, object] | None = None,
    ) -> dict[str, object]:
        self.upload_calls.append((path, file, file_options))
        return {"path": path}

    def remove(self, paths: list[str]) -> list[dict[str, object]]:
        self.remove_calls.append(paths)
        return [{"path": path} for path in paths]


class FakeStorageNamespace:
    def __init__(self, bucket: FakeStorageBucket, bucket_name: str) -> None:
        self._bucket = bucket
        self.bucket_name = bucket_name

    def from_(self, bucket_name: str) -> FakeStorageBucket:
        assert bucket_name == self.bucket_name
        return self._bucket


class FakeTableQuery:
    def __init__(self, client: "FakeSupabaseClient", table_name: str) -> None:
        self.client = client
        self.table_name = table_name
        self.operation = "select"
        self.payload: dict[str, object] | None = None
        self.filters: list[tuple[str, object]] = []
        self.limit_count: int | None = None
        self.order_clause: tuple[str, bool] | None = None

    def select(self, *columns: str, count=None, head=None):
        self.operation = "select"
        return self

    def insert(self, json, *, count=None, returning=None, upsert=False, default_to_null=True):
        self.operation = "insert"
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
            self.client.events.append(("insert", self.table_name, self.payload))
            self.client.tables.setdefault(self.table_name, []).append(self.payload)
            return FakeResponse(data=[self.payload])

        if self.operation == "delete":
            self.client.events.append(
                (
                    "delete",
                    self.table_name,
                    [(column, value) for column, value in self.filters],
                )
            )
            self.client.tables[self.table_name] = [
                row
                for row in self.client.tables.get(self.table_name, [])
                if row not in rows
            ]
            return FakeResponse(data=rows)

        raise AssertionError(f"Unsupported fake operation: {self.operation}")


class FakeSupabaseClient:
    def __init__(
        self,
        *,
        documents: list[dict[str, object]] | None = None,
        document_chunks: list[dict[str, object]] | None = None,
        bucket_name: str = "documents",
    ) -> None:
        self.tables: dict[str, list[dict[str, object]]] = {
            "documents": list(documents or []),
            "document_chunks": list(document_chunks or []),
            "document_summaries": [],
        }
        self.events: list[tuple[object, ...]] = []
        self._bucket = FakeStorageBucket()
        self.storage = FakeStorageNamespace(self._bucket, bucket_name)

    def table(self, table_name: str) -> FakeTableQuery:
        return FakeTableQuery(self, table_name)


class FakeQdrantClient:
    def __init__(self) -> None:
        self.delete_calls: list[dict[str, object]] = []

    def delete(self, *, collection_name, points_selector, wait=True, ordering=None, shard_key_selector=None, timeout=None, **kwargs):
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


class HttpStatusError(RuntimeError):
    def __init__(self, status_code: int) -> None:
        super().__init__(f"http {status_code}")
        self.response = type("Response", (), {"status_code": status_code})()


class FakeIngestionGraph:
    def __init__(self, result: dict[str, object] | None = None) -> None:
        self.result = result or {"status": "ready"}
        self.invocations: list[dict[str, object]] = []

    def invoke(self, state: dict[str, object]) -> dict[str, object]:
        self.invocations.append(dict(state))
        return dict(self.result)


def _unexpected_provider_client_factory(name: str):
    def _factory(*args, **kwargs):
        pytest.fail(f"{name} client should not be called")

    return _factory


def test_list_documents_returns_document_models_in_created_order(monkeypatch):
    settings = _test_settings()
    rows = [
        _document_row(
            document_id=SECOND_DOCUMENT_ID,
            file_hash="bbb",
            created_at=datetime(2026, 6, 18, 8, 30, tzinfo=timezone.utc),
        ),
        _document_row(
            document_id=FIXED_DOCUMENT_ID,
            file_hash="aaa",
            created_at=datetime(2026, 6, 18, 9, 30, tzinfo=timezone.utc),
        ),
    ]
    client = FakeSupabaseClient(documents=rows)

    documents = document_service.list_documents(settings=settings, supabase_client=client)

    assert [document.id for document in documents] == [FIXED_DOCUMENT_ID, SECOND_DOCUMENT_ID]
    assert all(document.file_name == "report.pdf" for document in documents)


def test_get_document_and_find_document_by_hash_return_expected_rows():
    settings = _test_settings()
    row = _document_row(
        document_id=FIXED_DOCUMENT_ID,
        file_hash="abc123",
        status="failed",
        error_code="embedding_timeout",
    )
    client = FakeSupabaseClient(documents=[row])

    by_id = document_service.get_document(
        FIXED_DOCUMENT_ID,
        settings=settings,
        supabase_client=client,
    )
    by_hash = document_service.find_document_by_hash(
        "abc123",
        settings=settings,
        supabase_client=client,
    )

    assert by_id is not None
    assert by_id.id == FIXED_DOCUMENT_ID
    assert by_id.file_hash == "abc123"
    assert by_id.error_code == "embedding_timeout"
    assert by_hash is not None
    assert by_hash.id == FIXED_DOCUMENT_ID
    assert by_hash.error_code == "embedding_timeout"


def test_upload_original_file_uses_storage_bucket_and_content_type():
    settings = _test_settings()
    client = FakeSupabaseClient()
    storage_path = f"documents/{FIXED_DOCUMENT_ID}/original/report.pdf"

    document_service.upload_original_file(
        storage_path,
        b"document bytes",
        "application/pdf",
        settings=settings,
        supabase_client=client,
    )

    assert client._bucket.upload_calls == [
        (storage_path, b"document bytes", {"content-type": "application/pdf"})
    ]


def test_create_uploaded_document_uses_storage_path_document_id():
    settings = _test_settings()
    client = FakeSupabaseClient()
    storage_path = f"documents/{FIXED_DOCUMENT_ID}/original/report.pdf"

    document = document_service.create_uploaded_document(
        file_name="report.pdf",
        mime_type="application/pdf",
        file_size=123,
        file_hash="abc123",
        storage_path=storage_path,
        title="Quarterly report",
        settings=settings,
        supabase_client=client,
    )

    assert document.id == FIXED_DOCUMENT_ID
    assert document.status == "uploaded"
    assert document.storage_path == storage_path
    assert client.tables["documents"][0]["id"] == str(FIXED_DOCUMENT_ID)
    assert client.tables["documents"][0]["file_hash"] == "abc123"


def test_register_uploaded_document_skips_upload_and_insert_for_duplicate_hash(monkeypatch):
    settings = _test_settings()
    existing_row = _document_row(
        document_id=FIXED_DOCUMENT_ID,
        file_hash="duplicate-hash",
        status="ready",
    )
    client = FakeSupabaseClient(documents=[existing_row])

    def _unexpected_uuid4():
        raise AssertionError("uuid4 should not be called for duplicate uploads")

    monkeypatch.setattr(document_service, "uuid4", _unexpected_uuid4)

    result = document_service.register_uploaded_document(
        file_name="report.pdf",
        mime_type="application/pdf",
        file_size=123,
        file_hash="duplicate-hash",
        file_bytes=b"new bytes that should never upload",
        title="Ignored",
        settings=settings,
        supabase_client=client,
    )

    assert result.duplicate is True
    assert result.document.id == FIXED_DOCUMENT_ID
    assert client._bucket.upload_calls == []
    assert client.events == []


def test_register_uploaded_document_uploads_then_creates_document(monkeypatch):
    settings = _test_settings()
    client = FakeSupabaseClient()

    monkeypatch.setattr(document_service, "uuid4", lambda: THIRD_DOCUMENT_ID)

    result = document_service.register_uploaded_document(
        file_name="report.pdf",
        mime_type="application/pdf",
        file_size=123,
        file_hash="new-hash",
        file_bytes=b"document bytes",
        title="Quarterly report",
        settings=settings,
        supabase_client=client,
    )

    assert result.duplicate is False
    assert result.document.id == THIRD_DOCUMENT_ID
    assert result.document.storage_path == (
        f"documents/{THIRD_DOCUMENT_ID}/original/report.pdf"
    )
    assert client._bucket.upload_calls == [
        (
            f"documents/{THIRD_DOCUMENT_ID}/original/report.pdf",
            b"document bytes",
            {"content-type": "application/pdf"},
        )
    ]
    assert client.events[0][0] == "insert"
    assert client.tables["documents"][0]["id"] == str(THIRD_DOCUMENT_ID)


def test_delete_document_and_file_deletes_qdrant_before_storage_before_row():
    settings = _test_settings()
    row = _document_row(
        document_id=FIXED_DOCUMENT_ID,
        file_hash="delete-me",
        qdrant_collection="custom_collection",
        status="ready",
    )
    client = FakeSupabaseClient(documents=[row])
    qdrant_client = FakeQdrantClient()

    deleted = document_service.delete_document_and_file(
        FIXED_DOCUMENT_ID,
        settings=settings,
        supabase_client=client,
        qdrant_client=qdrant_client,
    )

    assert deleted.id == FIXED_DOCUMENT_ID
    assert qdrant_client.delete_calls[0]["collection_name"] == "custom_collection"
    assert client._bucket.remove_calls == [[row["storage_path"]]]
    assert client.events == [
        ("delete", "documents", [("id", str(FIXED_DOCUMENT_ID))])
    ]
    assert client.tables["documents"] == []


def test_delete_document_and_file_retries_transient_qdrant_delete_failure():
    settings = _test_settings().model_copy(
        update={
            "WORKFLOW_MAX_ATTEMPTS": 3,
            "WORKFLOW_RETRY_BASE_DELAY_SECONDS": 0.0,
            "WORKFLOW_RETRY_MAX_DELAY_SECONDS": 0.0,
        }
    )
    row = _document_row(
        document_id=FIXED_DOCUMENT_ID,
        file_hash="delete-me",
        qdrant_collection="custom_collection",
        status="ready",
    )
    client = FakeSupabaseClient(documents=[row])

    class FlakyQdrantClient(FakeQdrantClient):
        def delete(self, **kwargs):
            self.delete_calls.append(kwargs)
            if len(self.delete_calls) < 3:
                raise TimeoutError("qdrant delete timed out")
            return {"status": "ok"}

    qdrant_client = FlakyQdrantClient()

    document_service.delete_document_and_file(
        FIXED_DOCUMENT_ID,
        settings=settings,
        supabase_client=client,
        qdrant_client=qdrant_client,
    )

    assert len(qdrant_client.delete_calls) == 3
    assert client._bucket.remove_calls == [[row["storage_path"]]]
    assert client.tables["documents"] == []


def test_delete_document_and_file_non_retryable_qdrant_delete_failure_runs_once():
    settings = _test_settings().model_copy(
        update={
            "WORKFLOW_MAX_ATTEMPTS": 3,
            "WORKFLOW_RETRY_BASE_DELAY_SECONDS": 0.0,
            "WORKFLOW_RETRY_MAX_DELAY_SECONDS": 0.0,
        }
    )
    row = _document_row(
        document_id=FIXED_DOCUMENT_ID,
        file_hash="delete-me",
        qdrant_collection="custom_collection",
        status="ready",
    )
    client = FakeSupabaseClient(documents=[row])

    class BadRequestQdrantClient(FakeQdrantClient):
        def delete(self, **kwargs):
            self.delete_calls.append(kwargs)
            raise HttpStatusError(400)

    qdrant_client = BadRequestQdrantClient()

    with pytest.raises(HttpStatusError):
        document_service.delete_document_and_file(
            FIXED_DOCUMENT_ID,
            settings=settings,
            supabase_client=client,
            qdrant_client=qdrant_client,
        )

    assert len(qdrant_client.delete_calls) == 1
    assert client._bucket.remove_calls == []
    assert client.tables["documents"] == [row]


def _patch_route_settings(monkeypatch, settings: Settings) -> None:
    monkeypatch.setattr(documents_route, "get_settings", lambda: settings)


def _test_app(settings: Settings):
    return create_app(settings=settings)


def test_upload_route_rejects_invalid_file_before_service_call(monkeypatch):
    settings = _test_settings()
    _patch_route_settings(monkeypatch, settings)
    monkeypatch.setattr(
        document_service,
        "register_uploaded_document",
        lambda **kwargs: pytest.fail("service should not be called for invalid upload"),
    )

    app = _test_app(settings)

    with TestClient(app) as test_client:
        response = test_client.post(
            "/api/documents/upload",
            files={"file": ("empty.pdf", b"", "application/pdf")},
        )

    assert response.status_code == 400
    assert response.json()["detail"] == "Uploaded file is empty"


def test_upload_route_returns_duplicate_existing_document_response(monkeypatch):
    settings = _test_settings()
    existing_row = _document_row(
        document_id=FIXED_DOCUMENT_ID,
        file_hash=compute_sha256(b"duplicate bytes"),
        status="ready",
    )
    fake_client = FakeSupabaseClient(documents=[existing_row])

    _patch_route_settings(monkeypatch, settings)
    monkeypatch.setattr(
        document_service,
        "_resolve_supabase_client",
        lambda supabase_client=None: fake_client,
    )

    app = _test_app(settings)

    with TestClient(app) as test_client:
        response = test_client.post(
            "/api/documents/upload",
            files={
                "file": (
                    "report.pdf",
                    b"duplicate bytes",
                    "application/pdf",
                )
            },
        )

    assert response.status_code == 200
    assert response.json() == {
        "document_id": str(FIXED_DOCUMENT_ID),
        "status": "ready",
        "duplicate": True,
    }
    assert fake_client._bucket.upload_calls == []
    assert fake_client.events == []


def test_index_route_invokes_runner_with_document_id_only(monkeypatch):
    settings = _test_settings()
    fake_client = FakeSupabaseClient(
        documents=[
            _document_row(
                document_id=FIXED_DOCUMENT_ID,
                file_hash="index-me",
                status="uploaded",
            )
        ]
    )
    fake_graph = FakeIngestionGraph()

    _patch_route_settings(monkeypatch, settings)
    monkeypatch.setattr(
        document_service,
        "_resolve_supabase_client",
        lambda supabase_client=None: fake_client,
    )
    monkeypatch.setattr(
        documents_route,
        "build_ingestion_graph",
        lambda settings=None: fake_graph,
    )

    app = _test_app(settings)

    with TestClient(app) as test_client:
        response = test_client.post(f"/api/documents/{FIXED_DOCUMENT_ID}/index")

    assert response.status_code == 202
    assert response.json() == {
        "document_id": str(FIXED_DOCUMENT_ID),
        "status": "processing",
    }
    assert fake_graph.invocations == [{"document_id": str(FIXED_DOCUMENT_ID)}]


def test_reindex_route_cleans_old_vectors_and_chunks_before_graph_invocation(monkeypatch):
    settings = _test_settings()
    row = _document_row(
        document_id=FIXED_DOCUMENT_ID,
        file_hash="reindex-me",
        qdrant_collection="custom_collection",
        status="ready",
    )
    fake_client = FakeSupabaseClient(
        documents=[row],
        document_chunks=[
            {
                "id": "chunk-1",
                "document_id": str(FIXED_DOCUMENT_ID),
                "chunk_index": 0,
                "content": "old chunk",
            }
        ],
    )
    fake_graph = FakeIngestionGraph()
    call_order: list[object] = []

    def _delete_vectors(
        document_id: UUID,
        *,
        settings: Settings,
        qdrant_collection: str | None = None,
        qdrant_client=None,
    ) -> None:
        call_order.append(("vectors", document_id, qdrant_collection))

    def _delete_chunks(
        document_id: UUID,
        *,
        settings: Settings,
        supabase_client=None,
    ) -> None:
        call_order.append(("chunks", document_id))

    def _invoke_graph(state: dict[str, object]) -> dict[str, object]:
        call_order.append(("graph", dict(state)))
        fake_graph.invocations.append(dict(state))
        return dict(fake_graph.result)

    fake_graph.invoke = _invoke_graph  # type: ignore[method-assign]

    _patch_route_settings(monkeypatch, settings)
    monkeypatch.setattr(
        document_service,
        "_resolve_supabase_client",
        lambda supabase_client=None: fake_client,
    )
    monkeypatch.setattr(documents_route, "delete_document_vectors", _delete_vectors)
    monkeypatch.setattr(documents_route, "delete_document_chunks", _delete_chunks)
    monkeypatch.setattr(
        documents_route,
        "build_ingestion_graph",
        lambda settings=None: fake_graph,
    )

    app = _test_app(settings)

    with TestClient(app) as test_client:
        response = test_client.post(f"/api/documents/{FIXED_DOCUMENT_ID}/reindex")

    assert response.status_code == 202
    assert response.json() == {
        "document_id": str(FIXED_DOCUMENT_ID),
        "status": "processing",
    }
    assert call_order == [
        ("vectors", FIXED_DOCUMENT_ID, "custom_collection"),
        ("chunks", FIXED_DOCUMENT_ID),
        ("graph", {"document_id": str(FIXED_DOCUMENT_ID)}),
    ]
    assert fake_graph.invocations == [{"document_id": str(FIXED_DOCUMENT_ID)}]


def test_reindex_cleanup_retries_transient_qdrant_delete_failure():
    settings = _test_settings().model_copy(
        update={
            "WORKFLOW_MAX_ATTEMPTS": 3,
            "WORKFLOW_RETRY_BASE_DELAY_SECONDS": 0.0,
            "WORKFLOW_RETRY_MAX_DELAY_SECONDS": 0.0,
        }
    )

    class FlakyQdrantClient(FakeQdrantClient):
        def delete(self, **kwargs):
            self.delete_calls.append(kwargs)
            if len(self.delete_calls) < 3:
                raise ConnectionError("qdrant delete connection failed")
            return {"status": "ok"}

    qdrant_client = FlakyQdrantClient()

    documents_route.delete_document_vectors(
        FIXED_DOCUMENT_ID,
        settings=settings,
        qdrant_collection="custom_collection",
        qdrant_client=qdrant_client,
    )

    assert len(qdrant_client.delete_calls) == 3
    assert qdrant_client.delete_calls[-1]["collection_name"] == "custom_collection"


def test_reindex_cleanup_non_retryable_qdrant_delete_failure_runs_once():
    settings = _test_settings().model_copy(
        update={
            "WORKFLOW_MAX_ATTEMPTS": 3,
            "WORKFLOW_RETRY_BASE_DELAY_SECONDS": 0.0,
            "WORKFLOW_RETRY_MAX_DELAY_SECONDS": 0.0,
        }
    )

    class BadRequestQdrantClient(FakeQdrantClient):
        def delete(self, **kwargs):
            self.delete_calls.append(kwargs)
            raise HttpStatusError(400)

    qdrant_client = BadRequestQdrantClient()

    with pytest.raises(HttpStatusError):
        documents_route.delete_document_vectors(
            FIXED_DOCUMENT_ID,
            settings=settings,
            qdrant_collection="custom_collection",
            qdrant_client=qdrant_client,
        )

    assert len(qdrant_client.delete_calls) == 1


def test_delete_route_deletes_qdrant_before_storage_before_row(monkeypatch):
    settings = _test_settings()
    row = _document_row(
        document_id=FIXED_DOCUMENT_ID,
        file_hash="delete-me",
        qdrant_collection="custom_collection",
        status="ready",
    )
    fake_client = FakeSupabaseClient(documents=[row])
    fake_qdrant_client = FakeQdrantClient()

    _patch_route_settings(monkeypatch, settings)
    monkeypatch.setattr(
        document_service,
        "_resolve_supabase_client",
        lambda supabase_client=None: fake_client,
    )
    monkeypatch.setattr(
        document_service,
        "_resolve_qdrant_client",
        lambda qdrant_client=None: fake_qdrant_client,
    )

    app = _test_app(settings)

    with TestClient(app) as test_client:
        response = test_client.delete(f"/api/documents/{FIXED_DOCUMENT_ID}")

    assert response.status_code == 200
    assert response.json()["id"] == str(FIXED_DOCUMENT_ID)
    assert fake_qdrant_client.delete_calls[0]["collection_name"] == "custom_collection"
    assert fake_client._bucket.remove_calls == [[row["storage_path"]]]
    assert fake_client.events == [
        ("delete", "documents", [("id", str(FIXED_DOCUMENT_ID))])
    ]
    assert fake_client.tables["documents"] == []


def test_list_chunks_by_document_returns_ordered_document_chunk_responses_and_normalizes_ids():
    settings = _test_settings()
    first_chunk_id = UUID("44444444-4444-4444-4444-444444444444")
    second_chunk_id = UUID("55555555-5555-5555-5555-555555555555")
    fake_client = FakeSupabaseClient(
        documents=[
            _document_row(
                document_id=FIXED_DOCUMENT_ID,
                file_hash="chunk-source",
                status="ready",
            )
        ],
        document_chunks=[
            _chunk_row(
                document_id=FIXED_DOCUMENT_ID,
                chunk_id=second_chunk_id,
                chunk_index=1,
                content="chunk one",
                heading="Second",
                section_path=["Section 2"],
                metadata={"source": "second"},
            ),
            _chunk_row(
                document_id=FIXED_DOCUMENT_ID,
                chunk_id=first_chunk_id,
                chunk_index=0,
                content="chunk zero",
                heading="First",
                section_path=["Section 1"],
                metadata={"source": "first"},
            ),
        ],
    )

    chunks = chunk_service.list_chunks_by_document(
        FIXED_DOCUMENT_ID,
        settings=settings,
        supabase_client=fake_client,
    )

    assert all(isinstance(chunk, DocumentChunkResponse) for chunk in chunks)
    assert [chunk.chunk_index for chunk in chunks] == [0, 1]
    assert [chunk.id for chunk in chunks] == [str(first_chunk_id), str(second_chunk_id)]
    assert [chunk.document_id for chunk in chunks] == [
        str(FIXED_DOCUMENT_ID),
        str(FIXED_DOCUMENT_ID),
    ]
    assert chunks[0].heading == "First"
    assert chunks[0].section_path == ["Section 1"]
    assert chunks[0].metadata == {"source": "first"}


def test_list_chunks_by_document_returns_empty_list_when_document_has_no_chunks():
    settings = _test_settings()
    fake_client = FakeSupabaseClient(
        documents=[
            _document_row(
                document_id=FIXED_DOCUMENT_ID,
                file_hash="chunk-source",
                status="ready",
            )
        ],
        document_chunks=[],
    )

    chunks = chunk_service.list_chunks_by_document(
        FIXED_DOCUMENT_ID,
        settings=settings,
        supabase_client=fake_client,
    )

    assert chunks == []


def test_get_document_chunks_route_returns_typed_rows_and_does_not_call_external_providers(monkeypatch):
    settings = _test_settings()
    first_chunk_id = UUID("66666666-6666-6666-6666-666666666666")
    second_chunk_id = UUID("77777777-7777-7777-7777-777777777777")
    fake_client = FakeSupabaseClient(
        documents=[
            _document_row(
                document_id=FIXED_DOCUMENT_ID,
                file_hash="route-source",
                status="ready",
            )
        ],
        document_chunks=[
            _chunk_row(
                document_id=FIXED_DOCUMENT_ID,
                chunk_id=second_chunk_id,
                chunk_index=1,
                content="chunk one",
                heading="Second",
                section_path=["Section 2"],
                metadata={"source": "second"},
            ),
            _chunk_row(
                document_id=FIXED_DOCUMENT_ID,
                chunk_id=first_chunk_id,
                chunk_index=0,
                content="chunk zero",
                heading="First",
                section_path=["Section 1"],
                metadata={"source": "first"},
            ),
        ],
    )

    _patch_route_settings(monkeypatch, settings)
    monkeypatch.setattr(
        document_service,
        "_resolve_supabase_client",
        lambda supabase_client=None: fake_client,
    )
    monkeypatch.setattr(
        chunk_service,
        "_resolve_supabase_client",
        lambda supabase_client=None: fake_client,
    )
    monkeypatch.setattr(
        "app.services.qdrant_client.create_qdrant_client",
        _unexpected_provider_client_factory("Qdrant"),
    )
    monkeypatch.setattr(
        "app.services.shopaikey_client.create_shopaikey_client",
        _unexpected_provider_client_factory("ShopAIKey"),
    )
    monkeypatch.setattr(
        "app.services.jina_client.create_jina_client",
        _unexpected_provider_client_factory("Jina"),
    )

    app = _test_app(settings)

    with TestClient(app) as test_client:
        response = test_client.get(f"/api/documents/{FIXED_DOCUMENT_ID}/chunks")

    assert response.status_code == 200
    payload = response.json()
    assert payload["document_id"] == str(FIXED_DOCUMENT_ID)
    assert [chunk["chunk_index"] for chunk in payload["chunks"]] == [0, 1]
    assert payload["chunks"][0]["id"] == str(first_chunk_id)
    assert payload["chunks"][0]["document_id"] == str(FIXED_DOCUMENT_ID)
    assert payload["chunks"][0]["content"] == "chunk zero"
    assert payload["chunks"][0]["section_path"] == ["Section 1"]
    assert set(payload["chunks"][0]) == {
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
        "qdrant_point_id",
        "metadata",
        "created_at",
    }


def test_get_document_chunks_route_returns_404_for_unknown_document_without_external_provider_calls(monkeypatch):
    settings = _test_settings()
    fake_client = FakeSupabaseClient(documents=[], document_chunks=[])

    _patch_route_settings(monkeypatch, settings)
    monkeypatch.setattr(
        document_service,
        "_resolve_supabase_client",
        lambda supabase_client=None: fake_client,
    )
    monkeypatch.setattr(
        chunk_service,
        "_resolve_supabase_client",
        lambda supabase_client=None: fake_client,
    )
    monkeypatch.setattr(
        documents_route,
        "list_chunks_by_document",
        lambda *args, **kwargs: pytest.fail(
            "chunk lookup should not run when the document is missing"
        ),
    )
    monkeypatch.setattr(
        "app.services.qdrant_client.create_qdrant_client",
        _unexpected_provider_client_factory("Qdrant"),
    )
    monkeypatch.setattr(
        "app.services.shopaikey_client.create_shopaikey_client",
        _unexpected_provider_client_factory("ShopAIKey"),
    )
    monkeypatch.setattr(
        "app.services.jina_client.create_jina_client",
        _unexpected_provider_client_factory("Jina"),
    )

    app = _test_app(settings)

    with TestClient(app) as test_client:
        response = test_client.get(f"/api/documents/{THIRD_DOCUMENT_ID}/chunks")

    assert response.status_code == 404
    assert response.json()["detail"] == f"Document {THIRD_DOCUMENT_ID} not found"


def test_get_document_summaries_route_returns_typed_ordered_rows_without_external_provider_calls(monkeypatch):
    settings = _test_settings()
    summary_a_id = UUID("88888888-8888-8888-8888-888888888888")
    summary_b_id = UUID("99999999-9999-9999-9999-999999999999")
    summary_c_id = UUID("aaaaaaaa-1111-4111-8111-aaaaaaaaaaaa")
    fake_client = FakeSupabaseClient(
        documents=[
            _document_row(
                document_id=FIXED_DOCUMENT_ID,
                file_hash="summary-source",
                status="ready",
            )
        ],
    )
    fake_client.tables["document_summaries"] = [
        {
            "id": str(summary_b_id),
            "document_id": str(FIXED_DOCUMENT_ID),
            "summary_type": "section",
            "heading": "Zeta",
            "section_path": ["Zeta"],
            "content": "Zeta summary",
            "source_chunk_ids": [],
            "model": "summary-model",
            "created_at": datetime(2026, 6, 18, 8, 45, tzinfo=timezone.utc),
            "updated_at": datetime(2026, 6, 18, 8, 45, tzinfo=timezone.utc),
        },
        {
            "id": str(summary_a_id),
            "document_id": str(FIXED_DOCUMENT_ID),
            "summary_type": "document",
            "heading": None,
            "section_path": [],
            "content": "Document summary",
            "source_chunk_ids": [],
            "model": "summary-model",
            "created_at": datetime(2026, 6, 18, 8, 40, tzinfo=timezone.utc),
            "updated_at": datetime(2026, 6, 18, 8, 40, tzinfo=timezone.utc),
        },
        {
            "id": str(summary_c_id),
            "document_id": str(FIXED_DOCUMENT_ID),
            "summary_type": "section",
            "heading": "Alpha",
            "section_path": ["Alpha"],
            "content": "Alpha summary",
            "source_chunk_ids": [str(UUID("66666666-6666-6666-6666-666666666666"))],
            "model": "summary-model",
            "created_at": datetime(2026, 6, 18, 8, 42, tzinfo=timezone.utc),
            "updated_at": datetime(2026, 6, 18, 8, 42, tzinfo=timezone.utc),
        },
    ]

    _patch_route_settings(monkeypatch, settings)
    monkeypatch.setattr(
        document_service,
        "_resolve_supabase_client",
        lambda supabase_client=None: fake_client,
    )
    monkeypatch.setattr(
        summary_service,
        "create_supabase_client",
        lambda settings=None: fake_client,
    )
    monkeypatch.setattr(
        "app.services.qdrant_client.create_qdrant_client",
        _unexpected_provider_client_factory("Qdrant"),
    )
    monkeypatch.setattr(
        "app.services.shopaikey_client.create_shopaikey_client",
        _unexpected_provider_client_factory("ShopAIKey"),
    )
    monkeypatch.setattr(
        "app.services.jina_client.create_jina_client",
        _unexpected_provider_client_factory("Jina"),
    )

    app = _test_app(settings)

    with TestClient(app) as test_client:
        response = test_client.get(f"/api/documents/{FIXED_DOCUMENT_ID}/summaries")

    assert response.status_code == 200
    payload = response.json()
    assert payload["document_id"] == str(FIXED_DOCUMENT_ID)
    assert [row["summary_type"] for row in payload["summaries"]] == [
        "document",
        "section",
        "section",
    ]
    assert [row["section_path"] for row in payload["summaries"]] == [
        [],
        ["Alpha"],
        ["Zeta"],
    ]
    assert payload["summaries"][0]["content"] == "Document summary"
    assert payload["summaries"][1]["source_chunk_ids"] == [
        "66666666-6666-6666-6666-666666666666"
    ]


def test_get_document_relations_route_returns_both_directions_with_normalized_related_id(monkeypatch):
    settings = _test_settings()
    relation_id_a = UUID("aaaaaaaa-1111-4111-8111-aaaaaaaaaaaa")
    relation_id_b = UUID("bbbbbbbb-2222-4222-8222-bbbbbbbbbbbb")
    fake_client = FakeSupabaseClient(
        documents=[
            _document_row(
                document_id=FIXED_DOCUMENT_ID,
                file_hash="relation-source",
                status="ready",
            )
        ],
    )

    _patch_route_settings(monkeypatch, settings)
    monkeypatch.setattr(
        document_service,
        "_resolve_supabase_client",
        lambda supabase_client=None: fake_client,
    )
    monkeypatch.setattr(
        relation_service,
        "list_relations",
        lambda document_id: [
            {
                "id": str(relation_id_a),
                "source_document_id": str(FIXED_DOCUMENT_ID),
                "target_document_id": str(SECOND_DOCUMENT_ID),
                "relation_type": "supports",
                "description": "Requested document supports the related document.",
                "evidence_chunk_ids": [
                    "66666666-6666-6666-6666-666666666666"
                ],
                "confidence": 0.8,
                "model": "relation-model",
                "created_at": datetime(2026, 6, 18, 8, 45, tzinfo=timezone.utc),
                "updated_at": datetime(2026, 6, 18, 8, 45, tzinfo=timezone.utc),
            },
            {
                "id": str(relation_id_b),
                "source_document_id": str(THIRD_DOCUMENT_ID),
                "target_document_id": str(FIXED_DOCUMENT_ID),
                "relation_type": "references",
                "description": "Related document references the requested document.",
                "evidence_chunk_ids": [
                    "77777777-7777-7777-7777-777777777777"
                ],
                "confidence": 0.7,
                "model": "relation-model",
                "created_at": datetime(2026, 6, 18, 8, 46, tzinfo=timezone.utc),
                "updated_at": datetime(2026, 6, 18, 8, 46, tzinfo=timezone.utc),
            },
        ],
    )
    monkeypatch.setattr(
        "app.services.qdrant_client.create_qdrant_client",
        _unexpected_provider_client_factory("Qdrant"),
    )
    monkeypatch.setattr(
        "app.services.shopaikey_client.create_shopaikey_client",
        _unexpected_provider_client_factory("ShopAIKey"),
    )
    monkeypatch.setattr(
        "app.services.jina_client.create_jina_client",
        _unexpected_provider_client_factory("Jina"),
    )

    app = _test_app(settings)

    with TestClient(app) as test_client:
        response = test_client.get(f"/api/documents/{FIXED_DOCUMENT_ID}/relations")

    assert response.status_code == 200
    payload = response.json()
    assert payload["document_id"] == str(FIXED_DOCUMENT_ID)
    assert [row["related_document_id"] for row in payload["relations"]] == [
        str(SECOND_DOCUMENT_ID),
        str(THIRD_DOCUMENT_ID),
    ]
    assert payload["relations"][0]["source_document_id"] == str(FIXED_DOCUMENT_ID)
    assert payload["relations"][1]["target_document_id"] == str(FIXED_DOCUMENT_ID)
