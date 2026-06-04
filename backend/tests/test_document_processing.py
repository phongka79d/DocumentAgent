from pathlib import Path
import sys
from uuid import UUID

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.schemas.parsing import ChunkDraft, ParsedSection
from app.services import document_processing_service
from app.services.document_parser import (
    DocumentDecodingError,
    DocumentParserError,
    EmptyDocumentError,
    UnsupportedDocumentTypeError,
)
from app.services.supabase_service import SupabaseConnectionError


class _ProcessingSettings:
    single_user_id = "single_user"
    chunk_size_tokens = 1000
    chunk_overlap_tokens = 150


DOCUMENT_ID = UUID("00000000-0000-0000-0000-000000000123")
DOCUMENT_ID_TEXT = str(DOCUMENT_ID)
STORAGE_PATH = f"documents/single_user/{DOCUMENT_ID_TEXT}/sample.txt"


def _document_row(*, file_type: str = "txt") -> dict:
    return {
        "id": DOCUMENT_ID_TEXT,
        "file_name": f"sample.{file_type}",
        "file_type": file_type,
        "storage_path": STORAGE_PATH,
    }


def test_process_document_orchestrates_success_path(monkeypatch):
    calls: list[tuple] = []

    def fake_get_settings():
        return _ProcessingSettings()

    def fake_get_processing_document(received_document_id: str):
        calls.append(("get_document", received_document_id))
        return _document_row()

    def fake_update_document_status(
        received_document_id: str,
        status: str,
        *,
        error_message: str | None = None,
    ):
        calls.append(("status", received_document_id, status, error_message))
        return {
            "id": received_document_id,
            "status": status,
            "error_message": error_message,
        }

    def fake_download_original_document_file(received_storage_path: str):
        calls.append(("download", received_storage_path))
        return b"Uploaded document text."

    def fake_parse_document(file_bytes: bytes, file_type: str, file_name: str):
        calls.append(("parse", file_bytes, file_type, file_name))
        return [
            ParsedSection(
                text="Uploaded document text.",
                file_name=file_name,
                metadata={"source_type": file_type},
            )
        ]

    def fake_chunk_sections(
        sections: list[ParsedSection],
        chunk_size: int,
        chunk_overlap: int,
    ):
        calls.append(
            (
                "chunk",
                sections[0].metadata,
                sections[0].file_name,
                chunk_size,
                chunk_overlap,
            )
        )
        return [
            ChunkDraft(
                content="Uploaded document text.",
                chunk_index=0,
                token_count=3,
                document_id=DOCUMENT_ID,
                user_id="single_user",
                file_name="sample.txt",
                metadata=sections[0].metadata,
            )
        ]

    def fake_insert_document_chunks(
        received_document_id: str,
        chunks: list[ChunkDraft],
    ):
        calls.append(("insert_chunks", received_document_id, chunks))
        return [{"id": "chunk-1", "chunk_index": chunks[0].chunk_index}]

    def fake_update_document_chunk_count(
        received_document_id: str,
        chunk_count: int,
    ):
        calls.append(("chunk_count", received_document_id, chunk_count))
        return {"id": received_document_id, "chunk_count": chunk_count}

    monkeypatch.setattr(
        document_processing_service,
        "get_settings",
        fake_get_settings,
    )
    monkeypatch.setattr(
        document_processing_service,
        "get_processing_document",
        fake_get_processing_document,
    )
    monkeypatch.setattr(
        document_processing_service,
        "update_document_status",
        fake_update_document_status,
    )
    monkeypatch.setattr(
        document_processing_service,
        "download_original_document_file",
        fake_download_original_document_file,
    )
    monkeypatch.setattr(
        document_processing_service,
        "parse_document",
        fake_parse_document,
    )
    monkeypatch.setattr(
        document_processing_service,
        "chunk_sections",
        fake_chunk_sections,
    )
    monkeypatch.setattr(
        document_processing_service,
        "insert_document_chunks",
        fake_insert_document_chunks,
    )
    monkeypatch.setattr(
        document_processing_service,
        "update_document_chunk_count",
        fake_update_document_chunk_count,
    )

    result = document_processing_service.process_document(DOCUMENT_ID)

    assert result.document_id == DOCUMENT_ID
    assert result.status == "ready"
    assert result.chunk_count == 1
    assert calls == [
        ("get_document", DOCUMENT_ID_TEXT),
        ("status", DOCUMENT_ID_TEXT, "processing", None),
        ("download", STORAGE_PATH),
        ("parse", b"Uploaded document text.", "txt", "sample.txt"),
        (
            "chunk",
            {
                "source_type": "txt",
                "document_id": DOCUMENT_ID_TEXT,
                "user_id": "single_user",
                "file_name": "sample.txt",
            },
            "sample.txt",
            1000,
            150,
        ),
        ("insert_chunks", DOCUMENT_ID_TEXT, calls[5][2]),
        ("chunk_count", DOCUMENT_ID_TEXT, 1),
        ("status", DOCUMENT_ID_TEXT, "ready", None),
    ]

    inserted_chunks = calls[5][2]
    assert inserted_chunks[0].document_id == DOCUMENT_ID
    assert inserted_chunks[0].user_id == "single_user"
    assert inserted_chunks[0].qdrant_point_id is None


def test_process_document_persists_real_txt_chunks_with_single_user_owner(
    monkeypatch,
):
    calls: list[tuple] = []
    inserted_chunks: list[ChunkDraft] = []

    def fake_get_settings():
        return _ProcessingSettings()

    def fake_get_processing_document(received_document_id: str):
        calls.append(("get_document", received_document_id))
        return _document_row(file_type="txt")

    def fake_update_document_status(
        received_document_id: str,
        status: str,
        *,
        error_message: str | None = None,
    ):
        calls.append(("status", received_document_id, status, error_message))
        return {
            "id": received_document_id,
            "status": status,
            "error_message": error_message,
        }

    def fake_download_original_document_file(received_storage_path: str):
        calls.append(("download", received_storage_path))
        return (
            b"Alpha beta gamma delta. Epsilon zeta eta theta. "
            b"Iota kappa lambda mu."
        )

    def fake_insert_document_chunks(
        received_document_id: str,
        chunks: list[ChunkDraft],
    ):
        calls.append(("insert_chunks", received_document_id, chunks))
        inserted_chunks.extend(chunks)
        return [
            {"id": f"chunk-{chunk.chunk_index}", "chunk_index": chunk.chunk_index}
            for chunk in chunks
        ]

    def fake_update_document_chunk_count(
        received_document_id: str,
        chunk_count: int,
    ):
        calls.append(("chunk_count", received_document_id, chunk_count))
        return {"id": received_document_id, "chunk_count": chunk_count}

    monkeypatch.setattr(
        document_processing_service,
        "get_settings",
        fake_get_settings,
    )
    monkeypatch.setattr(
        document_processing_service,
        "get_processing_document",
        fake_get_processing_document,
    )
    monkeypatch.setattr(
        document_processing_service,
        "update_document_status",
        fake_update_document_status,
    )
    monkeypatch.setattr(
        document_processing_service,
        "download_original_document_file",
        fake_download_original_document_file,
    )
    monkeypatch.setattr(
        document_processing_service,
        "insert_document_chunks",
        fake_insert_document_chunks,
    )
    monkeypatch.setattr(
        document_processing_service,
        "update_document_chunk_count",
        fake_update_document_chunk_count,
    )

    result = document_processing_service.process_document(DOCUMENT_ID)

    assert result.status == "ready"
    assert result.chunk_count == len(inserted_chunks)
    assert len(inserted_chunks) >= 1
    assert [chunk.chunk_index for chunk in inserted_chunks] == list(
        range(len(inserted_chunks))
    )
    assert all(chunk.document_id == DOCUMENT_ID for chunk in inserted_chunks)
    assert all(
        chunk.user_id == _ProcessingSettings.single_user_id
        for chunk in inserted_chunks
    )
    assert all(chunk.qdrant_point_id is None for chunk in inserted_chunks)
    assert all(chunk.content.strip() for chunk in inserted_chunks)
    assert all(chunk.token_count > 0 for chunk in inserted_chunks)
    assert all(
        chunk.metadata["document_id"] == DOCUMENT_ID_TEXT
        for chunk in inserted_chunks
    )
    assert all(
        chunk.metadata["user_id"] == _ProcessingSettings.single_user_id
        for chunk in inserted_chunks
    )
    assert all(chunk.metadata["file_name"] == "sample.txt" for chunk in inserted_chunks)
    assert all(chunk.metadata["source_type"] == "txt" for chunk in inserted_chunks)

    status_events = [call for call in calls if call[0] == "status"]
    assert status_events == [
        ("status", DOCUMENT_ID_TEXT, "processing", None),
        ("status", DOCUMENT_ID_TEXT, "ready", None),
    ]
    assert calls.index(("insert_chunks", DOCUMENT_ID_TEXT, inserted_chunks)) < calls.index(
        ("chunk_count", DOCUMENT_ID_TEXT, len(inserted_chunks))
    )


def test_process_document_empty_txt_file_marks_document_failed(monkeypatch):
    calls: list[tuple] = []

    def fake_get_settings():
        return _ProcessingSettings()

    def fake_get_processing_document(received_document_id: str):
        calls.append(("get_document", received_document_id))
        return _document_row(file_type="txt")

    def fake_update_document_status(
        received_document_id: str,
        status: str,
        *,
        error_message: str | None = None,
    ):
        calls.append(("status", received_document_id, status, error_message))
        return {
            "id": received_document_id,
            "status": status,
            "error_message": error_message,
        }

    def fake_download_original_document_file(received_storage_path: str):
        calls.append(("download", received_storage_path))
        return b" \n\t "

    def fail_insert_document_chunks(*_args, **_kwargs):
        pytest.fail("empty TXT processing should not insert chunks")

    def fail_update_document_chunk_count(*_args, **_kwargs):
        pytest.fail("empty TXT processing should not update chunk_count")

    monkeypatch.setattr(
        document_processing_service,
        "get_settings",
        fake_get_settings,
    )
    monkeypatch.setattr(
        document_processing_service,
        "get_processing_document",
        fake_get_processing_document,
    )
    monkeypatch.setattr(
        document_processing_service,
        "update_document_status",
        fake_update_document_status,
    )
    monkeypatch.setattr(
        document_processing_service,
        "download_original_document_file",
        fake_download_original_document_file,
    )
    monkeypatch.setattr(
        document_processing_service,
        "insert_document_chunks",
        fail_insert_document_chunks,
    )
    monkeypatch.setattr(
        document_processing_service,
        "update_document_chunk_count",
        fail_update_document_chunk_count,
    )

    with pytest.raises(document_processing_service.DocumentProcessingError) as exc_info:
        document_processing_service.process_document(DOCUMENT_ID)

    assert str(exc_info.value) == "Parsed document is empty."
    assert calls == [
        ("get_document", DOCUMENT_ID_TEXT),
        ("status", DOCUMENT_ID_TEXT, "processing", None),
        ("download", STORAGE_PATH),
        ("status", DOCUMENT_ID_TEXT, "failed", "Parsed document is empty."),
    ]


def _install_default_processing_mocks(monkeypatch, calls: list[tuple]) -> None:
    def fake_get_settings():
        return _ProcessingSettings()

    def fake_get_processing_document(received_document_id: str):
        calls.append(("get_document", received_document_id))
        return _document_row()

    def fake_update_document_status(
        received_document_id: str,
        status: str,
        *,
        error_message: str | None = None,
    ):
        calls.append(("status", received_document_id, status, error_message))
        return {
            "id": received_document_id,
            "status": status,
            "error_message": error_message,
        }

    def fake_download_original_document_file(received_storage_path: str):
        calls.append(("download", received_storage_path))
        return b"Uploaded document text."

    def fake_parse_document(file_bytes: bytes, file_type: str, file_name: str):
        calls.append(("parse", file_bytes, file_type, file_name))
        return [
            ParsedSection(
                text="Uploaded document text.",
                file_name=file_name,
                metadata={"source_type": file_type},
            )
        ]

    def fake_chunk_sections(
        sections: list[ParsedSection],
        chunk_size: int,
        chunk_overlap: int,
    ):
        calls.append(("chunk", chunk_size, chunk_overlap))
        return [
            ChunkDraft(
                content="Uploaded document text.",
                chunk_index=0,
                token_count=3,
                document_id=DOCUMENT_ID,
                user_id="single_user",
                file_name="sample.txt",
                metadata=sections[0].metadata,
            )
        ]

    def fake_insert_document_chunks(
        received_document_id: str,
        chunks: list[ChunkDraft],
    ):
        calls.append(("insert_chunks", received_document_id, chunks))
        return [{"id": "chunk-1", "chunk_index": chunks[0].chunk_index}]

    def fake_update_document_chunk_count(
        received_document_id: str,
        chunk_count: int,
    ):
        calls.append(("chunk_count", received_document_id, chunk_count))
        return {"id": received_document_id, "chunk_count": chunk_count}

    monkeypatch.setattr(document_processing_service, "get_settings", fake_get_settings)
    monkeypatch.setattr(
        document_processing_service,
        "get_processing_document",
        fake_get_processing_document,
    )
    monkeypatch.setattr(
        document_processing_service,
        "update_document_status",
        fake_update_document_status,
    )
    monkeypatch.setattr(
        document_processing_service,
        "download_original_document_file",
        fake_download_original_document_file,
    )
    monkeypatch.setattr(
        document_processing_service,
        "parse_document",
        fake_parse_document,
    )
    monkeypatch.setattr(
        document_processing_service,
        "chunk_sections",
        fake_chunk_sections,
    )
    monkeypatch.setattr(
        document_processing_service,
        "insert_document_chunks",
        fake_insert_document_chunks,
    )
    monkeypatch.setattr(
        document_processing_service,
        "update_document_chunk_count",
        fake_update_document_chunk_count,
    )


@pytest.mark.parametrize(
    ("patch_name", "failure", "expected_message"),
    [
        (
            "download_original_document_file",
            SupabaseConnectionError("Supabase operation 'storage download' failed: FileNotFoundError."),
            "Document storage or persistence operation failed.",
        ),
        (
            "parse_document",
            DocumentParserError("Raw parser details should not leak."),
            "Document parser failed.",
        ),
        (
            "parse_document",
            EmptyDocumentError("Parsed document is empty."),
            "Parsed document is empty.",
        ),
        (
            "parse_document",
            UnsupportedDocumentTypeError("Unsupported document type: exe."),
            "Unsupported document type.",
        ),
        (
            "parse_document",
            DocumentDecodingError("Could not decode CSV document."),
            "Could not decode CSV document.",
        ),
        (
            "chunk_sections",
            [],
            "Parsed document produced no chunks.",
        ),
        (
            "insert_document_chunks",
            SupabaseConnectionError("Supabase operation 'document chunk insert' failed: APIError."),
            "Document storage or persistence operation failed.",
        ),
        (
            "insert_document_chunks",
            [],
            "Chunk persistence returned no chunks.",
        ),
    ],
)
def test_process_document_marks_failures_failed(
    monkeypatch,
    patch_name,
    failure,
    expected_message,
):
    calls: list[tuple] = []
    _install_default_processing_mocks(monkeypatch, calls)

    if isinstance(failure, Exception):
        def failing_replacement(*_args, **_kwargs):
            calls.append((patch_name, "failed"))
            raise failure
    else:
        def failing_replacement(*_args, **_kwargs):
            calls.append((patch_name, "empty"))
            return failure

    monkeypatch.setattr(document_processing_service, patch_name, failing_replacement)

    with pytest.raises(document_processing_service.DocumentProcessingError) as exc_info:
        document_processing_service.process_document(DOCUMENT_ID)

    assert str(exc_info.value) == expected_message
    assert ("status", DOCUMENT_ID_TEXT, "processing", None) in calls
    assert ("status", DOCUMENT_ID_TEXT, "failed", expected_message) in calls
    assert ("status", DOCUMENT_ID_TEXT, "ready", None) not in calls
    assert not any(call[0] == "chunk_count" and call[2] == 0 for call in calls)
