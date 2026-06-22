from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import UUID

from app.services import observability


RUN_ID = UUID("11111111-1111-1111-1111-111111111111")


class FakeResponse:
    def __init__(self, data=None):
        self.data = data


class FakeQuery:
    def __init__(self, client, table_name):
        self.client = client
        self.table_name = table_name
        self.operation = "select"
        self.payload = None
        self.filters = []
        self.order_clause = None
        self.limit_count = None

    def select(self, *_args):
        self.operation = "select"
        return self

    def insert(self, payload):
        self.operation = "insert"
        self.payload = payload
        return self

    def update(self, payload):
        self.operation = "update"
        self.payload = payload
        return self

    def eq(self, field, value):
        self.filters.append((field, value))
        return self

    def order(self, field, *, desc=False):
        self.order_clause = (field, desc)
        return self

    def limit(self, value):
        self.limit_count = value
        return self

    def execute(self):
        if self.client.error is not None:
            raise self.client.error
        self.client.calls.append(self)
        return FakeResponse(self.client.responses.pop(0) if self.client.responses else [])


class FakeClient:
    def __init__(self, *responses, error=None):
        self.responses = list(responses)
        self.error = error
        self.calls = []

    def table(self, table_name):
        return FakeQuery(self, table_name)


def test_create_workflow_run_normalizes_payload_and_returns_inserted_row():
    started = datetime(2026, 6, 21, 8, 0, tzinfo=timezone.utc)
    inserted = {
        "id": RUN_ID,
        "workflow_type": "query",
        "entity_id": "question-1",
        "status": "running",
        "trace": [],
        "started_at": started,
    }
    client = FakeClient([inserted])

    result = observability.create_workflow_run(
        workflow_type="query",
        entity_id=" question-1 ",
        trace=None,
        started_at=started,
        supabase_client=client,
    )

    assert result["id"] == str(RUN_ID)
    assert client.calls[0].payload == {
        "workflow_type": "query",
        "entity_id": "question-1",
        "status": "running",
        "trace": [],
        "started_at": started.isoformat(),
    }


def test_update_workflow_run_normalizes_status_uuid_and_completion_fields():
    finished = datetime(2026, 6, 21, 8, 0, 1, tzinfo=timezone.utc)
    client = FakeClient([])

    result = observability.update_workflow_run(
        RUN_ID,
        status="completed",
        trace=[
            {
                "node_name": "retrieve_candidates",
                "status": "completed",
                "attempt": 1,
                "output_count": 3,
            }
        ],
        finished_at=finished,
        duration_ms=1000,
        supabase_client=client,
    )

    assert result["id"] == str(RUN_ID)
    assert client.calls[0].filters == [("id", str(RUN_ID))]
    assert client.calls[0].payload["status"] == "completed"
    assert client.calls[0].payload["trace"][0]["output_count"] == 3
    assert client.calls[0].payload["finished_at"] == finished.isoformat()


def test_list_and_get_workflow_runs_handle_empty_responses_and_ordering():
    client = FakeClient(None, None)

    assert observability.list_workflow_runs(supabase_client=client) == []
    assert observability.get_workflow_run(RUN_ID, supabase_client=client) is None
    assert client.calls[0].order_clause == ("created_at", True)
    assert client.calls[1].filters == [("id", str(RUN_ID))]
    assert client.calls[1].limit_count == 1


def test_list_workflow_runs_clamps_limit_to_one_hundred():
    client = FakeClient([])

    observability.list_workflow_runs(limit=500, supabase_client=client)

    assert client.calls[0].limit_count == 100


def test_trace_redaction_removes_prohibited_content_and_credential_urls():
    event = {
        "node_name": "generate_answer",
        "status": "completed",
        "attempt": 1,
        "prompt": "raw prompt must not persist",
        "answer": "full model answer must not persist",
        "url": "https://user:pass@example.com/path",
        "headers": {"authorization": "Bearer secret"},
        "output_count": 1,
    }

    normalized = observability._normalize_trace([event])

    assert normalized == [
        {
            "node_name": "generate_answer",
            "status": "completed",
            "attempt": 1,
            "output_count": 1,
        }
    ]


def test_node_error_code_rejects_secret_like_dynamic_values():
    started = datetime(2026, 6, 21, 8, 0, tzinfo=timezone.utc)
    unsafe_values = [
        "https://example.test/path?api_key=SECRET123",
        "Bearer SECRET123",
        "api_key_SECRET123",
        "raw chunk content from document",
    ]

    for unsafe_value in unsafe_values:
        event = observability.node_trace_event(
            node_name="retrieve_candidates",
            status="failed",
            attempt=1,
            started_at=started,
            finished_at=started,
            duration_ms=0,
            error_code=unsafe_value,
        )

        assert event["error_code"] == "retrieve_candidates_failed"
        assert "SECRET123" not in str(event)
        assert "api_key" not in event["error_code"]
        assert "raw chunk content" not in str(event)


def test_retrieval_totals_event_contains_counts_without_source_text():
    event = observability.retrieval_totals_event(
        {
            "route": "hybrid",
            "subqueries": [{"id": "q1"}],
            "path_candidates": {
                "q1:semantic": [{"content": "secret source text"}],
                "q1:keyword": [{"content": "secret source text"}],
            },
            "fused_candidates": [{"content": "secret source text"}],
            "reranked_chunks": [{"content": "secret source text"}],
            "context_chunks": [{"content": "secret source text"}],
            "retrieval_metrics": {
                "fallback_path": "keyword",
                "context_token_count": 123,
            },
        },
        total_query_latency_ms=42,
    )

    assert event["semantic_count"] == 1
    assert event["keyword_count"] == 1
    assert event["fused_count"] == 1
    assert event["reranked_count"] == 1
    assert event["context_count"] == 1
    assert event["selected_strategy"] == "hybrid"
    assert event["fallback_path"] == "keyword"
    assert "content" not in event


def test_trace_create_failure_logs_warning_and_is_nonfatal(caplog):
    client = FakeClient(error=RuntimeError("database unavailable"))

    with caplog.at_level(logging.WARNING):
        result = observability.create_workflow_run(
            workflow_type="ingestion", supabase_client=client
        )

    assert result is None
    assert "workflow trace" in caplog.text.lower()
    assert "database unavailable" in caplog.text


def test_trace_update_failure_logs_warning_and_is_nonfatal(caplog):
    client = FakeClient(error=RuntimeError("write refused"))

    with caplog.at_level(logging.WARNING):
        result = observability.update_workflow_run(
            RUN_ID, status="failed", supabase_client=client
        )

    assert result is None
    assert "workflow trace" in caplog.text.lower()
