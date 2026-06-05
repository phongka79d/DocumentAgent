from pathlib import Path
import sys
from uuid import UUID

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services import embedding_service


DOCUMENT_ID = UUID("11111111-1111-1111-1111-111111111111")
DOCUMENT_ID_TEXT = str(DOCUMENT_ID)
CHUNK_ONE_ID = UUID("22222222-2222-2222-2222-222222222222")
CHUNK_TWO_ID = UUID("33333333-3333-3333-3333-333333333333")


def _document_row(*, status: str = "ready") -> dict:
    return {
        "id": DOCUMENT_ID_TEXT,
        "user_id": "single_user",
        "status": status,
        "file_name": "contract.pdf",
        "file_type": "pdf",
    }


def _chunk_rows() -> list[dict]:
    return [
        {
            "id": str(CHUNK_ONE_ID),
            "document_id": DOCUMENT_ID_TEXT,
            "user_id": "single_user",
            "chunk_index": 0,
            "content": "First chunk content.",
            "page_number": 1,
            "section_title": "Overview",
            "token_count": 3,
            "qdrant_point_id": None,
        },
        {
            "id": str(CHUNK_TWO_ID),
            "document_id": DOCUMENT_ID_TEXT,
            "user_id": "single_user",
            "chunk_index": 1,
            "content": "Second chunk content.",
            "page_number": 2,
            "section_title": None,
            "token_count": 3,
            "qdrant_point_id": None,
        },
    ]


def test_index_document_chunks_indexes_unindexed_chunks_and_updates_point_ids(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple] = []
    chunks = _chunk_rows()

    def fake_get_indexing_document(received_document_id: str):
        calls.append(("get_document", received_document_id))
        return _document_row()

    def fake_list_chunks_needing_indexing(received_document_id: str):
        calls.append(("list_chunks", received_document_id))
        return chunks

    def fake_create_embedding(text: str):
        calls.append(("embedding", text))
        return [float(len(text)), 0.2, 0.3]

    def fake_ensure_collection(vector_size: int):
        calls.append(("ensure_collection", vector_size))

    def fake_upsert_chunk_vector(point_id: str, vector: list[float], payload):
        calls.append(
            (
                "upsert",
                point_id,
                vector,
                payload.user_id,
                str(payload.document_id),
                str(payload.chunk_id),
                payload.file_name,
                payload.file_type,
                payload.chunk_index,
                payload.content_preview,
            )
        )
        return point_id

    def fake_update_chunk_qdrant_point_id(
        received_document_id: str,
        chunk_id: str,
        qdrant_point_id: str,
    ):
        calls.append(("update_point", received_document_id, chunk_id, qdrant_point_id))
        return {"id": chunk_id, "qdrant_point_id": qdrant_point_id}

    monkeypatch.setattr(
        embedding_service,
        "get_indexing_document",
        fake_get_indexing_document,
    )
    monkeypatch.setattr(
        embedding_service,
        "list_chunks_needing_indexing",
        fake_list_chunks_needing_indexing,
    )
    monkeypatch.setattr(embedding_service, "create_embedding", fake_create_embedding)
    monkeypatch.setattr(embedding_service, "ensure_collection", fake_ensure_collection)
    monkeypatch.setattr(
        embedding_service,
        "upsert_chunk_vector",
        fake_upsert_chunk_vector,
    )
    monkeypatch.setattr(
        embedding_service,
        "update_chunk_qdrant_point_id",
        fake_update_chunk_qdrant_point_id,
    )

    result = embedding_service.index_document_chunks(DOCUMENT_ID)

    assert result.document_id == DOCUMENT_ID
    assert result.indexed_count == 2
    assert result.failed_count == 0
    assert result.errors == []
    assert calls == [
        ("get_document", DOCUMENT_ID_TEXT),
        ("list_chunks", DOCUMENT_ID_TEXT),
        ("embedding", "First chunk content."),
        ("ensure_collection", 3),
        (
            "upsert",
            str(CHUNK_ONE_ID),
            [20.0, 0.2, 0.3],
            "single_user",
            DOCUMENT_ID_TEXT,
            str(CHUNK_ONE_ID),
            "contract.pdf",
            "pdf",
            0,
            "First chunk content.",
        ),
        ("update_point", DOCUMENT_ID_TEXT, str(CHUNK_ONE_ID), str(CHUNK_ONE_ID)),
        ("embedding", "Second chunk content."),
        (
            "upsert",
            str(CHUNK_TWO_ID),
            [21.0, 0.2, 0.3],
            "single_user",
            DOCUMENT_ID_TEXT,
            str(CHUNK_TWO_ID),
            "contract.pdf",
            "pdf",
            1,
            "Second chunk content.",
        ),
        ("update_point", DOCUMENT_ID_TEXT, str(CHUNK_TWO_ID), str(CHUNK_TWO_ID)),
    ]


def test_index_document_chunks_rejects_non_ready_document(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        embedding_service,
        "get_indexing_document",
        lambda received_document_id: _document_row(status="uploaded"),
    )

    def fail_list_chunks_needing_indexing(*_args, **_kwargs):
        pytest.fail("non-ready documents should not list chunks")

    monkeypatch.setattr(
        embedding_service,
        "list_chunks_needing_indexing",
        fail_list_chunks_needing_indexing,
    )

    with pytest.raises(embedding_service.DocumentIndexingError) as exc_info:
        embedding_service.index_document_chunks(DOCUMENT_ID)

    assert str(exc_info.value) == "Document must be ready before indexing."
