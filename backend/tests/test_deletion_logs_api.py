import sys
from datetime import datetime, timezone
from importlib import import_module
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.schemas.deletion_logs import (
    DeletionLogListResponse,
    DeletionLogResponse,
    DeletionLogStatus,
)
from app.services import deletion_log_service


LOG_ID = UUID("11111111-1111-1111-1111-111111111111")
DOCUMENT_ID = UUID("22222222-2222-2222-2222-222222222222")
CREATED_AT = datetime(2026, 6, 14, 9, 30, tzinfo=timezone.utc)


def _row(**overrides: object) -> dict:
    row = {
        "id": str(LOG_ID),
        "document_id": str(DOCUMENT_ID),
        "file_name": "contract.pdf",
        "status": "success",
        "failure_stage": None,
        "error_message": None,
        "deleted_storage_file": True,
        "deleted_qdrant_points": True,
        "deleted_chunks": 3,
        "deleted_entities": 2,
        "deleted_relationships": 1,
        "deleted_agent_runs": 4,
        "deleted_agent_steps": 12,
        "deleted_chat_messages": 8,
        "deleted_chat_sessions": 1,
        "created_at": CREATED_AT.isoformat(),
    }
    row.update(overrides)
    return row


def _client() -> TestClient:
    from app.api.deletion_logs import router

    app = FastAPI()
    app.include_router(router, prefix="/api/deletion-logs")
    return TestClient(app)


def test_deletion_log_response_has_exact_public_shape() -> None:
    item = DeletionLogResponse.model_validate(_row())

    assert item.model_dump(mode="json") == {
        "id": str(LOG_ID),
        "document_id": str(DOCUMENT_ID),
        "file_name": "contract.pdf",
        "status": "success",
        "failure_stage": None,
        "error_message": None,
        "deleted_storage_file": True,
        "deleted_qdrant_points": True,
        "deleted_chunks": 3,
        "deleted_entities": 2,
        "deleted_relationships": 1,
        "deleted_agent_runs": 4,
        "deleted_agent_steps": 12,
        "deleted_chat_messages": 8,
        "deleted_chat_sessions": 1,
        "created_at": "2026-06-14T09:30:00Z",
    }


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("status", "pending"),
        ("deleted_storage_file", 1),
        ("deleted_qdrant_points", "true"),
        ("deleted_chunks", -1),
        ("deleted_entities", "2"),
    ],
)
def test_deletion_log_response_rejects_malformed_values(
    field: str,
    value: object,
) -> None:
    with pytest.raises(ValidationError):
        DeletionLogResponse.model_validate(_row(**{field: value}))


def test_deletion_log_response_rejects_private_or_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        DeletionLogResponse.model_validate(_row(user_id="single_user"))


def test_deletion_log_status_is_exported_from_schema() -> None:
    valid_status: DeletionLogStatus = "success"

    assert valid_status == "success"


def test_list_deletion_logs_uses_configured_user_filter_and_limit_lookahead(
    monkeypatch,
) -> None:
    adapter = Mock(return_value=[_row(), _row(id="33333333-3333-3333-3333-333333333333")])
    monkeypatch.setattr(deletion_log_service, "get_settings", lambda: SimpleNamespace(single_user_id="owner"))
    monkeypatch.setattr(deletion_log_service, "fetch_deletion_logs", adapter)

    result = deletion_log_service.list_deletion_logs(
        status="failed",
        limit=1,
        offset=5,
    )

    adapter.assert_called_once_with("owner", "failed", 2, 5)
    assert isinstance(result, DeletionLogListResponse)
    assert len(result.logs) == 1
    assert result.limit == 1
    assert result.offset == 5
    assert result.has_more is True


def test_list_deletion_logs_reports_no_more_when_lookahead_is_absent(
    monkeypatch,
) -> None:
    monkeypatch.setattr(deletion_log_service, "get_settings", lambda: SimpleNamespace(single_user_id="owner"))
    monkeypatch.setattr(deletion_log_service, "fetch_deletion_logs", Mock(return_value=[_row()]))

    result = deletion_log_service.list_deletion_logs(status=None, limit=2, offset=0)

    assert len(result.logs) == 1
    assert result.has_more is False


def test_list_deletion_logs_preserves_newest_first_adapter_order_when_trimming(
    monkeypatch,
) -> None:
    newest_id = "33333333-3333-3333-3333-333333333333"
    middle_id = "44444444-4444-4444-4444-444444444444"
    lookahead_id = "55555555-5555-5555-5555-555555555555"
    rows = [
        _row(id=newest_id, created_at="2026-06-14T12:00:00+00:00"),
        _row(id=middle_id, created_at="2026-06-14T11:00:00+00:00"),
        _row(id=lookahead_id, created_at="2026-06-14T10:00:00+00:00"),
    ]
    monkeypatch.setattr(
        deletion_log_service,
        "get_settings",
        lambda: SimpleNamespace(single_user_id="owner"),
    )
    monkeypatch.setattr(
        deletion_log_service,
        "fetch_deletion_logs",
        Mock(return_value=rows),
    )

    result = deletion_log_service.list_deletion_logs(
        status=None,
        limit=2,
        offset=4,
    )

    assert [str(log.id) for log in result.logs] == [newest_id, middle_id]
    assert result.offset == 4
    assert result.has_more is True


@pytest.mark.parametrize(
    "dependency_result",
    [
        RuntimeError("database password leaked"),
        [_row(deleted_chunks="invalid")],
    ],
)
def test_list_deletion_logs_wraps_dependency_and_validation_failures(
    monkeypatch,
    dependency_result,
) -> None:
    def fail_or_return(*_args):
        if isinstance(dependency_result, Exception):
            raise dependency_result
        return dependency_result

    monkeypatch.setattr(deletion_log_service, "get_settings", lambda: SimpleNamespace(single_user_id="owner"))
    monkeypatch.setattr(deletion_log_service, "fetch_deletion_logs", fail_or_return)

    with pytest.raises(deletion_log_service.DeletionLogServiceError) as exc_info:
        deletion_log_service.list_deletion_logs(status=None, limit=20, offset=0)

    assert str(exc_info.value) == "Deletion logs are temporarily unavailable."
    assert "password" not in str(exc_info.value)


def test_get_deletion_logs_returns_filtered_public_response(monkeypatch) -> None:
    service = Mock(
        return_value=DeletionLogListResponse(
            logs=[
                DeletionLogResponse.model_validate(
                    _row(
                        status="failed",
                        failure_stage="storage",
                        error_message="Storage deletion failed.",
                        deleted_storage_file=False,
                        deleted_qdrant_points=True,
                    )
                )
            ],
            limit=20,
            offset=0,
            has_more=False,
        )
    )
    monkeypatch.setattr(deletion_log_service, "list_deletion_logs", service)

    response = _client().get("/api/deletion-logs?status=failed")

    assert response.status_code == 200
    service.assert_called_once_with(status="failed", limit=20, offset=0)
    assert response.json() == {
        "logs": [
            {
                "id": str(LOG_ID),
                "document_id": str(DOCUMENT_ID),
                "file_name": "contract.pdf",
                "status": "failed",
                "failure_stage": "storage",
                "error_message": "Storage deletion failed.",
                "deleted_storage_file": False,
                "deleted_qdrant_points": True,
                "deleted_chunks": 3,
                "deleted_entities": 2,
                "deleted_relationships": 1,
                "deleted_agent_runs": 4,
                "deleted_agent_steps": 12,
                "deleted_chat_messages": 8,
                "deleted_chat_sessions": 1,
                "created_at": "2026-06-14T09:30:00Z",
            }
        ],
        "limit": 20,
        "offset": 0,
        "has_more": False,
    }


@pytest.mark.parametrize(
    "query",
    [
        "?status=pending",
        "?limit=0",
        "?limit=101",
        "?offset=-1",
    ],
)
def test_get_deletion_logs_rejects_invalid_parameters(query: str) -> None:
    response = _client().get(f"/api/deletion-logs{query}")

    assert response.status_code == 422


@pytest.mark.parametrize(
    "failure",
    [
        deletion_log_service.DeletionLogServiceError(),
        RuntimeError("database password leaked"),
    ],
)
def test_get_deletion_logs_returns_safe_500(monkeypatch, failure: Exception) -> None:
    monkeypatch.setattr(
        deletion_log_service,
        "list_deletion_logs",
        Mock(side_effect=failure),
    )

    response = _client().get("/api/deletion-logs")

    assert response.status_code == 500
    assert response.json() == {
        "detail": "Deletion logs are temporarily unavailable."
    }


def test_production_app_registers_deletion_logs_route() -> None:
    main = import_module("app.main")
    paths = {route.path for route in main.app.routes}

    assert "/api/deletion-logs" in paths
