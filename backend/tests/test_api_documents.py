from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.api.routes import documents as documents_route
from app.core.config import Settings
from app.main import create_app
from app.models.schemas import DocumentResponse
from app.services.hashing import compute_sha256
from app.services import documents as document_service


FIXED_DOCUMENT_ID = UUID("11111111-1111-1111-1111-111111111111")
SECOND_DOCUMENT_ID = UUID("22222222-2222-2222-2222-222222222222")
THIRD_DOCUMENT_ID = UUID("33333333-3333-3333-3333-333333333333")


def _test_settings() -> Settings:
    return Settings(
        _env_file=None,
        SUPABASE_STORAGE_BUCKET="documents",
        QDRANT_COLLECTION="document_chunks_v1",
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
        "created_at": created_at
        or datetime(2026, 6, 18, 8, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2026, 6, 18, 8, 0, tzinfo=timezone.utc),
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
        bucket_name: str = "documents",
    ) -> None:
        self.tables: dict[str, list[dict[str, object]]] = {
            "documents": list(documents or [])
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
    row = _document_row(document_id=FIXED_DOCUMENT_ID, file_hash="abc123")
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
    assert by_hash is not None
    assert by_hash.id == FIXED_DOCUMENT_ID


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
    captured: dict[str, object] = {}

    _patch_route_settings(monkeypatch, settings)
    monkeypatch.setattr(
        document_service,
        "_resolve_supabase_client",
        lambda supabase_client=None: fake_client,
    )

    def _fake_runner(document_id: UUID, *, settings: Settings) -> None:
        captured["document_id"] = document_id
        captured["settings"] = settings

    monkeypatch.setattr(documents_route, "run_document_index", _fake_runner)

    app = _test_app(settings)

    with TestClient(app) as test_client:
        response = test_client.post(f"/api/documents/{FIXED_DOCUMENT_ID}/index")

    assert response.status_code == 202
    assert response.json() == {
        "document_id": str(FIXED_DOCUMENT_ID),
        "status": "processing",
    }
    assert captured["document_id"] == FIXED_DOCUMENT_ID
    assert captured["settings"] == settings


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
