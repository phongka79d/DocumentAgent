from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from fastapi.testclient import TestClient

from app.api.routes import chat as chat_route
from app.core.config import Settings
from app.main import create_app


FIXED_DOCUMENT_ID = UUID("11111111-1111-1111-1111-111111111111")
SECOND_DOCUMENT_ID = UUID("22222222-2222-2222-2222-222222222222")
FIXED_CHUNK_ID = UUID("33333333-3333-3333-3333-333333333333")


def _test_settings() -> Settings:
    return Settings(
        _env_file=None,
        SUPABASE_STORAGE_BUCKET="documents",
        QDRANT_COLLECTION="document_chunks_v1",
    )


@dataclass
class FakeQueryGraph:
    result: dict[str, object]
    invocations: list[dict[str, object]] = field(default_factory=list)

    def invoke(self, state: dict[str, object]) -> dict[str, object]:
        self.invocations.append(dict(state))
        return dict(self.result)


def _patch_route_settings(monkeypatch, settings: Settings) -> None:
    monkeypatch.setattr(chat_route, "get_settings", lambda: settings)


def _test_app(settings: Settings):
    return create_app(settings=settings)


def test_chat_route_invokes_query_graph_with_default_save_message_false(monkeypatch):
    settings = _test_settings()
    fake_graph = FakeQueryGraph(
        result={
            "answer": "Pricing is based on usage tiers.",
            "sources": [],
        }
    )
    build_calls: list[Settings | None] = []

    _patch_route_settings(monkeypatch, settings)
    monkeypatch.setattr(
        chat_route,
        "build_query_graph",
        lambda settings=None: build_calls.append(settings) or fake_graph,
    )

    app = _test_app(settings)

    with TestClient(app) as test_client:
        response = test_client.post(
            "/api/chat",
            json={"question": "What does this document say about pricing?"},
        )

    assert response.status_code == 200
    assert response.json() == {
        "answer": "Pricing is based on usage tiers.",
        "sources": [],
    }
    assert build_calls == [settings]
    assert fake_graph.invocations == [
        {
            "question": "What does this document say about pricing?",
            "document_ids": [],
            "save_message": False,
        }
    ]


def test_chat_route_preserves_optional_document_ids_and_save_message(monkeypatch):
    settings = _test_settings()
    fake_graph = FakeQueryGraph(
        result={
            "answer": "The document states pricing is usage-based.",
            "sources": [],
        }
    )

    _patch_route_settings(monkeypatch, settings)
    monkeypatch.setattr(
        chat_route,
        "build_query_graph",
        lambda settings=None: fake_graph,
    )

    app = _test_app(settings)

    with TestClient(app) as test_client:
        response = test_client.post(
            "/api/chat",
            json={
                "question": "What does this document say about pricing?",
                "document_ids": [str(FIXED_DOCUMENT_ID), str(SECOND_DOCUMENT_ID)],
                "save_message": True,
            },
        )

    assert response.status_code == 200
    assert fake_graph.invocations == [
        {
            "question": "What does this document say about pricing?",
            "document_ids": [str(FIXED_DOCUMENT_ID), str(SECOND_DOCUMENT_ID)],
            "save_message": True,
        }
    ]


def test_chat_route_returns_answer_and_sources_from_query_graph(monkeypatch):
    settings = _test_settings()
    fake_graph = FakeQueryGraph(
        result={
            "question": "What does this document say about pricing?",
            "document_ids": [str(FIXED_DOCUMENT_ID)],
            "save_message": False,
            "prepared_query": "What does this document say about pricing?",
            "query_embedding": [0.1, 0.2, 0.3],
            "retrieved_chunks": [{"chunk_id": str(FIXED_CHUNK_ID)}],
            "reranked_chunks": [{"chunk_id": str(FIXED_CHUNK_ID)}],
            "context_chunks": [{"chunk_id": str(FIXED_CHUNK_ID)}],
            "answer": "The document states pricing is based on usage tiers.",
            "sources": [
                {
                    "document_id": str(FIXED_DOCUMENT_ID),
                    "chunk_id": str(FIXED_CHUNK_ID),
                        "file_name": "pricing.pdf",
                        "chunk_index": 12,
                        "page_start": 3,
                    "page_end": 4,
                    "heading": None,
                    "qdrant_score": 0.78,
                    "rerank_score": 0.91,
                }
            ],
        }
    )

    _patch_route_settings(monkeypatch, settings)
    monkeypatch.setattr(
        chat_route,
        "build_query_graph",
        lambda settings=None: fake_graph,
    )

    app = _test_app(settings)

    with TestClient(app) as test_client:
        response = test_client.post(
            "/api/chat",
            json={"question": "What does this document say about pricing?"},
        )

    assert response.status_code == 200
    assert response.json() == {
        "answer": "The document states pricing is based on usage tiers.",
            "sources": [
                {
                    "document_id": str(FIXED_DOCUMENT_ID),
                    "chunk_id": str(FIXED_CHUNK_ID),
                    "file_name": "pricing.pdf",
                    "chunk_index": 12,
                    "page_start": 3,
                    "page_end": 4,
                    "heading": None,
                    "qdrant_score": 0.78,
                    "rerank_score": 0.91,
                    "section_path": [],
                    "content_preview": "",
                    "is_neighbor_context": False,
                }
        ],
    }


def test_chat_route_returns_api_error_when_query_graph_reports_failure(monkeypatch):
    settings = _test_settings()
    fake_graph = FakeQueryGraph(result={"error_message": "ShopAIKey chat failure"})

    _patch_route_settings(monkeypatch, settings)
    monkeypatch.setattr(
        chat_route,
        "build_query_graph",
        lambda settings=None: fake_graph,
    )

    app = _test_app(settings)

    with TestClient(app) as test_client:
        response = test_client.post(
            "/api/chat",
            json={"question": "What does this document say about pricing?"},
        )

    assert response.status_code == 500
    assert response.json() == {"detail": "ShopAIKey chat failure"}
