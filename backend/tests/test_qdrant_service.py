import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import UUID

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services import qdrant_service


def _settings(
    *,
    url: str = "https://qdrant.test",
    api_key: str = "private-qdrant-key",
    collection: str = "document_chunks",
) -> SimpleNamespace:
    return SimpleNamespace(
        require_qdrant_settings=lambda: {
            "url": url,
            "api_key": api_key,
            "collection": collection,
        }
    )


def test_get_qdrant_client_constructs_client_from_backend_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client_class = Mock(return_value="client")

    monkeypatch.setattr(qdrant_service, "get_settings", lambda: _settings())
    monkeypatch.setattr(qdrant_service, "QdrantClient", client_class)

    client = qdrant_service.get_qdrant_client()

    assert client == "client"
    client_class.assert_called_once_with(
        url="https://qdrant.test",
        api_key="private-qdrant-key",
    )


def test_get_qdrant_client_maps_missing_config_to_setup_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        qdrant_service,
        "get_settings",
        lambda: SimpleNamespace(
            require_qdrant_settings=Mock(
                side_effect=RuntimeError(
                    "Missing QDRANT_URL. Configure Qdrant settings in the backend environment before using vector indexing services."
                )
            )
        ),
    )

    with pytest.raises(qdrant_service.QdrantSetupError) as exc_info:
        qdrant_service.get_qdrant_client()

    message = str(exc_info.value)
    assert "Missing QDRANT_URL" in message
    assert "backend environment" in message


def test_ensure_collection_maps_missing_config_to_setup_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        qdrant_service,
        "get_settings",
        lambda: SimpleNamespace(
            require_qdrant_settings=Mock(
                side_effect=RuntimeError(
                    "Missing QDRANT_COLLECTION. Configure Qdrant settings in the backend environment before using vector indexing services."
                )
            )
        ),
    )

    with pytest.raises(qdrant_service.QdrantSetupError) as exc_info:
        qdrant_service.ensure_collection(vector_size=1536)

    assert "Missing QDRANT_COLLECTION" in str(exc_info.value)


def test_ensure_collection_creates_missing_collection_with_cosine_distance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = Mock()
    client.collection_exists.return_value = False

    monkeypatch.setattr(qdrant_service, "get_settings", lambda: _settings())
    monkeypatch.setattr(qdrant_service, "get_qdrant_client", Mock(return_value=client))

    qdrant_service.ensure_collection(vector_size=1536)

    client.collection_exists.assert_called_once_with("document_chunks")
    client.create_collection.assert_called_once()
    assert client.create_collection.call_args.kwargs["collection_name"] == "document_chunks"
    vectors_config = client.create_collection.call_args.kwargs["vectors_config"]
    assert vectors_config.size == 1536
    assert vectors_config.distance == qdrant_service.Distance.COSINE


def test_ensure_collection_maps_connection_failure_to_safe_setup_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = Mock()
    client.collection_exists.side_effect = RuntimeError("private connection detail")

    monkeypatch.setattr(qdrant_service, "get_settings", lambda: _settings())
    monkeypatch.setattr(qdrant_service, "get_qdrant_client", Mock(return_value=client))

    with pytest.raises(qdrant_service.QdrantSetupError) as exc_info:
        qdrant_service.ensure_collection(vector_size=1536)

    assert str(exc_info.value) == "Qdrant collection check failed."


def test_ensure_collection_maps_collection_creation_failure_to_safe_setup_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = Mock()
    client.collection_exists.return_value = False
    client.create_collection.side_effect = RuntimeError("private collection detail")

    monkeypatch.setattr(qdrant_service, "get_settings", lambda: _settings())
    monkeypatch.setattr(qdrant_service, "get_qdrant_client", Mock(return_value=client))

    with pytest.raises(qdrant_service.QdrantSetupError) as exc_info:
        qdrant_service.ensure_collection(vector_size=1536)

    assert str(exc_info.value) == "Qdrant collection creation failed."


def test_ensure_collection_maps_collection_lookup_failure_to_safe_setup_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = Mock()
    client.collection_exists.return_value = True
    client.get_collection.side_effect = RuntimeError("private lookup detail")

    monkeypatch.setattr(qdrant_service, "get_settings", lambda: _settings())
    monkeypatch.setattr(qdrant_service, "get_qdrant_client", Mock(return_value=client))

    with pytest.raises(qdrant_service.QdrantSetupError) as exc_info:
        qdrant_service.ensure_collection(vector_size=1536)

    assert str(exc_info.value) == "Qdrant collection configuration lookup failed."


def test_ensure_collection_accepts_existing_collection_with_matching_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = Mock()
    client.collection_exists.return_value = True
    client.get_collection.return_value = SimpleNamespace(
        config=SimpleNamespace(
            params=SimpleNamespace(
                vectors=SimpleNamespace(
                    size=1536,
                    distance=qdrant_service.Distance.COSINE,
                )
            )
        )
    )

    monkeypatch.setattr(qdrant_service, "get_settings", lambda: _settings())
    monkeypatch.setattr(qdrant_service, "get_qdrant_client", Mock(return_value=client))

    qdrant_service.ensure_collection(vector_size=1536)

    client.get_collection.assert_called_once_with("document_chunks")
    client.create_collection.assert_not_called()


@pytest.mark.parametrize(
    ("existing_size", "existing_distance", "expected_message"),
    [
        (768, qdrant_service.Distance.COSINE, "vector size"),
        (1536, qdrant_service.Distance.DOT, "distance"),
    ],
)
def test_ensure_collection_rejects_existing_collection_mismatch(
    monkeypatch: pytest.MonkeyPatch,
    existing_size: int,
    existing_distance: object,
    expected_message: str,
) -> None:
    client = Mock()
    client.collection_exists.return_value = True
    client.get_collection.return_value = SimpleNamespace(
        config=SimpleNamespace(
            params=SimpleNamespace(
                vectors=SimpleNamespace(
                    size=existing_size,
                    distance=existing_distance,
                )
            )
        )
    )

    monkeypatch.setattr(qdrant_service, "get_settings", lambda: _settings())
    monkeypatch.setattr(qdrant_service, "get_qdrant_client", Mock(return_value=client))

    with pytest.raises(qdrant_service.QdrantSetupError) as exc_info:
        qdrant_service.ensure_collection(vector_size=1536)

    message = str(exc_info.value)
    assert expected_message in message
    assert "document_chunks" in message
    assert "verify collection setup" in message


def test_build_chunk_payload_includes_required_metadata_and_safe_preview() -> None:
    document_id = UUID("11111111-1111-1111-1111-111111111111")
    chunk_id = UUID("22222222-2222-2222-2222-222222222222")
    content = "x" * 501

    payload = qdrant_service.build_chunk_payload(
        user_id="single_user",
        document_id=document_id,
        chunk_id=chunk_id,
        file_name="contract.pdf",
        file_type="pdf",
        page_number=3,
        section_title="Probation",
        chunk_index=0,
        content=content,
    )

    assert payload.user_id == "single_user"
    assert payload.document_id == document_id
    assert payload.chunk_id == chunk_id
    assert payload.file_name == "contract.pdf"
    assert payload.file_type == "pdf"
    assert payload.page_number == 3
    assert payload.section_title == "Probation"
    assert payload.chunk_index == 0
    assert payload.content_preview == "x" * 500


def test_upsert_chunk_vector_uses_stable_point_id_payload_and_vector_passthrough(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = Mock()
    chunk_id = "22222222-2222-2222-2222-222222222222"
    vector = [0.1, 0.2, 0.3]
    payload = qdrant_service.build_chunk_payload(
        user_id="single_user",
        document_id="11111111-1111-1111-1111-111111111111",
        chunk_id=chunk_id,
        file_name="contract.pdf",
        file_type="pdf",
        page_number=None,
        section_title=None,
        chunk_index=4,
        content="Chunk content",
    )

    monkeypatch.setattr(qdrant_service, "get_settings", lambda: _settings())
    monkeypatch.setattr(qdrant_service, "get_qdrant_client", Mock(return_value=client))

    point_id = qdrant_service.upsert_chunk_vector(
        point_id=chunk_id,
        vector=vector,
        payload=payload,
    )

    assert point_id == chunk_id
    client.upsert.assert_called_once()
    assert client.upsert.call_args.kwargs["collection_name"] == "document_chunks"
    points = client.upsert.call_args.kwargs["points"]
    assert len(points) == 1
    point = points[0]
    assert point.id == chunk_id
    assert point.vector == vector
    assert point.payload == {
        "user_id": "single_user",
        "document_id": "11111111-1111-1111-1111-111111111111",
        "chunk_id": chunk_id,
        "file_name": "contract.pdf",
        "file_type": "pdf",
        "page_number": None,
        "section_title": None,
        "chunk_index": 4,
        "content_preview": "Chunk content",
    }
    assert "qdrant_point_id" not in point.payload


def test_upsert_chunk_vector_does_not_update_supabase_qdrant_point_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = Mock()
    payload = qdrant_service.build_chunk_payload(
        user_id="single_user",
        document_id="11111111-1111-1111-1111-111111111111",
        chunk_id="22222222-2222-2222-2222-222222222222",
        file_name="contract.pdf",
        file_type="pdf",
        page_number=1,
        section_title="Intro",
        chunk_index=0,
        content="Chunk content",
    )

    monkeypatch.setattr(qdrant_service, "get_settings", lambda: _settings())
    monkeypatch.setattr(qdrant_service, "get_qdrant_client", Mock(return_value=client))

    qdrant_service.upsert_chunk_vector(
        point_id="22222222-2222-2222-2222-222222222222",
        vector=[0.1],
        payload=payload,
    )

    client.upsert.assert_called_once()
    assert not hasattr(qdrant_service, "update_chunk_qdrant_point_id")


def test_upsert_chunk_vector_maps_qdrant_failure_to_safe_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = Mock()
    client.upsert.side_effect = RuntimeError("private provider detail")
    payload = qdrant_service.build_chunk_payload(
        user_id="single_user",
        document_id="11111111-1111-1111-1111-111111111111",
        chunk_id="22222222-2222-2222-2222-222222222222",
        file_name="contract.pdf",
        file_type="pdf",
        page_number=1,
        section_title="Intro",
        chunk_index=0,
        content="Chunk content",
    )

    monkeypatch.setattr(qdrant_service, "get_settings", lambda: _settings())
    monkeypatch.setattr(qdrant_service, "get_qdrant_client", Mock(return_value=client))

    with pytest.raises(qdrant_service.QdrantUpsertError) as exc_info:
        qdrant_service.upsert_chunk_vector(
            point_id="22222222-2222-2222-2222-222222222222",
            vector=[0.1],
            payload=payload,
        )

    assert str(exc_info.value) == "Qdrant chunk vector upsert failed."


def test_upsert_chunk_vector_maps_vector_size_failure_to_setup_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = Mock()
    client.upsert.side_effect = RuntimeError(
        "Wrong vector dimension: expected dim: 1536, got 768"
    )
    payload = qdrant_service.build_chunk_payload(
        user_id="single_user",
        document_id="11111111-1111-1111-1111-111111111111",
        chunk_id="22222222-2222-2222-2222-222222222222",
        file_name="contract.pdf",
        file_type="pdf",
        page_number=1,
        section_title="Intro",
        chunk_index=0,
        content="Chunk content",
    )

    monkeypatch.setattr(qdrant_service, "get_settings", lambda: _settings())
    monkeypatch.setattr(qdrant_service, "get_qdrant_client", Mock(return_value=client))

    with pytest.raises(qdrant_service.QdrantSetupError) as exc_info:
        qdrant_service.upsert_chunk_vector(
            point_id="22222222-2222-2222-2222-222222222222",
            vector=[0.1],
            payload=payload,
        )

    message = str(exc_info.value)
    assert "vector-size mismatch" in message
    assert "verify collection setup" in message
    assert "1536" not in message
