import logging
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, call
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import app
from app.services import document_service
from app.services.qdrant_service import QdrantDeleteError
from app.services.supabase_service import SupabaseConnectionError


DOCUMENT_ID = UUID("44444444-4444-4444-8444-444444444444")
STORAGE_PATH = f"documents/single_user/{DOCUMENT_ID}/sample.txt"
SAFE_MESSAGE = "Document deletion failed. Please try again."


def _settings() -> SimpleNamespace:
    return SimpleNamespace(single_user_id="single_user")


def _document_row() -> dict:
    return {
        "id": str(DOCUMENT_ID),
        "user_id": "single_user",
        "file_name": "sample.txt",
        "storage_path": STORAGE_PATH,
    }


def _cascade_row() -> dict:
    return {
        "document_id": str(DOCUMENT_ID),
        "file_name": "sample.txt",
        "deleted": True,
        "deleted_storage_file": True,
        "deleted_qdrant_points": True,
        "deleted_chunks": 3,
        "deleted_entities": 4,
        "deleted_relationships": 5,
        "deleted_agent_runs": 2,
        "deleted_agent_steps": 6,
        "deleted_chat_messages": 7,
        "deleted_chat_sessions": 1,
    }


def _successful_audit_row() -> dict:
    return {
        **{key: value for key, value in _cascade_row().items() if key != "deleted"},
        "status": "success",
    }


def _install_success_adapters(monkeypatch, *, cascade_row=None):
    events: list[str] = []
    get_metadata = Mock(side_effect=lambda *_: events.append("preflight") or _document_row())
    delete_vectors = Mock(side_effect=lambda *_: events.append("qdrant") or True)
    remove_file = Mock(side_effect=lambda *_: events.append("storage") or True)
    cascade = Mock(
        side_effect=lambda *_: events.append("database")
        or (_cascade_row() if cascade_row is None else cascade_row)
    )
    audit = Mock()
    successful_audit = Mock(return_value=None)

    monkeypatch.setattr(document_service, "get_settings", _settings)
    monkeypatch.setattr(document_service, "get_document_metadata", get_metadata)
    monkeypatch.setattr(document_service, "delete_document_vectors", delete_vectors)
    monkeypatch.setattr(document_service, "remove_document_file", remove_file)
    monkeypatch.setattr(document_service, "delete_owned_document_cascade", cascade)
    monkeypatch.setattr(document_service, "insert_deletion_log", audit)
    monkeypatch.setattr(
        document_service, "get_successful_deletion_log", successful_audit
    )
    return (
        events,
        get_metadata,
        delete_vectors,
        remove_file,
        cascade,
        audit,
        successful_audit,
    )


def test_delete_document_orders_operations_and_maps_exact_counts(monkeypatch) -> None:
    events, get_metadata, delete_vectors, remove_file, cascade, audit, _ = (
        _install_success_adapters(monkeypatch)
    )

    response = document_service.delete_document(DOCUMENT_ID)

    assert events == ["preflight", "qdrant", "storage", "database", "qdrant"]
    assert response.model_dump(mode="json") == {
        "document_id": str(DOCUMENT_ID),
        "deleted": True,
        "deleted_agent_runs": 2,
        "deleted_agent_steps": 6,
        "deleted_chat_messages": 7,
        "deleted_chat_sessions": 1,
        "deleted_chunks": 3,
        "deleted_entities": 4,
        "deleted_relationships": 5,
        "deleted_qdrant_points": True,
        "deleted_storage_file": True,
    }
    get_metadata.assert_called_once_with(str(DOCUMENT_ID), "single_user")
    assert delete_vectors.call_args_list == [call(DOCUMENT_ID), call(DOCUMENT_ID)]
    remove_file.assert_called_once_with(STORAGE_PATH)
    cascade.assert_called_once_with(str(DOCUMENT_ID), "single_user")
    audit.assert_not_called()


def test_delete_document_preflight_miss_has_no_external_calls(monkeypatch) -> None:
    _, get_metadata, delete_vectors, remove_file, cascade, audit, _ = (
        _install_success_adapters(monkeypatch)
    )
    get_metadata.return_value = None
    get_metadata.side_effect = None

    with pytest.raises(document_service.DocumentNotFoundError):
        document_service.delete_document(DOCUMENT_ID)

    delete_vectors.assert_not_called()
    remove_file.assert_not_called()
    cascade.assert_not_called()
    audit.assert_not_called()


@pytest.mark.parametrize(
    ("failure_stage", "failing_adapter", "expected_qdrant", "expected_storage"),
    [
        ("qdrant", "delete_document_vectors", False, False),
        ("storage", "remove_document_file", True, False),
        ("database", "delete_owned_document_cascade", True, True),
    ],
)
def test_delete_document_stage_failure_writes_safe_audit(
    monkeypatch,
    caplog,
    failure_stage,
    failing_adapter,
    expected_qdrant,
    expected_storage,
) -> None:
    _, _, _, _, _, audit, _ = _install_success_adapters(monkeypatch)
    provider_secret = "provider-secret-detail"
    adapter_error = (
        QdrantDeleteError(provider_secret)
        if failing_adapter == "delete_document_vectors"
        else SupabaseConnectionError(provider_secret)
    )
    monkeypatch.setattr(
        document_service,
        failing_adapter,
        Mock(side_effect=adapter_error),
    )

    with caplog.at_level(logging.ERROR), pytest.raises(
        document_service.DocumentDeletionError
    ) as exc_info:
        document_service.delete_document(DOCUMENT_ID)

    assert str(exc_info.value) == SAFE_MESSAGE
    assert provider_secret not in caplog.text
    audit.assert_called_once_with(
        {
            "user_id": "single_user",
            "document_id": str(DOCUMENT_ID),
            "file_name": "sample.txt",
            "status": "failed",
            "failure_stage": failure_stage,
            "error_message": SAFE_MESSAGE,
            "deleted_storage_file": expected_storage,
            "deleted_qdrant_points": expected_qdrant,
            "deleted_chunks": 0,
            "deleted_entities": 0,
            "deleted_relationships": 0,
            "deleted_agent_runs": 0,
            "deleted_agent_steps": 0,
            "deleted_chat_messages": 0,
            "deleted_chat_sessions": 0,
        }
    )


def test_failed_audit_write_preserves_original_deletion_error(monkeypatch) -> None:
    _, _, _, _, _, audit, _ = _install_success_adapters(monkeypatch)
    monkeypatch.setattr(
        document_service,
        "remove_document_file",
        Mock(side_effect=SupabaseConnectionError("storage provider detail")),
    )
    audit.side_effect = SupabaseConnectionError("audit provider detail")

    with pytest.raises(document_service.DocumentDeletionError) as exc_info:
        document_service.delete_document(DOCUMENT_ID)

    assert str(exc_info.value) == SAFE_MESSAGE


def test_partial_progress_is_recorded_and_retry_repeats_idempotent_adapters(
    monkeypatch,
) -> None:
    _, _, delete_vectors, remove_file, cascade, audit, _ = _install_success_adapters(
        monkeypatch
    )
    remove_file.side_effect = [SupabaseConnectionError("temporary"), True]

    with pytest.raises(document_service.DocumentDeletionError):
        document_service.delete_document(DOCUMENT_ID)
    response = document_service.delete_document(DOCUMENT_ID)

    assert response.deleted is True
    assert delete_vectors.call_count == 3
    assert remove_file.call_count == 2
    cascade.assert_called_once_with(str(DOCUMENT_ID), "single_user")
    assert audit.call_args_list[0] == call(
        {
            "user_id": "single_user",
            "document_id": str(DOCUMENT_ID),
            "file_name": "sample.txt",
            "status": "failed",
            "failure_stage": "storage",
            "error_message": SAFE_MESSAGE,
            "deleted_storage_file": False,
            "deleted_qdrant_points": True,
            "deleted_chunks": 0,
            "deleted_entities": 0,
            "deleted_relationships": 0,
            "deleted_agent_runs": 0,
            "deleted_agent_steps": 0,
            "deleted_chat_messages": 0,
            "deleted_chat_sessions": 0,
        }
    )


def test_database_failure_retry_repeats_external_deletes_and_then_succeeds(
    monkeypatch,
    caplog,
) -> None:
    events: list[str] = []
    provider_secret = "database-provider-secret"
    get_metadata = Mock(
        side_effect=lambda *_: events.append("preflight") or _document_row()
    )
    delete_vectors = Mock(side_effect=lambda *_: events.append("qdrant") or True)
    remove_file = Mock(side_effect=lambda *_: events.append("storage") or True)
    cascade_results = iter([SupabaseConnectionError(provider_secret), _cascade_row()])

    def cascade(*_args):
        events.append("database")
        result = next(cascade_results)
        if isinstance(result, Exception):
            raise result
        return result

    cascade_mock = Mock(side_effect=cascade)
    audit = Mock()
    monkeypatch.setattr(document_service, "get_settings", _settings)
    monkeypatch.setattr(document_service, "get_document_metadata", get_metadata)
    monkeypatch.setattr(document_service, "delete_document_vectors", delete_vectors)
    monkeypatch.setattr(document_service, "remove_document_file", remove_file)
    monkeypatch.setattr(
        document_service, "delete_owned_document_cascade", cascade_mock
    )
    monkeypatch.setattr(document_service, "insert_deletion_log", audit)
    monkeypatch.setattr(
        document_service, "get_successful_deletion_log", Mock(return_value=None)
    )

    with caplog.at_level(logging.ERROR), pytest.raises(
        document_service.DocumentDeletionError
    ) as exc_info:
        document_service.delete_document(DOCUMENT_ID)
    response = document_service.delete_document(DOCUMENT_ID)

    assert str(exc_info.value) == SAFE_MESSAGE
    assert provider_secret not in caplog.text
    assert events == [
        "preflight",
        "qdrant",
        "storage",
        "database",
        "preflight",
        "qdrant",
        "storage",
        "database",
        "qdrant",
    ]
    assert get_metadata.call_count == 2
    assert delete_vectors.call_args_list == [
        call(DOCUMENT_ID),
        call(DOCUMENT_ID),
        call(DOCUMENT_ID),
    ]
    assert remove_file.call_args_list == [call(STORAGE_PATH), call(STORAGE_PATH)]
    assert cascade_mock.call_args_list == [
        call(str(DOCUMENT_ID), "single_user"),
        call(str(DOCUMENT_ID), "single_user"),
    ]
    audit.assert_called_once_with(
        {
            "user_id": "single_user",
            "document_id": str(DOCUMENT_ID),
            "file_name": "sample.txt",
            "status": "failed",
            "failure_stage": "database",
            "error_message": SAFE_MESSAGE,
            "deleted_storage_file": True,
            "deleted_qdrant_points": True,
            "deleted_chunks": 0,
            "deleted_entities": 0,
            "deleted_relationships": 0,
            "deleted_agent_runs": 0,
            "deleted_agent_steps": 0,
            "deleted_chat_messages": 0,
            "deleted_chat_sessions": 0,
        }
    )
    assert response.model_dump(mode="json") == {
        "document_id": str(DOCUMENT_ID),
        "deleted": True,
        "deleted_agent_runs": 2,
        "deleted_agent_steps": 6,
        "deleted_chat_messages": 7,
        "deleted_chat_sessions": 1,
        "deleted_chunks": 3,
        "deleted_entities": 4,
        "deleted_relationships": 5,
        "deleted_qdrant_points": True,
        "deleted_storage_file": True,
    }


@pytest.mark.parametrize(
    "malformed_row",
    [
        {"document_id": str(DOCUMENT_ID)},
        {**_cascade_row(), "deleted_storage_file": 1},
        {**_cascade_row(), "deleted_chunks": -1},
        {**_cascade_row(), "deleted": False},
        {**_cascade_row(), "deleted_qdrant_points": False},
        {**_cascade_row(), "deleted_storage_file": False},
    ],
)
def test_malformed_rpc_success_row_without_audit_records_database_failure(
    monkeypatch,
    caplog,
    malformed_row,
) -> None:
    _, _, _, _, cascade, audit, successful_audit = _install_success_adapters(
        monkeypatch
    )
    cascade.side_effect = None
    cascade.return_value = malformed_row

    with caplog.at_level(logging.ERROR), pytest.raises(
        document_service.DocumentDeletionError
    ) as exc_info:
        document_service.delete_document(DOCUMENT_ID)

    assert str(exc_info.value) == SAFE_MESSAGE
    assert "validation error" not in caplog.text.lower()
    successful_audit.assert_called_once_with("single_user", str(DOCUMENT_ID))
    assert audit.call_args.args[0]["failure_stage"] == "database"
    assert audit.call_args.args[0]["deleted_qdrant_points"] is True
    assert audit.call_args.args[0]["deleted_storage_file"] is True


def test_rpc_success_row_rejects_mismatched_document_id(monkeypatch) -> None:
    row = _cascade_row()
    row["document_id"] = "55555555-5555-4555-8555-555555555555"
    _, _, _, _, cascade, audit, successful_audit = _install_success_adapters(
        monkeypatch
    )
    cascade.side_effect = None
    cascade.return_value = row

    with pytest.raises(document_service.DocumentDeletionError) as exc_info:
        document_service.delete_document(DOCUMENT_ID)

    assert str(exc_info.value) == SAFE_MESSAGE
    successful_audit.assert_called_once_with("single_user", str(DOCUMENT_ID))
    assert audit.call_args.args[0]["failure_stage"] == "database"


@pytest.mark.parametrize(
    "malformed_row",
    [
        {"document_id": str(DOCUMENT_ID)},
        {**_cascade_row(), "deleted_qdrant_points": False},
        {**_cascade_row(), "deleted_storage_file": False},
    ],
)
def test_malformed_rpc_success_row_reconciles_valid_success_audit(
    monkeypatch,
    malformed_row,
) -> None:
    _, _, _, _, cascade, audit, successful_audit = _install_success_adapters(
        monkeypatch
    )
    cascade.side_effect = None
    cascade.return_value = malformed_row
    successful_audit.return_value = _successful_audit_row()

    response = document_service.delete_document(DOCUMENT_ID)

    assert response.deleted is True
    assert response.deleted_qdrant_points is True
    assert response.deleted_storage_file is True
    successful_audit.assert_called_once_with("single_user", str(DOCUMENT_ID))
    audit.assert_not_called()


def test_rpc_transport_error_reconciles_committed_success(monkeypatch) -> None:
    (
        events,
        _,
        delete_vectors,
        remove_file,
        cascade,
        audit,
        successful_audit,
    ) = _install_success_adapters(monkeypatch)
    cascade.side_effect = SupabaseConnectionError("rpc response secret")
    successful_audit.return_value = _successful_audit_row()

    response = document_service.delete_document(DOCUMENT_ID)

    assert response.deleted is True
    assert events == ["preflight", "qdrant", "storage", "qdrant"]
    assert delete_vectors.call_args_list == [call(DOCUMENT_ID), call(DOCUMENT_ID)]
    remove_file.assert_called_once_with(STORAGE_PATH)
    successful_audit.assert_called_once_with("single_user", str(DOCUMENT_ID))
    audit.assert_not_called()


def test_final_qdrant_sweep_failure_returns_safe_deletion_error(monkeypatch) -> None:
    _, _, delete_vectors, _, _, audit, _ = _install_success_adapters(monkeypatch)
    delete_vectors.side_effect = [True, QdrantDeleteError("late qdrant secret")]

    with pytest.raises(document_service.DocumentDeletionError) as exc_info:
        document_service.delete_document(DOCUMENT_ID)

    assert str(exc_info.value) == SAFE_MESSAGE
    assert delete_vectors.call_args_list == [call(DOCUMENT_ID), call(DOCUMENT_ID)]
    audit.assert_not_called()


def test_missing_document_with_success_audit_retries_final_qdrant_sweep(
    monkeypatch,
) -> None:
    _, get_metadata, delete_vectors, remove_file, cascade, audit, successful_audit = (
        _install_success_adapters(monkeypatch)
    )
    get_metadata.return_value = None
    get_metadata.side_effect = None
    successful_audit.return_value = _successful_audit_row()

    response = document_service.delete_document(DOCUMENT_ID)

    assert response.deleted is True
    delete_vectors.assert_called_once_with(DOCUMENT_ID)
    remove_file.assert_not_called()
    cascade.assert_not_called()
    audit.assert_not_called()


def test_missing_document_with_success_audit_returns_safe_error_when_qdrant_retry_fails(
    monkeypatch,
) -> None:
    _, get_metadata, delete_vectors, remove_file, cascade, audit, successful_audit = (
        _install_success_adapters(monkeypatch)
    )
    get_metadata.return_value = None
    get_metadata.side_effect = None
    successful_audit.return_value = _successful_audit_row()
    delete_vectors.side_effect = QdrantDeleteError("late qdrant secret")

    with pytest.raises(document_service.DocumentDeletionError) as exc_info:
        document_service.delete_document(DOCUMENT_ID)

    assert str(exc_info.value) == SAFE_MESSAGE
    delete_vectors.assert_called_once_with(DOCUMENT_ID)
    remove_file.assert_not_called()
    cascade.assert_not_called()
    audit.assert_not_called()


def test_rpc_transport_error_without_success_audit_preserves_database_failure(
    monkeypatch,
    caplog,
) -> None:
    _, _, _, _, cascade, audit, successful_audit = _install_success_adapters(
        monkeypatch
    )
    provider_secret = "rpc response secret"
    cascade.side_effect = SupabaseConnectionError(provider_secret)

    with caplog.at_level(logging.ERROR), pytest.raises(
        document_service.DocumentDeletionError
    ) as exc_info:
        document_service.delete_document(DOCUMENT_ID)

    assert str(exc_info.value) == SAFE_MESSAGE
    assert provider_secret not in caplog.text
    successful_audit.assert_called_once_with("single_user", str(DOCUMENT_ID))
    assert audit.call_args.args[0]["failure_stage"] == "database"


def test_reconciliation_lookup_failure_preserves_database_failure(monkeypatch) -> None:
    _, _, _, _, cascade, audit, successful_audit = _install_success_adapters(
        monkeypatch
    )
    cascade.side_effect = SupabaseConnectionError("rpc secret")
    successful_audit.side_effect = SupabaseConnectionError("lookup secret")

    with pytest.raises(document_service.DocumentDeletionError) as exc_info:
        document_service.delete_document(DOCUMENT_ID)

    assert str(exc_info.value) == SAFE_MESSAGE
    assert audit.call_args.args[0]["failure_stage"] == "database"


def test_cascade_none_after_preflight_maps_to_not_found(monkeypatch) -> None:
    _, _, delete_vectors, remove_file, _, audit, _ = _install_success_adapters(
        monkeypatch, cascade_row=None
    )
    monkeypatch.setattr(
        document_service,
        "delete_owned_document_cascade",
        Mock(return_value=None),
    )

    with pytest.raises(document_service.DocumentNotFoundError):
        document_service.delete_document(DOCUMENT_ID)

    delete_vectors.assert_called_once_with(DOCUMENT_ID)
    remove_file.assert_called_once_with(STORAGE_PATH)
    audit.assert_not_called()


client = TestClient(app)


def test_delete_document_route_returns_typed_200(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.api.documents.document_service.delete_document",
        Mock(return_value=document_service.DocumentDeleteResponse(**_cascade_row())),
    )

    response = client.delete(f"/api/documents/{DOCUMENT_ID}")

    assert response.status_code == 200
    assert response.json()["document_id"] == str(DOCUMENT_ID)
    assert response.json()["deleted_agent_steps"] == 6


@pytest.mark.parametrize(
    ("error_kind", "status_code", "detail"),
    [
        ("not_found", 404, "Document not found."),
        ("deletion", 500, SAFE_MESSAGE),
    ],
)
def test_delete_document_route_maps_safe_errors(
    monkeypatch, error_kind, status_code, detail
) -> None:
    error = (
        document_service.DocumentNotFoundError("Document not found.")
        if error_kind == "not_found"
        else document_service.DocumentDeletionError(SAFE_MESSAGE)
    )
    monkeypatch.setattr(
        "app.api.documents.document_service.delete_document",
        Mock(side_effect=error),
    )

    response = client.delete(f"/api/documents/{DOCUMENT_ID}")

    assert response.status_code == status_code
    assert response.json() == {"detail": detail}


def test_delete_document_route_suppresses_deletion_exception_text(monkeypatch) -> None:
    secret = "provider-secret-in-exception"
    monkeypatch.setattr(
        "app.api.documents.document_service.delete_document",
        Mock(side_effect=document_service.DocumentDeletionError(secret)),
    )

    response = client.delete(f"/api/documents/{DOCUMENT_ID}")

    assert response.status_code == 500
    assert response.json() == {"detail": SAFE_MESSAGE}
    assert secret not in response.text


def test_delete_document_route_rejects_malformed_uuid() -> None:
    response = client.delete("/api/documents/not-a-uuid")

    assert response.status_code == 422
