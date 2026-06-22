from __future__ import annotations

from uuid import UUID

from fastapi.testclient import TestClient

from app.api.routes import chat as chat_route
from app.api.routes import observability as observability_route
from app.core.config import Settings
from app.main import create_app

RUN_ID = UUID("11111111-1111-1111-1111-111111111111")


def _test_settings() -> Settings:
    return Settings(
        _env_file=None,
        ADMIN_API_TOKEN="admin-token",
        SUPABASE_STORAGE_BUCKET="documents",
        QDRANT_COLLECTION="document_chunks_v1",
    )


def test_list_runs_requires_admin_token(monkeypatch):
    settings = _test_settings()
    monkeypatch.setattr(
        observability_route.observability,
        "list_workflow_runs",
        lambda **kwargs: [],
    )
    app = create_app(settings=settings)

    with TestClient(app) as test_client:
        response = test_client.get("/api/observability/runs")

    assert response.status_code == 401


def test_list_runs_clamps_limit_and_returns_newest_first_from_service(monkeypatch):
    settings = _test_settings()
    calls: list[dict[str, object]] = []

    def _list_runs(**kwargs):
        calls.append(dict(kwargs))
        return [
            {
                "id": str(RUN_ID),
                "workflow_type": "query",
                "status": "completed",
                "trace": [],
                "created_at": "2026-06-22T08:00:00Z",
            }
        ]

    monkeypatch.setattr(observability_route.observability, "list_workflow_runs", _list_runs)
    app = create_app(settings=settings)

    with TestClient(app) as test_client:
        response = test_client.get(
            "/api/observability/runs?workflow_type=query&status=completed&limit=500",
            headers={"X-Admin-API-Token": "admin-token"},
        )

    assert response.status_code == 200
    assert response.json()["runs"][0]["id"] == str(RUN_ID)
    assert calls == [
        {
            "workflow_type": "query",
            "status": "completed",
            "limit": 100,
        }
    ]


def test_get_run_returns_404_for_unknown_id(monkeypatch):
    settings = _test_settings()
    monkeypatch.setattr(observability_route.observability, "get_workflow_run", lambda run_id: None)
    app = create_app(settings=settings)

    with TestClient(app) as test_client:
        response = test_client.get(
            f"/api/observability/runs/{RUN_ID}",
            headers={"X-Admin-API-Token": "admin-token"},
        )

    assert response.status_code == 404


def test_get_run_returns_detail_payload(monkeypatch):
    settings = _test_settings()
    monkeypatch.setattr(
        observability_route.observability,
        "get_workflow_run",
        lambda run_id: {
            "id": str(run_id),
            "workflow_type": "ingestion",
            "status": "failed",
            "trace": [
                {
                    "node_name": "parse_document",
                    "status": "failed",
                    "attempt": 1,
                    "duration_ms": 2,
                    "error_code": "parse_failed",
                }
            ],
        },
    )
    app = create_app(settings=settings)

    with TestClient(app) as test_client:
        response = test_client.get(
            f"/api/observability/runs/{RUN_ID}",
            headers={"X-Admin-API-Token": "admin-token"},
        )

    assert response.status_code == 200
    assert response.json()["trace"][0]["node_name"] == "parse_document"


class FakeQueryGraph:
    def __init__(self, result: dict[str, object]) -> None:
        self.result = result
        self.invocations: list[dict[str, object]] = []

    def invoke(self, state: dict[str, object]) -> dict[str, object]:
        self.invocations.append(dict(state))
        return dict(self.result)


def test_chat_api_creates_and_closes_query_run(monkeypatch):
    settings = _test_settings()
    settings.ADMIN_API_TOKEN = ""
    fake_graph = FakeQueryGraph(
        {
            "answer": "The indexed documents do not contain enough verified information to answer this question.",
            "sources": [],
            "workflow_trace": [
                {
                    "node_name": "prepare_query",
                    "status": "completed",
                    "attempt": 1,
                    "duration_ms": 1,
                }
            ],
        }
    )
    created: list[dict[str, object]] = []
    updated: list[dict[str, object]] = []

    monkeypatch.setattr(chat_route, "get_settings", lambda: settings)
    monkeypatch.setattr(chat_route, "build_query_graph", lambda settings=None: fake_graph)
    monkeypatch.setattr(
        chat_route.observability,
        "create_workflow_run",
        lambda **kwargs: created.append(dict(kwargs)) or {"id": str(RUN_ID)},
    )
    monkeypatch.setattr(
        chat_route.observability,
        "update_workflow_run",
        lambda run_id, **kwargs: updated.append({"run_id": str(run_id), **kwargs})
        or {"id": str(run_id)},
    )
    app = create_app(settings=settings)

    with TestClient(app) as test_client:
        response = test_client.post("/api/chat", json={"question": "What is pricing?"})

    assert response.status_code == 200
    assert response.json()["trace_id"] == str(RUN_ID)
    assert created[0]["workflow_type"] == "query"
    assert fake_graph.invocations[0]["trace_id"] == str(RUN_ID)
    assert updated[0]["status"] == "completed"
    assert updated[0]["trace"][0]["node_name"] == "prepare_query"
    assert updated[0]["trace"][-1]["event_type"] == "retrieval_totals"


def test_chat_api_trace_persistence_failure_does_not_change_success(monkeypatch):
    settings = _test_settings()
    settings.ADMIN_API_TOKEN = ""
    fake_graph = FakeQueryGraph(
        {
            "answer": "The indexed documents do not contain enough verified information to answer this question.",
            "sources": [],
        }
    )

    monkeypatch.setattr(chat_route, "get_settings", lambda: settings)
    monkeypatch.setattr(chat_route, "build_query_graph", lambda settings=None: fake_graph)
    monkeypatch.setattr(chat_route.observability, "create_workflow_run", lambda **kwargs: None)
    monkeypatch.setattr(
        chat_route.observability,
        "update_workflow_run",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("no run id")),
    )
    app = create_app(settings=settings)

    with TestClient(app) as test_client:
        response = test_client.post("/api/chat", json={"question": "What is pricing?"})

    assert response.status_code == 200
    assert "trace_id" not in response.json()
