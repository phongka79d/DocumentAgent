from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.api.routes import messages as messages_route
from app.core.config import Settings
from app.main import create_app
from app.models.schemas import MessageResponse
from app.services import messages as message_service


FIRST_MESSAGE_ID = UUID("11111111-1111-1111-1111-111111111111")
SECOND_MESSAGE_ID = UUID("22222222-2222-2222-2222-222222222222")
THIRD_MESSAGE_ID = UUID("33333333-3333-3333-3333-333333333333")
FIRST_DOCUMENT_ID = UUID("44444444-4444-4444-4444-444444444444")
FIRST_CHUNK_ID = UUID("55555555-5555-5555-5555-555555555555")


def _test_settings() -> Settings:
    return Settings(
        _env_file=None,
        SUPABASE_STORAGE_BUCKET="documents",
        QDRANT_COLLECTION="document_chunks_v1",
    )


def _message_row(
    *,
    message_id: UUID,
    question: str,
    answer: str,
    created_at: datetime,
    sources: list[dict[str, object]] | None = None,
    metadata: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "id": message_id,
        "question": question,
        "answer": answer,
        "sources": sources,
        "metadata": metadata,
        "created_at": created_at,
    }


@dataclass
class FakeResponse:
    data: list[dict[str, object]] | dict[str, object] | None = None


@dataclass
class FakeTableQuery:
    client: "FakeSupabaseClient"
    table_name: str
    operation: str = "select"
    selected_columns: tuple[str, ...] = ()
    order_clause: tuple[str, bool] | None = None
    limit_count: int | None = None

    def select(self, *columns: str, count=None, head=None):
        self.operation = "select"
        self.selected_columns = columns
        return self

    def order(self, column: str, *, desc=False, nullsfirst=None, foreign_table=None):
        self.order_clause = (column, desc)
        return self

    def limit(self, size: int, *, foreign_table=None):
        self.limit_count = size
        return self

    def execute(self) -> FakeResponse:
        rows = list(self.client.tables.get(self.table_name, []))
        if self.order_clause is not None:
            column, desc = self.order_clause
            rows.sort(key=lambda row: row.get(column), reverse=desc)
        if self.limit_count is not None:
            rows = rows[: self.limit_count]

        self.client.query_log.append(
            {
                "table_name": self.table_name,
                "operation": self.operation,
                "selected_columns": self.selected_columns,
                "order_clause": self.order_clause,
                "limit": self.limit_count,
            }
        )
        return FakeResponse(data=rows)


@dataclass
class FakeSupabaseClient:
    messages: list[dict[str, object]] | None = None
    tables: dict[str, list[dict[str, object]]] = field(init=False)
    query_log: list[dict[str, object]] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.tables = {"messages": list(self.messages or [])}

    def table(self, table_name: str) -> FakeTableQuery:
        return FakeTableQuery(self, table_name)


def _patch_route_settings(monkeypatch, settings: Settings) -> None:
    monkeypatch.setattr(messages_route, "get_settings", lambda: settings)


def _test_app(settings: Settings):
    return create_app(settings=settings)


def test_list_messages_returns_newest_first_and_normalizes_json_fields():
    settings = _test_settings()
    oldest_row = _message_row(
        message_id=FIRST_MESSAGE_ID,
        question="What does the document say about pricing?",
        answer="Pricing is based on usage tiers.",
        created_at=datetime(2026, 6, 18, 8, 0, tzinfo=timezone.utc),
        sources=[
            {
                "document_id": str(FIRST_DOCUMENT_ID),
                "chunk_id": str(FIRST_CHUNK_ID),
                "file_name": "pricing.pdf",
                "chunk_index": 12,
                "page_start": 3,
                "page_end": 4,
                "heading": "Pricing",
                "qdrant_score": 0.78,
                "rerank_score": 0.91,
            }
        ],
        metadata={
            "document_ids": [str(FIRST_DOCUMENT_ID)],
            "prepared_query": "What does the document say about pricing?",
            "context_chunk_count": 2,
        },
    )
    newest_row = _message_row(
        message_id=SECOND_MESSAGE_ID,
        question="What are the support hours?",
        answer="Support is available from 9am to 5pm UTC.",
        created_at=datetime(2026, 6, 18, 9, 0, tzinfo=timezone.utc),
        sources=None,
        metadata=None,
    )
    fake_client = FakeSupabaseClient(messages=[oldest_row, newest_row])

    messages = message_service.list_messages(
        settings=settings,
        supabase_client=fake_client,
    )

    assert [message.id for message in messages] == [SECOND_MESSAGE_ID, FIRST_MESSAGE_ID]
    assert [message.question for message in messages] == [
        "What are the support hours?",
        "What does the document say about pricing?",
    ]
    assert isinstance(messages[0], MessageResponse)
    assert messages[0].sources == []
    assert messages[0].metadata == {}
    assert messages[1].sources[0].document_id == FIRST_DOCUMENT_ID
    assert messages[1].sources[0].chunk_id == FIRST_CHUNK_ID
    assert messages[1].metadata == {
        "document_ids": [str(FIRST_DOCUMENT_ID)],
        "prepared_query": "What does the document say about pricing?",
        "context_chunk_count": 2,
    }
    assert fake_client.query_log == [
        {
            "table_name": "messages",
            "operation": "select",
            "selected_columns": ("*",),
            "order_clause": ("created_at", True),
            "limit": 50,
        }
    ]


def test_list_messages_passes_custom_settings_to_client_factory(monkeypatch):
    settings = _test_settings()
    fake_client = FakeSupabaseClient(messages=[])
    received_settings: list[Settings | None] = []

    def _create_client(client_settings=None):
        received_settings.append(client_settings)
        return fake_client

    monkeypatch.setattr(message_service, "create_supabase_client", _create_client)

    messages = message_service.list_messages(settings=settings)

    assert messages == []
    assert received_settings == [settings]


@pytest.mark.parametrize(
    ("limit", "expected_limit", "expected_ids"),
    [
        (-5, 1, [THIRD_MESSAGE_ID]),
        (200, 100, [THIRD_MESSAGE_ID, SECOND_MESSAGE_ID, FIRST_MESSAGE_ID]),
    ],
)
def test_get_messages_route_clamps_limit_and_returns_newest_rows_first(
    monkeypatch,
    limit: int,
    expected_limit: int,
    expected_ids: list[UUID],
):
    settings = _test_settings()
    fake_client = FakeSupabaseClient(
        messages=[
            _message_row(
                message_id=FIRST_MESSAGE_ID,
                question="First question",
                answer="First answer",
                created_at=datetime(2026, 6, 18, 8, 0, tzinfo=timezone.utc),
                sources=[],
                metadata={},
            ),
            _message_row(
                message_id=SECOND_MESSAGE_ID,
                question="Second question",
                answer="Second answer",
                created_at=datetime(2026, 6, 18, 9, 0, tzinfo=timezone.utc),
                sources=[],
                metadata={},
            ),
            _message_row(
                message_id=THIRD_MESSAGE_ID,
                question="Third question",
                answer="Third answer",
                created_at=datetime(2026, 6, 18, 10, 0, tzinfo=timezone.utc),
                sources=[],
                metadata={},
            ),
        ]
    )

    _patch_route_settings(monkeypatch, settings)
    monkeypatch.setattr(
        message_service,
        "_resolve_supabase_client",
        lambda supabase_client=None, settings=None: fake_client,
    )

    app = _test_app(settings)

    with TestClient(app) as test_client:
        response = test_client.get("/api/messages", params={"limit": limit})

    assert response.status_code == 200
    payload = response.json()
    expected_questions = (
        ["Third question"]
        if expected_limit == 1
        else ["Third question", "Second question", "First question"]
    )
    assert [UUID(message["id"]) for message in payload["messages"]] == expected_ids
    assert [message["question"] for message in payload["messages"]] == expected_questions
    assert fake_client.query_log[-1]["limit"] == expected_limit


def test_get_messages_route_returns_safe_http_error_when_listing_fails(monkeypatch):
    settings = _test_settings()

    class BrokenQuery:
        def select(self, *columns: str, count=None, head=None):
            return self

        def order(self, column: str, *, desc=False, nullsfirst=None, foreign_table=None):
            return self

        def limit(self, size: int, *, foreign_table=None):
            return self

        def execute(self):
            raise RuntimeError("messages table is unavailable")

    class BrokenClient:
        def table(self, table_name: str):
            assert table_name == "messages"
            return BrokenQuery()

    _patch_route_settings(monkeypatch, settings)
    monkeypatch.setattr(
        message_service,
        "_resolve_supabase_client",
        lambda supabase_client=None, settings=None: BrokenClient(),
    )

    app = _test_app(settings)

    with TestClient(app) as test_client:
        response = test_client.get("/api/messages")

    assert response.status_code == 500
    assert response.json() == {"detail": messages_route.DEFAULT_MESSAGES_ERROR}
