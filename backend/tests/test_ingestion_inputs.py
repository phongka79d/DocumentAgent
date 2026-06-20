from __future__ import annotations

from io import BytesIO

from app.graphs import ingestion_inputs


def test_resolve_document_fields_prefer_state_then_document_record():
    state = {
        "document_id": " doc-1 ",
        "file_name": " state.pdf ",
        "document_record": {
            "file_name": "record.pdf",
            "mime_type": " application/pdf ",
            "storage_path": " documents/doc-1/original.pdf ",
        },
    }

    assert ingestion_inputs.resolve_document_id(state) == "doc-1"
    assert ingestion_inputs.resolve_file_name(state) == "state.pdf"
    assert ingestion_inputs.resolve_mime_type(state) == "application/pdf"
    assert ingestion_inputs.resolve_storage_path(state) == "documents/doc-1/original.pdf"


def test_resolve_rows_normalizes_response_shapes():
    class Response:
        data = {"id": "row-1"}

    assert ingestion_inputs.resolve_rows(Response()) == [{"id": "row-1"}]
    assert ingestion_inputs.resolve_rows([{"id": "row-2"}]) == [{"id": "row-2"}]
    assert ingestion_inputs.resolve_rows(None) == []


def test_normalize_bytes_accepts_common_download_shapes():
    assert ingestion_inputs.normalize_bytes(b"abc") == b"abc"
    assert ingestion_inputs.normalize_bytes(bytearray(b"abc")) == b"abc"
    assert ingestion_inputs.normalize_bytes(memoryview(b"abc")) == b"abc"
    assert ingestion_inputs.normalize_bytes(BytesIO(b"abc")) == b"abc"
    assert ingestion_inputs.normalize_bytes("abc") == b"abc"
