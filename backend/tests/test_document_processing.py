from pathlib import Path
import sys
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.schemas.parsing import ChunkDraft, ParsedSection
from app.services import document_processing_service


class _ProcessingSettings:
    single_user_id = "single_user"
    chunk_size_tokens = 1000
    chunk_overlap_tokens = 150


def test_process_document_orchestrates_success_path(monkeypatch):
    document_id = UUID("00000000-0000-0000-0000-000000000123")
    document_id_text = str(document_id)
    storage_path = f"documents/single_user/{document_id_text}/sample.txt"
    calls: list[tuple] = []

    def fake_get_settings():
        return _ProcessingSettings()

    def fake_get_processing_document(received_document_id: str):
        calls.append(("get_document", received_document_id))
        return {
            "id": received_document_id,
            "file_name": "sample.txt",
            "file_type": "txt",
            "storage_path": storage_path,
        }

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
                document_id=document_id,
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

    result = document_processing_service.process_document(document_id)

    assert result.document_id == document_id
    assert result.status == "ready"
    assert result.chunk_count == 1
    assert calls == [
        ("get_document", document_id_text),
        ("status", document_id_text, "processing", None),
        ("download", storage_path),
        ("parse", b"Uploaded document text.", "txt", "sample.txt"),
        (
            "chunk",
            {
                "source_type": "txt",
                "document_id": document_id_text,
                "user_id": "single_user",
                "file_name": "sample.txt",
            },
            "sample.txt",
            1000,
            150,
        ),
        ("insert_chunks", document_id_text, calls[5][2]),
        ("chunk_count", document_id_text, 1),
        ("status", document_id_text, "ready", None),
    ]

    inserted_chunks = calls[5][2]
    assert inserted_chunks[0].document_id == document_id
    assert inserted_chunks[0].user_id == "single_user"
    assert inserted_chunks[0].qdrant_point_id is None
