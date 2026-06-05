import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

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
