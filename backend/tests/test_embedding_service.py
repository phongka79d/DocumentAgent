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


def test_index_document_chunks_skips_existing_qdrant_point_ids_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple] = []
    chunks = _chunk_rows()
    chunks[0]["qdrant_point_id"] = "existing-point-id"

    monkeypatch.setattr(
        embedding_service,
        "get_indexing_document",
        lambda received_document_id: _document_row(),
    )
    monkeypatch.setattr(
        embedding_service,
        "list_chunks_needing_indexing",
        lambda received_document_id: chunks,
    )
    monkeypatch.setattr(
        embedding_service,
        "create_embedding",
        lambda text: calls.append(("embedding", text)) or [1.0, 2.0, 3.0],
    )
    monkeypatch.setattr(
        embedding_service,
        "ensure_collection",
        lambda vector_size: calls.append(("ensure_collection", vector_size)),
    )
    monkeypatch.setattr(
        embedding_service,
        "upsert_chunk_vector",
        lambda point_id, vector, payload: calls.append(("upsert", point_id)) or point_id,
    )
    monkeypatch.setattr(
        embedding_service,
        "update_chunk_qdrant_point_id",
        lambda received_document_id, chunk_id, point_id: calls.append(
            ("update_point", chunk_id, point_id)
        )
        or {"id": chunk_id, "qdrant_point_id": point_id},
    )

    result = embedding_service.index_document_chunks(DOCUMENT_ID)

    assert result.indexed_count == 1
    assert result.failed_count == 0
    assert result.errors == []
    assert calls == [
        ("embedding", "Second chunk content."),
        ("ensure_collection", 3),
        ("upsert", str(CHUNK_TWO_ID)),
        ("update_point", str(CHUNK_TWO_ID), str(CHUNK_TWO_ID)),
    ]


def test_index_document_chunks_returns_no_work_result_for_document_with_no_chunks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        embedding_service,
        "get_indexing_document",
        lambda received_document_id: _document_row(),
    )
    monkeypatch.setattr(
        embedding_service,
        "list_chunks_needing_indexing",
        lambda received_document_id: [],
    )

    def fail_provider_call(*_args, **_kwargs):
        pytest.fail("no chunks should not call embedding or vector services")

    monkeypatch.setattr(embedding_service, "create_embedding", fail_provider_call)
    monkeypatch.setattr(embedding_service, "ensure_collection", fail_provider_call)
    monkeypatch.setattr(embedding_service, "upsert_chunk_vector", fail_provider_call)
    monkeypatch.setattr(
        embedding_service,
        "update_chunk_qdrant_point_id",
        fail_provider_call,
    )

    result = embedding_service.index_document_chunks(DOCUMENT_ID)

    assert result.document_id == DOCUMENT_ID
    assert result.indexed_count == 0
    assert result.failed_count == 0
    assert result.errors == []


def test_index_document_chunks_records_shopaikey_error_and_continues(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple] = []
    chunks = _chunk_rows()

    monkeypatch.setattr(
        embedding_service,
        "get_indexing_document",
        lambda received_document_id: _document_row(),
    )
    monkeypatch.setattr(
        embedding_service,
        "list_chunks_needing_indexing",
        lambda received_document_id: chunks,
    )

    def fake_create_embedding(text: str):
        calls.append(("embedding", text))
        if text == "First chunk content.":
            raise RuntimeError("ShopAIKey embedding request timed out.")
        return [1.0, 2.0, 3.0]

    monkeypatch.setattr(embedding_service, "create_embedding", fake_create_embedding)
    monkeypatch.setattr(
        embedding_service,
        "ensure_collection",
        lambda vector_size: calls.append(("ensure_collection", vector_size)),
    )
    monkeypatch.setattr(
        embedding_service,
        "upsert_chunk_vector",
        lambda point_id, vector, payload: calls.append(("upsert", point_id)) or point_id,
    )
    monkeypatch.setattr(
        embedding_service,
        "update_chunk_qdrant_point_id",
        lambda received_document_id, chunk_id, point_id: calls.append(
            ("update_point", chunk_id, point_id)
        )
        or {"id": chunk_id, "qdrant_point_id": point_id},
    )

    result = embedding_service.index_document_chunks(DOCUMENT_ID)

    assert result.indexed_count == 1
    assert result.failed_count == 1
    assert len(result.errors) == 1
    assert result.errors[0].chunk_id == CHUNK_ONE_ID
    assert result.errors[0].chunk_index == 0
    assert result.errors[0].message == "ShopAIKey embedding request timed out."
    assert calls == [
        ("embedding", "First chunk content."),
        ("embedding", "Second chunk content."),
        ("ensure_collection", 3),
        ("upsert", str(CHUNK_TWO_ID)),
        ("update_point", str(CHUNK_TWO_ID), str(CHUNK_TWO_ID)),
    ]


def test_index_document_chunks_records_qdrant_failure_without_updating_point_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple] = []
    chunks = _chunk_rows()[:1]

    monkeypatch.setattr(
        embedding_service,
        "get_indexing_document",
        lambda received_document_id: _document_row(),
    )
    monkeypatch.setattr(
        embedding_service,
        "list_chunks_needing_indexing",
        lambda received_document_id: chunks,
    )
    monkeypatch.setattr(
        embedding_service,
        "create_embedding",
        lambda text: calls.append(("embedding", text)) or [1.0, 2.0, 3.0],
    )
    monkeypatch.setattr(
        embedding_service,
        "ensure_collection",
        lambda vector_size: calls.append(("ensure_collection", vector_size)),
    )

    def fake_upsert_chunk_vector(point_id: str, vector: list[float], payload):
        calls.append(("upsert", point_id))
        raise RuntimeError("Qdrant chunk vector upsert failed.")

    monkeypatch.setattr(
        embedding_service,
        "upsert_chunk_vector",
        fake_upsert_chunk_vector,
    )
    monkeypatch.setattr(
        embedding_service,
        "update_chunk_qdrant_point_id",
        lambda *_args, **_kwargs: pytest.fail(
            "failed Qdrant upserts must not update qdrant_point_id"
        ),
    )

    result = embedding_service.index_document_chunks(DOCUMENT_ID)

    assert result.indexed_count == 0
    assert result.failed_count == 1
    assert len(result.errors) == 1
    assert result.errors[0].chunk_id == CHUNK_ONE_ID
    assert result.errors[0].message == "Qdrant chunk vector upsert failed."
    assert calls == [
        ("embedding", "First chunk content."),
        ("ensure_collection", 3),
        ("upsert", str(CHUNK_ONE_ID)),
    ]


def test_index_document_chunks_continues_after_recoverable_partial_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple] = []
    chunks = _chunk_rows()

    monkeypatch.setattr(
        embedding_service,
        "get_indexing_document",
        lambda received_document_id: _document_row(),
    )
    monkeypatch.setattr(
        embedding_service,
        "list_chunks_needing_indexing",
        lambda received_document_id: chunks,
    )
    monkeypatch.setattr(
        embedding_service,
        "create_embedding",
        lambda text: calls.append(("embedding", text)) or [1.0, 2.0, 3.0],
    )
    monkeypatch.setattr(
        embedding_service,
        "ensure_collection",
        lambda vector_size: calls.append(("ensure_collection", vector_size)),
    )

    def fake_upsert_chunk_vector(point_id: str, vector: list[float], payload):
        calls.append(("upsert", point_id))
        if point_id == str(CHUNK_ONE_ID):
            raise RuntimeError("Qdrant chunk vector upsert failed.")
        return point_id

    monkeypatch.setattr(
        embedding_service,
        "upsert_chunk_vector",
        fake_upsert_chunk_vector,
    )
    monkeypatch.setattr(
        embedding_service,
        "update_chunk_qdrant_point_id",
        lambda received_document_id, chunk_id, point_id: calls.append(
            ("update_point", chunk_id, point_id)
        )
        or {"id": chunk_id, "qdrant_point_id": point_id},
    )

    result = embedding_service.index_document_chunks(DOCUMENT_ID)

    assert result.indexed_count == 1
    assert result.failed_count == 1
    assert result.errors[0].chunk_id == CHUNK_ONE_ID
    assert calls == [
        ("embedding", "First chunk content."),
        ("ensure_collection", 3),
        ("upsert", str(CHUNK_ONE_ID)),
        ("embedding", "Second chunk content."),
        ("ensure_collection", 3),
        ("upsert", str(CHUNK_TWO_ID)),
        ("update_point", str(CHUNK_TWO_ID), str(CHUNK_TWO_ID)),
    ]
