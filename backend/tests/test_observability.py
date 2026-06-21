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
        trace=[{"node": "retrieve", "count": 3}],
        finished_at=finished,
        duration_ms=1000,
        supabase_client=client,
    )

    assert result["id"] == str(RUN_ID)
    assert client.calls[0].filters == [("id", str(RUN_ID))]
    assert client.calls[0].payload["status"] == "completed"
    assert client.calls[0].payload["finished_at"] == finished.isoformat()


def test_list_and_get_workflow_runs_handle_empty_responses_and_ordering():
    client = FakeClient(None, None)

    assert observability.list_workflow_runs(supabase_client=client) == []
    assert observability.get_workflow_run(RUN_ID, supabase_client=client) is None
    assert client.calls[0].order_clause == ("created_at", True)
    assert client.calls[1].filters == [("id", str(RUN_ID))]
    assert client.calls[1].limit_count == 1


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

