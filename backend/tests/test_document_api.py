import io
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import app
from app.schemas.documents import (
    DocumentDetailResponse,
    DocumentListItem,
    DocumentListResponse,
)
from app.services import document_service
from app.services.supabase_service import SupabaseConnectionError


client = TestClient(app)


DOCUMENT_ID = UUID("22222222-2222-4222-8222-222222222222")
UNKNOWN_DOCUMENT_ID = UUID("33333333-3333-4333-8333-333333333333")
CREATED_AT = datetime(2026, 6, 1, 10, 0, tzinfo=timezone.utc)
UPDATED_AT = datetime(2026, 6, 1, 10, 5, tzinfo=timezone.utc)


class UploadStub:
    def __init__(
        self,
        *,
        filename: str = "contract.pdf",
        content: bytes = b"%PDF-1.4 content",
        content_type: str = "application/pdf",
    ) -> None:
        self.filename = filename
        self.content_type = content_type
        self._file = io.BytesIO(content)

    async def read(self) -> bytes:
        return self._file.read()


def _settings() -> SimpleNamespace:
    return SimpleNamespace(
        single_user_id="single_user",
        max_upload_bytes=25_000_000,
    )


def _metadata_row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "id": str(DOCUMENT_ID),
        "user_id": "single_user",
        "file_name": "contract.pdf",
        "file_type": "pdf",
        "storage_path": f"documents/single_user/{DOCUMENT_ID}/contract.pdf",
        "status": "uploaded",
        "chunk_count": 0,
        "created_at": CREATED_AT,
        "updated_at": UPDATED_AT,
        "error_message": None,
    }
    row.update(overrides)
    return row


def test_list_documents_api_returns_documents_contract(monkeypatch) -> None:
    list_mock = Mock(
        return_value=DocumentListResponse(
            documents=[
                DocumentListItem(
                    id=DOCUMENT_ID,
                    file_name="contract.pdf",
                    file_type="pdf",
                    status="uploaded",
                    chunk_count=0,
                    created_at=CREATED_AT,
                    error_message=None,
                )
            ]
        )
    )
    monkeypatch.setattr(
        "app.api.documents.document_service.list_documents",
        list_mock,
    )

    response = client.get("/api/documents")

    assert response.status_code == 200
    body = response.json()
    assert list(body) == ["documents"]
    assert body["documents"] == [
        {
            "id": str(DOCUMENT_ID),
            "file_name": "contract.pdf",
            "file_type": "pdf",
            "status": "uploaded",
            "chunk_count": 0,
            "created_at": "2026-06-01T10:00:00Z",
            "error_message": None,
        }
    ]
    list_mock.assert_called_once_with()


def test_document_detail_api_returns_detail_contract_with_empty_chunks(
    monkeypatch,
) -> None:
    detail_mock = Mock(
        return_value=DocumentDetailResponse(
            id=DOCUMENT_ID,
            file_name="contract.pdf",
            file_type="pdf",
            status="uploaded",
            chunk_count=0,
            created_at=CREATED_AT,
            updated_at=UPDATED_AT,
            error_message=None,
            chunks=[],
        )
    )
    monkeypatch.setattr(
        "app.api.documents.document_service.get_document_detail",
        detail_mock,
    )

    response = client.get(f"/api/documents/{DOCUMENT_ID}")

    assert response.status_code == 200
    assert response.json() == {
        "id": str(DOCUMENT_ID),
        "file_name": "contract.pdf",
        "file_type": "pdf",
        "status": "uploaded",
        "chunk_count": 0,
        "created_at": "2026-06-01T10:00:00Z",
        "updated_at": "2026-06-01T10:05:00Z",
        "error_message": None,
        "chunks": [],
    }
    detail_mock.assert_called_once_with(DOCUMENT_ID)


def test_unknown_document_uuid_returns_404(monkeypatch) -> None:
    detail_mock = Mock(
        side_effect=document_service.DocumentNotFoundError("Document not found.")
    )
    monkeypatch.setattr(
        "app.api.documents.document_service.get_document_detail",
        detail_mock,
    )

    response = client.get(f"/api/documents/{UNKNOWN_DOCUMENT_ID}")

    assert response.status_code == 404
    assert response.json()["detail"] == "Document not found."
    detail_mock.assert_called_once_with(UNKNOWN_DOCUMENT_ID)


@pytest.mark.asyncio
async def test_upload_document_service_uploads_file_and_inserts_metadata(
    monkeypatch,
) -> None:
    upload_file_mock = Mock()
    insert_metadata_mock = Mock(return_value=_metadata_row())
    monkeypatch.setattr(document_service, "get_settings", _settings)
    monkeypatch.setattr(document_service, "uuid4", lambda: DOCUMENT_ID)
    monkeypatch.setattr(document_service, "upload_document_file", upload_file_mock)
    monkeypatch.setattr(document_service, "insert_document_metadata", insert_metadata_mock)

    response = await document_service.upload_document(UploadStub())

    assert response.document_id == DOCUMENT_ID
    assert response.file_name == "contract.pdf"
    assert response.status == "uploaded"
    upload_file_mock.assert_called_once_with(
        f"documents/single_user/{DOCUMENT_ID}/contract.pdf",
        b"%PDF-1.4 content",
        content_type="application/pdf",
    )
    insert_metadata_mock.assert_called_once_with(
        {
            "id": str(DOCUMENT_ID),
            "user_id": "single_user",
            "file_name": "contract.pdf",
            "file_type": "pdf",
            "storage_path": f"documents/single_user/{DOCUMENT_ID}/contract.pdf",
            "status": "uploaded",
            "chunk_count": 0,
            "error_message": None,
        }
    )


@pytest.mark.asyncio
async def test_upload_document_service_reports_storage_failure_without_insert(
    monkeypatch,
) -> None:
    upload_file_mock = Mock(side_effect=SupabaseConnectionError("storage failed"))
    insert_metadata_mock = Mock()
    monkeypatch.setattr(document_service, "get_settings", _settings)
    monkeypatch.setattr(document_service, "uuid4", lambda: DOCUMENT_ID)
    monkeypatch.setattr(document_service, "upload_document_file", upload_file_mock)
    monkeypatch.setattr(document_service, "insert_document_metadata", insert_metadata_mock)

    with pytest.raises(document_service.DocumentStorageError) as exc_info:
        await document_service.upload_document(UploadStub())

    assert str(exc_info.value) == "Document storage upload failed."
    insert_metadata_mock.assert_not_called()


@pytest.mark.asyncio
async def test_upload_document_service_reports_metadata_insert_failure(
    monkeypatch,
) -> None:
    upload_file_mock = Mock()
    insert_metadata_mock = Mock(side_effect=SupabaseConnectionError("insert failed"))
    monkeypatch.setattr(document_service, "get_settings", _settings)
    monkeypatch.setattr(document_service, "uuid4", lambda: DOCUMENT_ID)
    monkeypatch.setattr(document_service, "upload_document_file", upload_file_mock)
    monkeypatch.setattr(document_service, "insert_document_metadata", insert_metadata_mock)

    with pytest.raises(document_service.DocumentMetadataError) as exc_info:
        await document_service.upload_document(UploadStub())

    assert str(exc_info.value) == (
        "Document metadata insert failed after storage upload completed."
    )
    upload_file_mock.assert_called_once()
    insert_metadata_mock.assert_called_once()


def test_list_documents_service_filters_by_single_user_id(monkeypatch) -> None:
    list_metadata_mock = Mock(return_value=[_metadata_row()])
    monkeypatch.setattr(document_service, "get_settings", _settings)
    monkeypatch.setattr(document_service, "list_document_metadata", list_metadata_mock)

    response = document_service.list_documents()

    assert len(response.documents) == 1
    assert response.documents[0].id == DOCUMENT_ID
    assert response.documents[0].file_name == "contract.pdf"
    list_metadata_mock.assert_called_once_with("single_user")


def test_get_document_detail_service_filters_by_single_user_id(
    monkeypatch,
) -> None:
    get_metadata_mock = Mock(return_value=_metadata_row())
    monkeypatch.setattr(document_service, "get_settings", _settings)
    monkeypatch.setattr(document_service, "get_document_metadata", get_metadata_mock)

    response = document_service.get_document_detail(DOCUMENT_ID)

    assert response.id == DOCUMENT_ID
    assert response.chunks == []
    get_metadata_mock.assert_called_once_with(str(DOCUMENT_ID), "single_user")


def test_get_document_detail_service_returns_not_found_when_missing(
    monkeypatch,
) -> None:
    get_metadata_mock = Mock(return_value=None)
    monkeypatch.setattr(document_service, "get_settings", _settings)
    monkeypatch.setattr(document_service, "get_document_metadata", get_metadata_mock)

    with pytest.raises(document_service.DocumentNotFoundError) as exc_info:
        document_service.get_document_detail(DOCUMENT_ID)

    assert str(exc_info.value) == "Document not found."
    get_metadata_mock.assert_called_once_with(str(DOCUMENT_ID), "single_user")
