import sys
from pathlib import Path
from unittest.mock import AsyncMock
from uuid import UUID

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import app
from app.schemas.documents import DocumentUploadResponse
from app.utils.file_validation import UploadTooLargeError, UploadValidationError


client = TestClient(app)


DOCUMENT_ID = UUID("11111111-1111-4111-8111-111111111111")


def test_upload_supported_file_returns_document_metadata(monkeypatch) -> None:
    upload_mock = AsyncMock(
        return_value=DocumentUploadResponse(
            document_id=DOCUMENT_ID,
            file_name="contract.pdf",
            status="uploaded",
        )
    )
    monkeypatch.setattr(
        "app.api.documents.document_service.upload_document",
        upload_mock,
    )

    response = client.post(
        "/api/documents/upload",
        files={"file": ("contract.pdf", b"%PDF-1.4 content", "application/pdf")},
    )

    assert response.status_code == 200
    assert response.json() == {
        "document_id": str(DOCUMENT_ID),
        "file_name": "contract.pdf",
        "status": "uploaded",
    }
    upload_mock.assert_awaited_once()
    assert upload_mock.await_args.args[0].filename == "contract.pdf"


def test_upload_unsupported_file_type_returns_400(monkeypatch) -> None:
    upload_mock = AsyncMock(
        side_effect=UploadValidationError(
            "Unsupported file type. Supported document extensions are: .csv, .docx, .pdf, .txt."
        )
    )
    monkeypatch.setattr(
        "app.api.documents.document_service.upload_document",
        upload_mock,
    )

    response = client.post(
        "/api/documents/upload",
        files={"file": ("installer.exe", b"not a document", "application/octet-stream")},
    )

    assert response.status_code == 400
    assert "Unsupported file type" in response.json()["detail"]
    upload_mock.assert_awaited_once()


def test_upload_empty_file_returns_400(monkeypatch) -> None:
    upload_mock = AsyncMock(
        side_effect=UploadValidationError("Uploaded file cannot be empty.")
    )
    monkeypatch.setattr(
        "app.api.documents.document_service.upload_document",
        upload_mock,
    )

    response = client.post(
        "/api/documents/upload",
        files={"file": ("empty.txt", b"", "text/plain")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Uploaded file cannot be empty."
    upload_mock.assert_awaited_once()


def test_upload_too_large_file_returns_413(monkeypatch) -> None:
    upload_mock = AsyncMock(
        side_effect=UploadTooLargeError(
            "Uploaded file exceeds the maximum size of 100 bytes."
        )
    )
    monkeypatch.setattr(
        "app.api.documents.document_service.upload_document",
        upload_mock,
    )

    response = client.post(
        "/api/documents/upload",
        files={"file": ("large.pdf", b"x" * 101, "application/pdf")},
    )

    assert response.status_code == 413
    assert response.json()["detail"] == (
        "Uploaded file exceeds the maximum size of 100 bytes."
    )
    upload_mock.assert_awaited_once()
