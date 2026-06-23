from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class _SimpleNamespace:
    """Simple object attribute access, like types.SimpleNamespace without the import."""
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.contracts import QdrantPayloadKey
from app.main import create_app
from app.services import qdrant_client
from app.services.qdrant_client import ensure_qdrant_payload_indexes, FILTERABLE_PAYLOAD_INDEXES
from app.services.retrieval import search_semantic_chunks


@dataclass
class FakeSchemaField:
    name: str
    data_type: int  # PayloadSchemaType value


@dataclass
class FakeCollectionInfo:
    payload_schema: dict[str, FakeSchemaField]

    def model_dump(self):
        return {"payload_schema": {k: v.__dict__ for k, v in self.payload_schema.items()}}


@dataclass
class FakeQdrantClient:
    collection_info: dict[str, FakeCollectionInfo] = field(default_factory=dict)
    get_collection_calls: list[str] = field(default_factory=list)
    create_index_calls: list[dict[str, Any]] = field(default_factory=list)
    query_calls: list[dict[str, Any]] = field(default_factory=list)

    def get_collection(self, collection_name: str) -> FakeCollectionInfo | None:
        self.get_collection_calls.append(collection_name)
        return self.collection_info.get(collection_name)

    def create_payload_index(
        self,
        collection_name: str,
        field_name: str,
        field_type: Any,
        wait: bool = True,
    ) -> None:
        self.create_index_calls.append(
            {
                "collection_name": collection_name,
                "field_name": field_name,
                "field_type": field_type,
                "wait": wait,
            }
        )

    def query_points(self, **kwargs):
        self.query_calls.append(kwargs)
        return _SimpleNamespace(points=[])


def test_ensure_qdrant_payload_indexes_creates_missing_integer_indexes():
    client = FakeQdrantClient(
        collection_info={
            "document_chunks_v1": FakeCollectionInfo(
                payload_schema={
                    "document_id": FakeSchemaField(
                        name="document_id", data_type=4  # KEYWORD
                    ),
                }
            )
        }
    )

    created = ensure_qdrant_payload_indexes(
        client,
        collection_name="document_chunks_v1",
        field_names={"page_start", "page_end"},
    )

    # page_start and page_end should be created as INTEGER
    created_names = {call["field_name"] for call in client.create_index_calls}
    assert "page_start" in created_names, "page_start index should be created"
    assert "page_end" in created_names, "page_end index should be created"
    for call in client.create_index_calls:
        assert call["wait"] is True, "Index creation must be synchronous (wait=True)"
    # existing document_id index should NOT be re-created
    assert any(
        call["field_name"] == "document_id" for call in client.create_index_calls
    ) is False, "Existing index should not be re-created"
    # Return value should list actually created fields
    assert set(created) == {"page_start", "page_end"}


def test_ensure_qdrant_payload_indexes_skips_existing_indexes():
    client = FakeQdrantClient(
        collection_info={
            "document_chunks_v1": FakeCollectionInfo(
                payload_schema={
                    "page_start": FakeSchemaField(name="page_start", data_type=3),
                    "page_end": FakeSchemaField(name="page_end", data_type=3),
                    "document_id": FakeSchemaField(name="document_id", data_type=4),
                }
            )
        }
    )

    created = ensure_qdrant_payload_indexes(
        client,
        collection_name="document_chunks_v1",
        field_names={"page_start", "page_end", "document_id"},
    )

    assert client.create_index_calls == [], (
        f"No indexes should be created when all exist: {client.create_index_calls}"
    )
    assert created == []


def test_ensure_qdrant_payload_indexes_handles_missing_collection_gracefully():
    client = FakeQdrantClient(collection_info={})

    created = ensure_qdrant_payload_indexes(
        client,
        collection_name="nonexistent_collection",
        field_names={"page_start"},
    )

    assert client.create_index_calls == []
    assert created == []


def test_search_semantic_chunks_ensures_page_filter_indexes_before_query():
    settings = Settings(
        _env_file=None,
        QDRANT_URL="https://qdrant.example.com",
        QDRANT_API_KEY="qdrant-key",
        QDRANT_COLLECTION="document_chunks_v1",
        SHOPAIKEY_API_KEY="shopai-key",
        SHOPAIKEY_BASE_URL="https://api.shopaikey.com/v1",
    )
    client = FakeQdrantClient(
        collection_info={
            "document_chunks_v1": FakeCollectionInfo(
                payload_schema={
                    "document_id": FakeSchemaField(
                        name="document_id", data_type=4
                    ),
                }
            )
        }
    )

    # This should succeed - index provisioning runs before the Qdrant query
    search_semantic_chunks(
        [0.1, 0.2, 0.3],
        document_ids=["doc-a"],
        filters={"page_start": 1, "page_end": 5},
        settings=settings,
        qdrant_client=client,
    )

    # Verify page_start and page_end indexes were ensured before query_points
    assert len(client.get_collection_calls) >= 1, (
        "get_collection must be called to inspect payload schema"
    )
    assert any(
        call["field_name"] in {"page_start", "page_end"}
        for call in client.create_index_calls
    ), "Filter fields must have indexes created before query"
    # Range conditions should remain in the query filter
    assert len(client.query_calls) >= 1, "Query must be executed"
    if client.query_calls:
        query_filter = client.query_calls[0].get("query_filter")
        if query_filter is not None:
            must_conditions = query_filter.must
            page_conditions = [
                c for c in must_conditions
                if c.key in {"page_start", "page_end"}
            ]
            assert len(page_conditions) >= 2, (
                "Page range conditions must be present in the query filter"
            )


def test_startup_payload_index_failure_does_not_block_health_endpoint(monkeypatch):
    """Startup index provisioning failure should not block the health endpoint."""
    settings = Settings(
        _env_file=None,
        ENSURE_QDRANT_PAYLOAD_INDEXES_ON_STARTUP=True,
        SHOPAIKEY_API_KEY="shopai-key",
        SHOPAIKEY_BASE_URL="https://api.shopaikey.com/v1",
        QDRANT_URL="https://qdrant.example.com",
        QDRANT_API_KEY="qdrant-key",
    )

    def _failing_provision(*args, **kwargs):
        raise ConnectionError("Qdrant unavailable at startup")

    monkeypatch.setattr(
        qdrant_client,
        "ensure_qdrant_payload_indexes",
        _failing_provision,
    )

    app = create_app(settings=settings)
    with TestClient(app) as test_client:
        response = test_client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_disabled_startup_provisioning_performs_no_qdrant_calls():
    """When ENSURE_QDRANT_PAYLOAD_INDEXES_ON_STARTUP is False, no Qdrant call should occur."""
    qdrant_calls: list[str] = []

    def _tracking_create_qdrant_client(*args, **kwargs):
        client = qdrant_client.create_qdrant_client(*args, **kwargs)
        original_get_collection = client.get_collection
        original_create_payload_index = client.create_payload_index

        def _tracking_get_collection(name):
            qdrant_calls.append(f"get_collection:{name}")
            return original_get_collection(name)

        def _tracking_create_index(**kwargs):
            qdrant_calls.append(f"create_payload_index:{kwargs.get('field_name')}")
            return original_create_payload_index(**kwargs)

        client.get_collection = _tracking_get_collection
        client.create_payload_index = _tracking_create_index
        return client

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(
        qdrant_client,
        "create_qdrant_client",
        _tracking_create_qdrant_client,
    )

    try:
        settings = Settings(
            _env_file=None,
            ENSURE_QDRANT_PAYLOAD_INDEXES_ON_STARTUP=False,
            SHOPAIKEY_API_KEY="shopai-key",
            SHOPAIKEY_BASE_URL="https://api.shopaikey.com/v1",
            QDRANT_URL="https://qdrant.example.com",
            QDRANT_API_KEY="qdrant-key",
        )
        app = create_app(settings=settings)
        with TestClient(app) as test_client:
            response = test_client.get("/api/health")

        assert response.status_code == 200
        # No Qdrant collection inspection or index creation calls should have occurred
        assert qdrant_calls == [], (
            f"Expected no Qdrant calls when provisioning disabled: {qdrant_calls}"
        )
    finally:
        monkeypatch.undo()
