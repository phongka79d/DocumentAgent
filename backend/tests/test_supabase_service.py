import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, call

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.schemas.parsing import ChunkDraft
from app.schemas.graph import EntityDraft, RelationshipDraft
from app.services import supabase_service
from app.services.supabase_service import SupabaseConnectionError


@pytest.fixture(autouse=True)
def reset_supabase_singleton() -> None:
    supabase_service._supabase_client = None
    yield
    supabase_service._supabase_client = None


def _settings(
    *,
    url: str = "https://example.supabase.co",
    service_role_key: str = "fake-service-role-key",
    storage_bucket: str = "documents",
) -> SimpleNamespace:
    return SimpleNamespace(
        require_supabase_settings=lambda: {
            "url": url,
            "service_role_key": service_role_key,
            "storage_bucket": storage_bucket,
        },
        supabase_storage_bucket=storage_bucket,
        single_user_id="single_user",
    )


def test_get_supabase_client_raises_clear_error_when_config_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = SimpleNamespace(
        require_supabase_settings=lambda: (_ for _ in ()).throw(
            RuntimeError(
                "Missing SUPABASE_URL. Configure it in the backend environment before using Supabase services."
            )
        )
    )
    monkeypatch.setattr(supabase_service, "get_settings", lambda: settings)

    with pytest.raises(SupabaseConnectionError) as exc_info:
        supabase_service.get_supabase_client()

    message = str(exc_info.value)
    assert "Backend Supabase configuration error" in message
    assert "SUPABASE_URL" in message


def test_get_supabase_client_creates_and_reuses_singleton(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = Mock()
    create_client = Mock(return_value=client)
    monkeypatch.setattr(supabase_service, "get_settings", lambda: _settings())
    monkeypatch.setattr(supabase_service, "create_client", create_client)

    first_client = supabase_service.get_supabase_client()
    second_client = supabase_service.get_supabase_client()

    assert first_client is client
    assert second_client is client
    create_client.assert_called_once_with(
        "https://example.supabase.co",
        "fake-service-role-key",
    )


def test_get_supabase_client_reports_initialization_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(supabase_service, "get_settings", lambda: _settings())
    monkeypatch.setattr(
        supabase_service,
        "create_client",
        Mock(side_effect=ValueError("connection failed")),
    )

    with pytest.raises(SupabaseConnectionError) as exc_info:
        supabase_service.get_supabase_client()

    message = str(exc_info.value)
    assert "client initialization" in message
    assert "ValueError" in message


def test_check_supabase_connection_returns_database_and_storage_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    query = Mock()
    query.select.return_value = query
    query.limit.return_value = query
    query.execute.return_value = SimpleNamespace(data=[])

    client = SimpleNamespace(
        table=Mock(return_value=query),
        storage=SimpleNamespace(
            list_buckets=Mock(return_value=[{"name": "documents"}])
        ),
    )
    monkeypatch.setattr(supabase_service, "get_settings", lambda: _settings())
    monkeypatch.setattr(supabase_service, "get_supabase_client", lambda: client)

    result = supabase_service.check_supabase_connection()

    assert result == {"database": True, "storage": True}
    client.table.assert_called_once_with("documents")
    query.select.assert_called_once_with("id")
    query.limit.assert_called_once_with(1)
    query.execute.assert_called_once_with()
    client.storage.list_buckets.assert_called_once_with()


def test_check_supabase_connection_reports_database_query_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    query = Mock()
    query.select.return_value = query
    query.limit.return_value = query
    query.execute.side_effect = RuntimeError("query failed")

    client = SimpleNamespace(
        table=Mock(return_value=query),
        storage=SimpleNamespace(list_buckets=Mock(return_value=[])),
    )
    monkeypatch.setattr(supabase_service, "get_settings", lambda: _settings())
    monkeypatch.setattr(supabase_service, "get_supabase_client", lambda: client)

    with pytest.raises(SupabaseConnectionError) as exc_info:
        supabase_service.check_supabase_connection()

    message = str(exc_info.value)
    assert "documents connectivity check" in message
    assert "RuntimeError" in message
    client.storage.list_buckets.assert_not_called()


def test_check_supabase_connection_reports_storage_list_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    query = Mock()
    query.select.return_value = query
    query.limit.return_value = query

    client = SimpleNamespace(
        table=Mock(return_value=query),
        storage=SimpleNamespace(
            list_buckets=Mock(side_effect=LookupError("storage failed"))
        ),
    )
    monkeypatch.setattr(supabase_service, "get_settings", lambda: _settings())
    monkeypatch.setattr(supabase_service, "get_supabase_client", lambda: client)

    with pytest.raises(SupabaseConnectionError) as exc_info:
        supabase_service.check_supabase_connection()

    message = str(exc_info.value)
    assert "storage bucket connectivity check" in message
    assert "LookupError" in message


def test_check_supabase_connection_reports_missing_storage_bucket(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    query = Mock()
    query.select.return_value = query
    query.limit.return_value = query

    client = SimpleNamespace(
        table=Mock(return_value=query),
        storage=SimpleNamespace(
            list_buckets=Mock(
                return_value=[
                    SimpleNamespace(id="other-bucket", name="other-bucket")
                ]
            )
        ),
    )
    monkeypatch.setattr(supabase_service, "get_settings", lambda: _settings())
    monkeypatch.setattr(supabase_service, "get_supabase_client", lambda: client)

    with pytest.raises(SupabaseConnectionError) as exc_info:
        supabase_service.check_supabase_connection()

    message = str(exc_info.value)
    assert "storage setup failure" in message
    assert "documents" in message


def test_upload_document_file_uses_configured_storage_bucket(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bucket = SimpleNamespace(upload=Mock(return_value={"path": "stored"}))
    storage = SimpleNamespace(from_=Mock(return_value=bucket))
    client = SimpleNamespace(storage=storage)
    monkeypatch.setattr(
        supabase_service,
        "get_settings",
        lambda: _settings(storage_bucket="private-documents"),
    )
    monkeypatch.setattr(supabase_service, "get_supabase_client", lambda: client)

    result = supabase_service.upload_document_file(
        "documents/single_user/document-id/file.txt",
        b"hello",
        content_type="text/plain",
    )

    assert result == "documents/single_user/document-id/file.txt"
    storage.from_.assert_called_once_with("private-documents")
    bucket.upload.assert_called_once_with(
        "documents/single_user/document-id/file.txt",
        b"hello",
        {"content-type": "text/plain", "upsert": "false"},
    )


def test_upload_document_file_reports_storage_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bucket = SimpleNamespace(upload=Mock(side_effect=RuntimeError("secret failure")))
    client = SimpleNamespace(storage=SimpleNamespace(from_=Mock(return_value=bucket)))
    monkeypatch.setattr(supabase_service, "get_settings", lambda: _settings())
    monkeypatch.setattr(supabase_service, "get_supabase_client", lambda: client)

    with pytest.raises(SupabaseConnectionError) as exc_info:
        supabase_service.upload_document_file("documents/user/doc/file.txt", b"hello")

    message = str(exc_info.value)
    assert "storage upload" in message
    assert "RuntimeError" in message
    assert "secret failure" not in message


def test_insert_document_metadata_returns_created_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    row = {
        "user_id": "single_user",
        "file_name": "file.txt",
        "file_type": "txt",
        "storage_path": "documents/single_user/document-id/file.txt",
        "status": "uploaded",
        "chunk_count": 0,
        "error_message": None,
    }
    query = Mock()
    query.insert.return_value = query
    query.execute.return_value = SimpleNamespace(data=[{"id": "document-id", **row}])
    client = SimpleNamespace(table=Mock(return_value=query))
    monkeypatch.setattr(supabase_service, "get_supabase_client", lambda: client)

    result = supabase_service.insert_document_metadata(row)

    assert result == {"id": "document-id", **row}
    client.table.assert_called_once_with("documents")
    query.insert.assert_called_once_with(row)
    query.execute.assert_called_once_with()


def test_insert_document_metadata_reports_empty_insert_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    query = Mock()
    query.insert.return_value = query
    query.execute.return_value = SimpleNamespace(data=[])
    client = SimpleNamespace(table=Mock(return_value=query))
    monkeypatch.setattr(supabase_service, "get_supabase_client", lambda: client)

    with pytest.raises(SupabaseConnectionError) as exc_info:
        supabase_service.insert_document_metadata({"file_name": "file.txt"})

    assert "document metadata insert" in str(exc_info.value)


def test_insert_agent_step_log_inserts_required_row_shape(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inserted_row = {
        "id": "step-id",
        "agent_run_id": "11111111-1111-1111-1111-111111111111",
        "step_name": "agent_1_retrieval",
        "agent_name": "retrieval_agent",
        "input": {"question": "When can I start?"},
        "output": {"candidates": []},
        "status": "success",
        "error_message": None,
    }
    query = Mock()
    query.insert.return_value = query
    query.execute.return_value = SimpleNamespace(data=[inserted_row])
    client = SimpleNamespace(table=Mock(return_value=query))
    monkeypatch.setattr(supabase_service, "get_supabase_client", lambda: client)

    result = supabase_service.insert_agent_step_log(
        agent_run_id="11111111-1111-1111-1111-111111111111",
        step_name="agent_1_retrieval",
        agent_name="retrieval_agent",
        input_payload={"question": "When can I start?"},
        output_payload={"candidates": []},
        status="success",
        error_message=None,
    )

    assert result == inserted_row
    client.table.assert_called_once_with("agent_steps")
    query.insert.assert_called_once_with(
        {
            "agent_run_id": "11111111-1111-1111-1111-111111111111",
            "step_name": "agent_1_retrieval",
            "agent_name": "retrieval_agent",
            "input": {"question": "When can I start?"},
            "output": {"candidates": []},
            "status": "success",
            "error_message": None,
        }
    )
    query.execute.assert_called_once_with()


def test_insert_agent_step_log_reports_safe_insert_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    query = Mock()
    query.insert.return_value = query
    query.execute.side_effect = RuntimeError("database secret")
    client = SimpleNamespace(table=Mock(return_value=query))
    monkeypatch.setattr(supabase_service, "get_supabase_client", lambda: client)

    with pytest.raises(SupabaseConnectionError) as exc_info:
        supabase_service.insert_agent_step_log(
            agent_run_id="11111111-1111-1111-1111-111111111111",
            step_name="agent_1_retrieval",
            agent_name="retrieval_agent",
            input_payload={"question": "When can I start?"},
            output_payload={},
            status="failed",
            error_message="Safe error",
        )

    message = str(exc_info.value)
    assert "agent step log insert" in message
    assert "RuntimeError" in message
    assert "database secret" not in message


def test_create_chat_session_inserts_single_user_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    row = {
        "id": "session-id",
        "user_id": "single_user",
        "title": "Benefits Q&A",
    }
    query = Mock()
    query.insert.return_value = query
    query.execute.return_value = SimpleNamespace(data=[row])
    client = SimpleNamespace(table=Mock(return_value=query))
    monkeypatch.setattr(supabase_service, "get_settings", lambda: _settings())
    monkeypatch.setattr(supabase_service, "get_supabase_client", lambda: client)

    result = supabase_service.create_chat_session(title="Benefits Q&A")

    assert result == row
    client.table.assert_called_once_with("chat_sessions")
    query.insert.assert_called_once_with(
        {
            "user_id": "single_user",
            "title": "Benefits Q&A",
        }
    )
    query.execute.assert_called_once_with()


def test_get_chat_session_filters_single_user_and_session_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    row = {"id": "session-id", "user_id": "single_user", "title": "New chat"}
    query = Mock()
    query.select.return_value = query
    query.eq.return_value = query
    query.limit.return_value = query
    query.execute.return_value = SimpleNamespace(data=[row])
    client = SimpleNamespace(table=Mock(return_value=query))
    monkeypatch.setattr(supabase_service, "get_settings", lambda: _settings())
    monkeypatch.setattr(supabase_service, "get_supabase_client", lambda: client)

    result = supabase_service.get_chat_session("session-id")

    assert result == row
    client.table.assert_called_once_with("chat_sessions")
    query.select.assert_called_once_with("*")
    assert query.eq.call_args_list == [
        (("id", "session-id"),),
        (("user_id", "single_user"),),
    ]
    query.limit.assert_called_once_with(1)
    query.execute.assert_called_once_with()


def test_get_chat_session_returns_none_when_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    query = Mock()
    query.select.return_value = query
    query.eq.return_value = query
    query.limit.return_value = query
    query.execute.return_value = SimpleNamespace(data=[])
    client = SimpleNamespace(table=Mock(return_value=query))
    monkeypatch.setattr(supabase_service, "get_settings", lambda: _settings())
    monkeypatch.setattr(supabase_service, "get_supabase_client", lambda: client)

    assert supabase_service.get_chat_session("missing-session-id") is None


def test_get_or_create_chat_session_creates_when_session_id_is_omitted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    create_chat_session = Mock(return_value={"id": "new-session-id"})
    get_chat_session = Mock()
    monkeypatch.setattr(supabase_service, "create_chat_session", create_chat_session)
    monkeypatch.setattr(supabase_service, "get_chat_session", get_chat_session)

    result = supabase_service.get_or_create_chat_session(title="Question")

    assert result == {"id": "new-session-id"}
    create_chat_session.assert_called_once_with(title="Question")
    get_chat_session.assert_not_called()


def test_get_or_create_chat_session_fetches_when_session_id_is_present(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    create_chat_session = Mock()
    get_chat_session = Mock(return_value={"id": "existing-session-id"})
    monkeypatch.setattr(supabase_service, "create_chat_session", create_chat_session)
    monkeypatch.setattr(supabase_service, "get_chat_session", get_chat_session)

    result = supabase_service.get_or_create_chat_session("existing-session-id")

    assert result == {"id": "existing-session-id"}
    get_chat_session.assert_called_once_with("existing-session-id")
    create_chat_session.assert_not_called()


def test_list_chat_sessions_filters_single_user_and_orders_updated_desc(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows = [{"id": "session-id", "user_id": "single_user"}]
    query = Mock()
    query.select.return_value = query
    query.eq.return_value = query
    query.order.return_value = query
    query.execute.return_value = SimpleNamespace(data=rows)
    client = SimpleNamespace(table=Mock(return_value=query))
    monkeypatch.setattr(supabase_service, "get_settings", lambda: _settings())
    monkeypatch.setattr(supabase_service, "get_supabase_client", lambda: client)

    result = supabase_service.list_chat_sessions()

    assert result == rows
    client.table.assert_called_once_with("chat_sessions")
    query.select.assert_called_once_with("*")
    query.eq.assert_called_once_with("user_id", "single_user")
    query.order.assert_called_once_with("updated_at", desc=True)
    query.execute.assert_called_once_with()


def test_insert_chat_message_inserts_single_user_row_with_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    row = {
        "id": "message-id",
        "session_id": "session-id",
        "user_id": "single_user",
        "role": "assistant",
        "content": "Answer",
        "metadata": {"agent_run_id": "run-id"},
    }
    query = Mock()
    query.insert.return_value = query
    query.execute.return_value = SimpleNamespace(data=[row])
    client = SimpleNamespace(table=Mock(return_value=query))
    monkeypatch.setattr(supabase_service, "get_settings", lambda: _settings())
    monkeypatch.setattr(supabase_service, "get_supabase_client", lambda: client)

    result = supabase_service.insert_chat_message(
        session_id="session-id",
        role="assistant",
        content="Answer",
        metadata={"agent_run_id": "run-id"},
    )

    assert result == row
    client.table.assert_called_once_with("chat_messages")
    query.insert.assert_called_once_with(
        {
            "session_id": "session-id",
            "user_id": "single_user",
            "role": "assistant",
            "content": "Answer",
            "metadata": {"agent_run_id": "run-id"},
        }
    )
    query.execute.assert_called_once_with()


def test_insert_user_chat_message_for_documents_uses_lock_aware_rpc(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    row = {
        "id": "message-id",
        "session_id": "session-id",
        "user_id": "single_user",
        "role": "user",
        "content": "Question?",
        "metadata": {"document_ids": ["document-id"]},
    }
    rpc_query = Mock()
    rpc_query.execute.return_value = SimpleNamespace(data=[row])
    client = SimpleNamespace(rpc=Mock(return_value=rpc_query))
    monkeypatch.setattr(supabase_service, "get_settings", lambda: _settings())
    monkeypatch.setattr(supabase_service, "get_supabase_client", lambda: client)

    result = supabase_service.insert_user_chat_message_for_documents(
        session_id="session-id",
        content="Question?",
        document_ids=["document-id"],
    )

    assert result == row
    client.rpc.assert_called_once_with(
        "insert_user_chat_message_for_documents",
        {
            "p_session_id": "session-id",
            "p_user_id": "single_user",
            "p_content": "Question?",
            "p_document_ids": ["document-id"],
        },
    )
    rpc_query.execute.assert_called_once_with()


def test_insert_chat_message_defaults_metadata_to_empty_object(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    query = Mock()
    query.insert.return_value = query
    query.execute.return_value = SimpleNamespace(data=[{"id": "message-id"}])
    client = SimpleNamespace(table=Mock(return_value=query))
    monkeypatch.setattr(supabase_service, "get_settings", lambda: _settings())
    monkeypatch.setattr(supabase_service, "get_supabase_client", lambda: client)

    supabase_service.insert_chat_message(
        session_id="session-id",
        role="user",
        content="Question?",
    )

    assert query.insert.call_args.args[0]["metadata"] == {}


def test_insert_chat_message_reports_safe_insert_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    query = Mock()
    query.insert.return_value = query
    query.execute.side_effect = RuntimeError("database secret")
    client = SimpleNamespace(table=Mock(return_value=query))
    monkeypatch.setattr(supabase_service, "get_settings", lambda: _settings())
    monkeypatch.setattr(supabase_service, "get_supabase_client", lambda: client)

    with pytest.raises(SupabaseConnectionError) as exc_info:
        supabase_service.insert_chat_message(
            session_id="session-id",
            role="user",
            content="Question?",
        )

    message = str(exc_info.value)
    assert "chat message insert" in message
    assert "RuntimeError" in message
    assert "database secret" not in message


def test_create_agent_run_inserts_running_single_user_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    row = {
        "id": "run-id",
        "session_id": "session-id",
        "user_id": "single_user",
        "question": "When can I start?",
        "selected_document_ids": ["document-id"],
        "status": "running",
    }
    rpc_query = Mock()
    rpc_query.execute.return_value = SimpleNamespace(data=[row])
    client = SimpleNamespace(rpc=Mock(return_value=rpc_query))
    monkeypatch.setattr(supabase_service, "get_settings", lambda: _settings())
    monkeypatch.setattr(supabase_service, "get_supabase_client", lambda: client)

    result = supabase_service.create_agent_run(
        session_id="session-id",
        question="When can I start?",
        selected_document_ids=["document-id"],
    )

    assert result == row
    client.rpc.assert_called_once_with(
        "create_owned_agent_run",
        {
            "p_session_id": "session-id",
            "p_user_id": "single_user",
            "p_question": "When can I start?",
            "p_selected_document_ids": ["document-id"],
        },
    )
    rpc_query.execute.assert_called_once_with()


def test_create_agent_run_allows_omitted_session_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rpc_query = Mock()
    rpc_query.execute.return_value = SimpleNamespace(data=[{"id": "run-id"}])
    client = SimpleNamespace(rpc=Mock(return_value=rpc_query))
    monkeypatch.setattr(supabase_service, "get_settings", lambda: _settings())
    monkeypatch.setattr(supabase_service, "get_supabase_client", lambda: client)

    supabase_service.create_agent_run(
        session_id=None,
        question="Question?",
        selected_document_ids=["document-id"],
    )

    client.rpc.assert_called_once_with(
        "create_owned_agent_run",
        {
            "p_session_id": None,
            "p_user_id": "single_user",
            "p_question": "Question?",
            "p_selected_document_ids": ["document-id"],
        },
    )
    rpc_query.execute.assert_called_once_with()


def test_update_agent_run_success_filters_single_user_and_run_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    row = {
        "id": "run-id",
        "user_id": "single_user",
        "status": "success",
        "final_answer": "Final answer",
        "confidence": 0.82,
        "error_message": None,
    }
    query = Mock()
    query.update.return_value = query
    query.eq.return_value = query
    query.execute.return_value = SimpleNamespace(data=[row])
    client = SimpleNamespace(table=Mock(return_value=query))
    monkeypatch.setattr(supabase_service, "get_settings", lambda: _settings())
    monkeypatch.setattr(supabase_service, "get_supabase_client", lambda: client)

    result = supabase_service.update_agent_run_success(
        "run-id",
        final_answer="Final answer",
        confidence=0.82,
    )

    assert result == row
    client.table.assert_called_once_with("agent_runs")
    query.update.assert_called_once_with(
        {
            "status": "success",
            "final_answer": "Final answer",
            "confidence": 0.82,
            "error_message": None,
        }
    )
    assert query.eq.call_args_list == [
        (("id", "run-id"),),
        (("user_id", "single_user"),),
    ]
    query.execute.assert_called_once_with()


def test_update_agent_run_failure_filters_single_user_and_run_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    row = {
        "id": "run-id",
        "user_id": "single_user",
        "status": "failed",
        "error_message": "Agent 2 failed.",
    }
    query = Mock()
    query.update.return_value = query
    query.eq.return_value = query
    query.execute.return_value = SimpleNamespace(data=[row])
    client = SimpleNamespace(table=Mock(return_value=query))
    monkeypatch.setattr(supabase_service, "get_settings", lambda: _settings())
    monkeypatch.setattr(supabase_service, "get_supabase_client", lambda: client)

    result = supabase_service.update_agent_run_failure(
        "run-id",
        error_message="Agent 2 failed.",
    )

    assert result == row
    query.update.assert_called_once_with(
        {
            "status": "failed",
            "final_answer": None,
            "confidence": None,
            "error_message": "Agent 2 failed.",
        }
    )
    assert query.eq.call_args_list == [
        (("id", "run-id"),),
        (("user_id", "single_user"),),
    ]


def test_get_agent_run_filters_single_user_and_run_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    row = {"id": "run-id", "user_id": "single_user", "status": "running"}
    query = Mock()
    query.select.return_value = query
    query.eq.return_value = query
    query.limit.return_value = query
    query.execute.return_value = SimpleNamespace(data=[row])
    client = SimpleNamespace(table=Mock(return_value=query))
    monkeypatch.setattr(supabase_service, "get_settings", lambda: _settings())
    monkeypatch.setattr(supabase_service, "get_supabase_client", lambda: client)

    result = supabase_service.get_agent_run("run-id")

    assert result == row
    client.table.assert_called_once_with("agent_runs")
    query.select.assert_called_once_with("*")
    assert query.eq.call_args_list == [
        (("id", "run-id"),),
        (("user_id", "single_user"),),
    ]
    query.limit.assert_called_once_with(1)
    query.execute.assert_called_once_with()


def test_get_agent_run_returns_none_when_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    query = Mock()
    query.select.return_value = query
    query.eq.return_value = query
    query.limit.return_value = query
    query.execute.return_value = SimpleNamespace(data=[])
    client = SimpleNamespace(table=Mock(return_value=query))
    monkeypatch.setattr(supabase_service, "get_settings", lambda: _settings())
    monkeypatch.setattr(supabase_service, "get_supabase_client", lambda: client)

    assert supabase_service.get_agent_run("missing-run-id") is None


def test_list_agent_steps_for_run_checks_owned_run_and_orders_by_created_at(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_query = Mock()
    run_query.select.return_value = run_query
    run_query.eq.return_value = run_query
    run_query.limit.return_value = run_query
    run_query.execute.return_value = SimpleNamespace(
        data=[{"id": "run-id", "user_id": "single_user"}]
    )
    steps = [
        {
            "id": "step-1",
            "agent_run_id": "run-id",
            "created_at": "2026-01-01T00:00:00Z",
        }
    ]
    step_query = Mock()
    step_query.select.return_value = step_query
    step_query.eq.return_value = step_query
    step_query.order.return_value = step_query
    step_query.execute.return_value = SimpleNamespace(data=steps)
    client = SimpleNamespace(table=Mock(side_effect=[run_query, step_query]))
    monkeypatch.setattr(supabase_service, "get_settings", lambda: _settings())
    monkeypatch.setattr(supabase_service, "get_supabase_client", lambda: client)

    result = supabase_service.list_agent_steps_for_run("run-id")

    assert result == steps
    assert client.table.call_args_list == [
        (("agent_runs",),),
        (("agent_steps",),),
    ]
    assert run_query.eq.call_args_list == [
        (("id", "run-id"),),
        (("user_id", "single_user"),),
    ]
    step_query.select.assert_called_once_with("*")
    step_query.eq.assert_called_once_with("agent_run_id", "run-id")
    step_query.order.assert_called_once_with("created_at")
    step_query.execute.assert_called_once_with()


def test_list_agent_steps_for_run_returns_empty_for_unowned_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_query = Mock()
    run_query.select.return_value = run_query
    run_query.eq.return_value = run_query
    run_query.limit.return_value = run_query
    run_query.execute.return_value = SimpleNamespace(data=[])
    client = SimpleNamespace(table=Mock(return_value=run_query))
    monkeypatch.setattr(supabase_service, "get_settings", lambda: _settings())
    monkeypatch.setattr(supabase_service, "get_supabase_client", lambda: client)

    result = supabase_service.list_agent_steps_for_run("run-id")

    assert result == []
    client.table.assert_called_once_with("agent_runs")


def test_agent_run_helpers_report_safe_query_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    query = Mock()
    query.update.return_value = query
    query.eq.return_value = query
    query.execute.side_effect = RuntimeError("database secret")
    client = SimpleNamespace(table=Mock(return_value=query))
    monkeypatch.setattr(supabase_service, "get_settings", lambda: _settings())
    monkeypatch.setattr(supabase_service, "get_supabase_client", lambda: client)

    with pytest.raises(SupabaseConnectionError) as exc_info:
        supabase_service.update_agent_run_failure(
            "run-id",
            error_message="Safe failure.",
        )

    message = str(exc_info.value)
    assert "agent run failure update" in message
    assert "RuntimeError" in message
    assert "database secret" not in message


def test_list_document_metadata_filters_user_and_orders_created_desc(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows = [{"id": "document-id", "user_id": "single_user"}]
    query = Mock()
    query.select.return_value = query
    query.eq.return_value = query
    query.order.return_value = query
    query.execute.return_value = SimpleNamespace(data=rows)
    client = SimpleNamespace(table=Mock(return_value=query))
    monkeypatch.setattr(supabase_service, "get_supabase_client", lambda: client)

    result = supabase_service.list_document_metadata("single_user")

    assert result == rows
    client.table.assert_called_once_with("documents")
    query.select.assert_called_once_with("*")
    query.eq.assert_called_once_with("user_id", "single_user")
    query.order.assert_called_once_with("created_at", desc=True)
    query.execute.assert_called_once_with()


def test_get_document_metadata_filters_user_and_document_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    row = {"id": "document-id", "user_id": "single_user"}
    query = Mock()
    query.select.return_value = query
    query.eq.return_value = query
    query.limit.return_value = query
    query.execute.return_value = SimpleNamespace(data=[row])
    client = SimpleNamespace(table=Mock(return_value=query))
    monkeypatch.setattr(supabase_service, "get_supabase_client", lambda: client)

    result = supabase_service.get_document_metadata("document-id", "single_user")

    assert result == row
    client.table.assert_called_once_with("documents")
    query.select.assert_called_once_with("*")
    assert query.eq.call_args_list == [
        (("id", "document-id"),),
        (("user_id", "single_user"),),
    ]
    query.limit.assert_called_once_with(1)
    query.execute.assert_called_once_with()


def test_get_document_metadata_returns_none_when_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    query = Mock()
    query.select.return_value = query
    query.eq.return_value = query
    query.limit.return_value = query
    query.execute.return_value = SimpleNamespace(data=[])
    client = SimpleNamespace(table=Mock(return_value=query))
    monkeypatch.setattr(supabase_service, "get_supabase_client", lambda: client)

    assert supabase_service.get_document_metadata("document-id", "single_user") is None


def test_list_owned_document_metadata_by_ids_filters_single_user_and_selected_ids(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows = [{"id": "document-id", "user_id": "single_user"}]
    query = Mock()
    query.select.return_value = query
    query.eq.return_value = query
    query.in_.return_value = query
    query.execute.return_value = SimpleNamespace(data=rows)
    client = SimpleNamespace(table=Mock(return_value=query))
    monkeypatch.setattr(supabase_service, "get_settings", lambda: _settings())
    monkeypatch.setattr(supabase_service, "get_supabase_client", lambda: client)

    result = supabase_service.list_owned_document_metadata_by_ids(
        ["document-id", "other-document-id"]
    )

    assert result == rows
    client.table.assert_called_once_with("documents")
    query.select.assert_called_once_with("*")
    query.eq.assert_called_once_with("user_id", "single_user")
    query.in_.assert_called_once_with("id", ["document-id", "other-document-id"])
    query.execute.assert_called_once_with()


def test_get_processing_document_uses_configured_single_user(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    get_document_metadata = Mock(return_value={"id": "document-id"})
    monkeypatch.setattr(supabase_service, "get_settings", lambda: _settings())
    monkeypatch.setattr(
        supabase_service,
        "get_document_metadata",
        get_document_metadata,
    )

    result = supabase_service.get_processing_document("document-id")

    assert result == {"id": "document-id"}
    get_document_metadata.assert_called_once_with("document-id", "single_user")


def test_get_indexing_document_uses_configured_single_user(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    get_document_metadata = Mock(return_value={"id": "document-id"})
    monkeypatch.setattr(supabase_service, "get_settings", lambda: _settings())
    monkeypatch.setattr(
        supabase_service,
        "get_document_metadata",
        get_document_metadata,
    )

    result = supabase_service.get_indexing_document("document-id")

    assert result == {"id": "document-id"}
    get_document_metadata.assert_called_once_with("document-id", "single_user")


def test_download_original_document_file_uses_configured_storage_bucket(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bucket = SimpleNamespace(download=Mock(return_value=b"file bytes"))
    storage = SimpleNamespace(from_=Mock(return_value=bucket))
    client = SimpleNamespace(storage=storage)
    monkeypatch.setattr(
        supabase_service,
        "get_settings",
        lambda: _settings(storage_bucket="private-documents"),
    )
    monkeypatch.setattr(supabase_service, "get_supabase_client", lambda: client)

    result = supabase_service.download_original_document_file(
        "documents/single_user/document-id/file.txt"
    )

    assert result == b"file bytes"
    storage.from_.assert_called_once_with("private-documents")
    bucket.download.assert_called_once_with("documents/single_user/document-id/file.txt")


def test_download_original_document_file_reports_safe_storage_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bucket = SimpleNamespace(download=Mock(side_effect=LookupError("missing object")))
    client = SimpleNamespace(storage=SimpleNamespace(from_=Mock(return_value=bucket)))
    monkeypatch.setattr(supabase_service, "get_settings", lambda: _settings())
    monkeypatch.setattr(supabase_service, "get_supabase_client", lambda: client)

    with pytest.raises(SupabaseConnectionError) as exc_info:
        supabase_service.download_original_document_file(
            "documents/single_user/document-id/file.txt"
        )

    message = str(exc_info.value)
    assert "storage download" in message
    assert "LookupError" in message
    assert "missing object" not in message


def test_insert_document_chunks_inserts_single_user_rows_with_null_qdrant_point(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chunks = [
        ChunkDraft(
            content="First chunk",
            chunk_index=0,
            token_count=2,
            page_number=1,
            section_title="Intro",
        ),
        ChunkDraft(
            content="Second chunk",
            chunk_index=1,
            token_count=2,
            page_number=None,
            section_title=None,
        ),
    ]
    inserted_rows = [{"id": "chunk-1"}, {"id": "chunk-2"}]
    query = Mock()
    query.insert.return_value = query
    query.execute.return_value = SimpleNamespace(data=inserted_rows)
    client = SimpleNamespace(table=Mock(return_value=query))
    monkeypatch.setattr(supabase_service, "get_settings", lambda: _settings())
    monkeypatch.setattr(supabase_service, "get_supabase_client", lambda: client)

    result = supabase_service.insert_document_chunks("document-id", chunks)

    assert result == inserted_rows
    client.table.assert_called_once_with("document_chunks")
    query.insert.assert_called_once_with(
        [
            {
                "document_id": "document-id",
                "user_id": "single_user",
                "chunk_index": 0,
                "content": "First chunk",
                "page_number": 1,
                "section_title": "Intro",
                "token_count": 2,
                "qdrant_point_id": None,
            },
            {
                "document_id": "document-id",
                "user_id": "single_user",
                "chunk_index": 1,
                "content": "Second chunk",
                "page_number": None,
                "section_title": None,
                "token_count": 2,
                "qdrant_point_id": None,
            },
        ]
    )
    query.execute.assert_called_once_with()


def test_insert_document_chunks_skips_empty_input(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = SimpleNamespace(table=Mock())
    monkeypatch.setattr(supabase_service, "get_supabase_client", lambda: client)

    result = supabase_service.insert_document_chunks("document-id", [])

    assert result == []
    client.table.assert_not_called()


def test_insert_document_chunks_reports_safe_insert_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    query = Mock()
    query.insert.return_value = query
    query.execute.side_effect = RuntimeError("database secret")
    client = SimpleNamespace(table=Mock(return_value=query))
    monkeypatch.setattr(supabase_service, "get_settings", lambda: _settings())
    monkeypatch.setattr(supabase_service, "get_supabase_client", lambda: client)

    with pytest.raises(SupabaseConnectionError) as exc_info:
        supabase_service.insert_document_chunks(
            "document-id",
            [ChunkDraft(content="Chunk", chunk_index=0, token_count=1)],
        )

    message = str(exc_info.value)
    assert "document chunk insert" in message
    assert "RuntimeError" in message
    assert "database secret" not in message


def test_list_chunks_needing_indexing_filters_single_user_and_null_point_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows = [
        {
            "id": "chunk-1",
            "document_id": "document-id",
            "user_id": "single_user",
            "chunk_index": 0,
            "content": "Chunk text",
            "page_number": 1,
            "section_title": "Intro",
            "token_count": 2,
            "qdrant_point_id": None,
        }
    ]
    query = Mock()
    query.select.return_value = query
    query.eq.return_value = query
    query.is_.return_value = query
    query.order.return_value = query
    query.execute.return_value = SimpleNamespace(data=rows)
    client = SimpleNamespace(table=Mock(return_value=query))
    monkeypatch.setattr(supabase_service, "get_settings", lambda: _settings())
    monkeypatch.setattr(supabase_service, "get_supabase_client", lambda: client)

    result = supabase_service.list_chunks_needing_indexing("document-id")

    assert result == rows
    client.table.assert_called_once_with("document_chunks")
    query.select.assert_called_once_with(
        "id, document_id, user_id, chunk_index, content, page_number, "
        "section_title, token_count, qdrant_point_id"
    )
    assert query.eq.call_args_list == [
        (("document_id", "document-id"),),
        (("user_id", "single_user"),),
    ]
    query.is_.assert_called_once_with("qdrant_point_id", "null")
    query.order.assert_called_once_with("chunk_index")
    query.execute.assert_called_once_with()


def test_list_chunks_needing_indexing_reports_safe_query_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    query = Mock()
    query.select.return_value = query
    query.eq.return_value = query
    query.is_.return_value = query
    query.order.return_value = query
    query.execute.side_effect = RuntimeError("database secret")
    client = SimpleNamespace(table=Mock(return_value=query))
    monkeypatch.setattr(supabase_service, "get_settings", lambda: _settings())
    monkeypatch.setattr(supabase_service, "get_supabase_client", lambda: client)

    with pytest.raises(SupabaseConnectionError) as exc_info:
        supabase_service.list_chunks_needing_indexing("document-id")

    message = str(exc_info.value)
    assert "document chunks indexing list" in message
    assert "RuntimeError" in message
    assert "database secret" not in message


def test_update_chunk_qdrant_point_id_filters_intended_chunk_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    row = {"id": "chunk-1", "qdrant_point_id": "point-1"}
    query = Mock()
    query.update.return_value = query
    query.eq.return_value = query
    query.execute.return_value = SimpleNamespace(data=[row])
    client = SimpleNamespace(table=Mock(return_value=query))
    monkeypatch.setattr(supabase_service, "get_settings", lambda: _settings())
    monkeypatch.setattr(supabase_service, "get_supabase_client", lambda: client)

    result = supabase_service.update_chunk_qdrant_point_id(
        "document-id",
        "chunk-1",
        "point-1",
    )

    assert result == row
    client.table.assert_called_once_with("document_chunks")
    query.update.assert_called_once_with({"qdrant_point_id": "point-1"})
    assert query.eq.call_args_list == [
        (("id", "chunk-1"),),
        (("document_id", "document-id"),),
        (("user_id", "single_user"),),
    ]
    query.execute.assert_called_once_with()


def test_update_chunk_qdrant_point_id_reports_safe_update_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    query = Mock()
    query.update.return_value = query
    query.eq.return_value = query
    query.execute.side_effect = RuntimeError("database secret")
    client = SimpleNamespace(table=Mock(return_value=query))
    monkeypatch.setattr(supabase_service, "get_settings", lambda: _settings())
    monkeypatch.setattr(supabase_service, "get_supabase_client", lambda: client)

    with pytest.raises(SupabaseConnectionError) as exc_info:
        supabase_service.update_chunk_qdrant_point_id(
            "document-id",
            "chunk-1",
            "point-1",
        )

    message = str(exc_info.value)
    assert "document chunk qdrant point update" in message
    assert "RuntimeError" in message
    assert "database secret" not in message


def test_update_document_status_filters_user_and_updates_error_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    row = {"id": "document-id", "status": "failed", "error_message": "Safe error"}
    query = Mock()
    query.update.return_value = query
    query.eq.return_value = query
    query.execute.return_value = SimpleNamespace(data=[row])
    client = SimpleNamespace(table=Mock(return_value=query))
    monkeypatch.setattr(supabase_service, "get_settings", lambda: _settings())
    monkeypatch.setattr(supabase_service, "get_supabase_client", lambda: client)

    result = supabase_service.update_document_status(
        "document-id",
        "failed",
        error_message="Safe error",
    )

    assert result == row
    client.table.assert_called_once_with("documents")
    query.update.assert_called_once_with(
        {"status": "failed", "error_message": "Safe error"}
    )
    assert query.eq.call_args_list == [
        (("id", "document-id"),),
        (("user_id", "single_user"),),
    ]
    query.execute.assert_called_once_with()


def test_update_document_chunk_count_filters_user(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    row = {"id": "document-id", "chunk_count": 3}
    query = Mock()
    query.update.return_value = query
    query.eq.return_value = query
    query.execute.return_value = SimpleNamespace(data=[row])
    client = SimpleNamespace(table=Mock(return_value=query))
    monkeypatch.setattr(supabase_service, "get_settings", lambda: _settings())
    monkeypatch.setattr(supabase_service, "get_supabase_client", lambda: client)

    result = supabase_service.update_document_chunk_count("document-id", 3)

    assert result == row
    client.table.assert_called_once_with("documents")
    query.update.assert_called_once_with({"chunk_count": 3})
    assert query.eq.call_args_list == [
        (("id", "document-id"),),
        (("user_id", "single_user"),),
    ]
    query.execute.assert_called_once_with()


def test_get_graph_document_loads_single_user_document(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document = {"id": "document-id", "user_id": "single_user"}
    monkeypatch.setattr(supabase_service, "get_settings", lambda: _settings())
    get_document_metadata = Mock(return_value=document)
    monkeypatch.setattr(
        supabase_service,
        "get_document_metadata",
        get_document_metadata,
    )

    result = supabase_service.get_graph_document("document-id")

    assert result == document
    get_document_metadata.assert_called_once_with("document-id", "single_user")


def test_list_document_chunks_filters_single_user_and_orders_by_index(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows = [{"id": "chunk-1", "document_id": "document-id"}]
    query = Mock()
    query.select.return_value = query
    query.eq.return_value = query
    query.order.return_value = query
    query.execute.return_value = SimpleNamespace(data=rows)
    client = SimpleNamespace(table=Mock(return_value=query))
    monkeypatch.setattr(supabase_service, "get_settings", lambda: _settings())
    monkeypatch.setattr(supabase_service, "get_supabase_client", lambda: client)

    result = supabase_service.list_document_chunks("document-id")

    assert result == rows
    client.table.assert_called_once_with("document_chunks")
    query.select.assert_called_once_with(
        "id, document_id, user_id, chunk_index, content, page_number, "
        "section_title, token_count, qdrant_point_id"
    )
    assert query.eq.call_args_list == [
        (("document_id", "document-id"),),
        (("user_id", "single_user"),),
    ]
    query.order.assert_called_once_with("chunk_index")
    query.execute.assert_called_once_with()


def test_clear_document_graph_rows_deletes_relationships_before_entities(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    relationship_query = Mock()
    relationship_query.delete.return_value = relationship_query
    relationship_query.eq.return_value = relationship_query
    relationship_query.execute.return_value = SimpleNamespace(data=[])
    entity_query = Mock()
    entity_query.delete.return_value = entity_query
    entity_query.eq.return_value = entity_query
    entity_query.execute.return_value = SimpleNamespace(data=[])
    client = SimpleNamespace(
        table=Mock(side_effect=[relationship_query, entity_query])
    )
    monkeypatch.setattr(supabase_service, "get_settings", lambda: _settings())
    monkeypatch.setattr(supabase_service, "get_supabase_client", lambda: client)

    supabase_service.clear_document_graph_rows("document-id")

    assert client.table.call_args_list == [
        (("document_relationships",),),
        (("document_entities",),),
    ]
    relationship_query.delete.assert_called_once_with()
    relationship_query.eq.assert_called_once_with("document_id", "document-id")
    entity_query.delete.assert_called_once_with()
    assert entity_query.eq.call_args_list == [
        (("document_id", "document-id"),),
        (("user_id", "single_user"),),
    ]


def test_insert_document_entities_inserts_validated_single_user_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    entity = EntityDraft(
        entity_name="Probation Period",
        entity_type="contract term",
        description="Trial period",
        chunk_id="11111111-1111-1111-1111-111111111111",
    )
    inserted_rows = [{"id": "entity-1"}]
    query = Mock()
    query.insert.return_value = query
    query.execute.return_value = SimpleNamespace(data=inserted_rows)
    client = SimpleNamespace(table=Mock(return_value=query))
    monkeypatch.setattr(supabase_service, "get_settings", lambda: _settings())
    monkeypatch.setattr(supabase_service, "get_supabase_client", lambda: client)

    result = supabase_service.insert_document_entities("document-id", [entity])

    assert result == inserted_rows
    client.table.assert_called_once_with("document_entities")
    query.insert.assert_called_once_with(
        [
            {
                "document_id": "document-id",
                "chunk_id": "11111111-1111-1111-1111-111111111111",
                "user_id": "single_user",
                "entity_name": "Probation Period",
                "entity_type": "contract term",
                "description": "Trial period",
            }
        ]
    )
    query.execute.assert_called_once_with()


def test_find_document_entity_filters_single_user_name_and_type(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    row = {"id": "entity-1", "entity_name": "Probation Period"}
    query = Mock()
    query.select.return_value = query
    query.eq.return_value = query
    query.limit.return_value = query
    query.execute.return_value = SimpleNamespace(data=[row])
    client = SimpleNamespace(table=Mock(return_value=query))
    monkeypatch.setattr(supabase_service, "get_settings", lambda: _settings())
    monkeypatch.setattr(supabase_service, "get_supabase_client", lambda: client)

    result = supabase_service.find_document_entity(
        "document-id",
        "  Probation Period  ",
        "contract term",
    )

    assert result == row
    client.table.assert_called_once_with("document_entities")
    assert query.eq.call_args_list == [
        (("document_id", "document-id"),),
        (("user_id", "single_user"),),
        (("entity_name", "Probation Period"),),
        (("entity_type", "contract term"),),
    ]
    query.limit.assert_called_once_with(1)


def test_insert_document_relationships_inserts_validated_rows_without_user_filter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    relationship = RelationshipDraft(
        source_type="chunk",
        source_id="chunk-1",
        target_type="entity",
        target_id="entity-1",
        relationship_type="chunk_mentions_entity",
        weight=1.0,
        description="mentions",
    )
    inserted_rows = [{"id": "relationship-1"}]
    query = Mock()
    query.insert.return_value = query
    query.execute.return_value = SimpleNamespace(data=inserted_rows)
    client = SimpleNamespace(table=Mock(return_value=query))
    monkeypatch.setattr(supabase_service, "get_supabase_client", lambda: client)

    result = supabase_service.insert_document_relationships(
        "document-id",
        [relationship],
    )

    assert result == inserted_rows
    client.table.assert_called_once_with("document_relationships")
    query.insert.assert_called_once_with(
        [
            {
                "document_id": "document-id",
                "source_type": "chunk",
                "source_id": "chunk-1",
                "target_type": "entity",
                "target_id": "entity-1",
                "relationship_type": "chunk_mentions_entity",
                "weight": 1.0,
                "description": "mentions",
            }
        ]
    )
    query.execute.assert_called_once_with()


def test_insert_document_relationships_reports_safe_insert_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    query = Mock()
    query.insert.return_value = query
    query.execute.side_effect = RuntimeError("database secret")
    client = SimpleNamespace(table=Mock(return_value=query))
    monkeypatch.setattr(supabase_service, "get_supabase_client", lambda: client)

    with pytest.raises(SupabaseConnectionError) as exc_info:
        supabase_service.insert_document_relationships(
            "document-id",
            [
                RelationshipDraft(
                    source_type="chunk",
                    source_id="chunk-1",
                    target_type="entity",
                    target_id="entity-1",
                    relationship_type="chunk_mentions_entity",
                    weight=1.0,
                )
            ],
        )

    message = str(exc_info.value)
    assert "document relationship insert" in message
    assert "RuntimeError" in message
    assert "database secret" not in message


def test_remove_document_file_uses_exact_configured_bucket_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bucket = SimpleNamespace(remove=Mock(return_value=[]))
    storage = SimpleNamespace(from_=Mock(return_value=bucket))
    client = SimpleNamespace(storage=storage)
    monkeypatch.setattr(
        supabase_service,
        "get_settings",
        lambda: _settings(storage_bucket="private-documents"),
    )
    monkeypatch.setattr(supabase_service, "get_supabase_client", lambda: client)

    result = supabase_service.remove_document_file(
        "documents/single_user/document-id/original file.txt"
    )

    assert result is True
    storage.from_.assert_called_once_with("private-documents")
    bucket.remove.assert_called_once_with(
        ["documents/single_user/document-id/original file.txt"]
    )


def test_remove_document_file_treats_missing_response_as_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bucket = SimpleNamespace(remove=Mock(return_value=None))
    client = SimpleNamespace(storage=SimpleNamespace(from_=Mock(return_value=bucket)))
    monkeypatch.setattr(supabase_service, "get_settings", lambda: _settings())
    monkeypatch.setattr(supabase_service, "get_supabase_client", lambda: client)

    assert supabase_service.remove_document_file("missing/path.txt") is True


def test_remove_document_file_reports_safe_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bucket = SimpleNamespace(remove=Mock(side_effect=RuntimeError("storage secret")))
    client = SimpleNamespace(storage=SimpleNamespace(from_=Mock(return_value=bucket)))
    monkeypatch.setattr(supabase_service, "get_settings", lambda: _settings())
    monkeypatch.setattr(supabase_service, "get_supabase_client", lambda: client)

    with pytest.raises(SupabaseConnectionError) as exc_info:
        supabase_service.remove_document_file("documents/user/doc/file.txt")

    message = str(exc_info.value)
    assert "storage delete" in message
    assert "RuntimeError" in message
    assert "storage secret" not in message


def test_delete_owned_document_cascade_calls_exact_rpc_and_returns_first_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    row = {"deleted_agent_runs": 2, "deleted_chat_messages": 4}
    query = Mock()
    query.execute.return_value = SimpleNamespace(data=[row])
    client = SimpleNamespace(rpc=Mock(return_value=query))
    monkeypatch.setattr(supabase_service, "get_supabase_client", lambda: client)

    result = supabase_service.delete_owned_document_cascade(
        "document-id",
        "single_user",
    )

    assert result == row
    client.rpc.assert_called_once_with(
        "delete_owned_document_cascade",
        {"p_document_id": "document-id", "p_user_id": "single_user"},
    )
    query.execute.assert_called_once_with()


def test_delete_owned_document_cascade_returns_none_for_empty_rpc_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    query = Mock()
    query.execute.return_value = SimpleNamespace(data=[])
    client = SimpleNamespace(rpc=Mock(return_value=query))
    monkeypatch.setattr(supabase_service, "get_supabase_client", lambda: client)

    assert (
        supabase_service.delete_owned_document_cascade("document-id", "single_user")
        is None
    )


def test_delete_owned_document_cascade_reports_safe_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    query = Mock()
    query.execute.side_effect = RuntimeError("database secret")
    client = SimpleNamespace(rpc=Mock(return_value=query))
    monkeypatch.setattr(supabase_service, "get_supabase_client", lambda: client)

    with pytest.raises(SupabaseConnectionError) as exc_info:
        supabase_service.delete_owned_document_cascade("document-id", "single_user")

    message = str(exc_info.value)
    assert "document cascade delete" in message
    assert "RuntimeError" in message
    assert "database secret" not in message


def test_insert_deletion_log_inserts_row_and_returns_first_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    row = {"user_id": "single_user", "status": "success"}
    inserted = {"id": "log-id", **row}
    query = Mock()
    query.insert.return_value = query
    query.execute.return_value = SimpleNamespace(data=[inserted])
    client = SimpleNamespace(table=Mock(return_value=query))
    monkeypatch.setattr(supabase_service, "get_supabase_client", lambda: client)

    result = supabase_service.insert_deletion_log(row)

    assert result == inserted
    client.table.assert_called_once_with("deletion_logs")
    query.insert.assert_called_once_with(row)
    query.execute.assert_called_once_with()


def test_insert_deletion_log_preserves_exact_failed_audit_shape(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    row = {
        "user_id": "single_user",
        "document_id": "document-id",
        "file_name": "failed-file.txt",
        "status": "failed",
        "failure_stage": "qdrant",
        "error_message": "Document vector deletion failed.",
        "deleted_storage_file": False,
        "deleted_qdrant_points": False,
        "deleted_chunks": 0,
        "deleted_entities": 0,
        "deleted_relationships": 0,
        "deleted_agent_runs": 0,
        "deleted_agent_steps": 0,
        "deleted_chat_messages": 0,
        "deleted_chat_sessions": 0,
    }
    query = Mock()
    query.insert.return_value = query
    query.execute.return_value = SimpleNamespace(data=[{"id": "log-id", **row}])
    client = SimpleNamespace(table=Mock(return_value=query))
    monkeypatch.setattr(supabase_service, "get_supabase_client", lambda: client)

    result = supabase_service.insert_deletion_log(row)

    assert result == {"id": "log-id", **row}
    query.insert.assert_called_once_with(row)


def test_get_successful_deletion_log_scopes_and_returns_newest_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    row = {"id": "log-id", "status": "success"}
    query = Mock()
    query.select.return_value = query
    query.eq.return_value = query
    query.order.return_value = query
    query.limit.return_value = query
    query.execute.return_value = SimpleNamespace(data=[row])
    client = SimpleNamespace(table=Mock(return_value=query))
    monkeypatch.setattr(supabase_service, "get_supabase_client", lambda: client)

    result = supabase_service.get_successful_deletion_log(
        "single_user", "document-id"
    )

    assert result == row
    client.table.assert_called_once_with("deletion_logs")
    query.select.assert_called_once_with("*")
    assert query.eq.call_args_list == [
        call("user_id", "single_user"),
        call("document_id", "document-id"),
        call("status", "success"),
    ]
    query.order.assert_called_once_with("created_at", desc=True)
    query.limit.assert_called_once_with(1)


def test_get_successful_deletion_log_returns_none_when_absent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    query = Mock()
    query.select.return_value = query
    query.eq.return_value = query
    query.order.return_value = query
    query.limit.return_value = query
    query.execute.return_value = SimpleNamespace(data=[])
    client = SimpleNamespace(table=Mock(return_value=query))
    monkeypatch.setattr(supabase_service, "get_supabase_client", lambda: client)

    assert (
        supabase_service.get_successful_deletion_log("single_user", "document-id")
        is None
    )


def test_get_successful_deletion_log_reports_safe_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    query = Mock()
    query.select.return_value = query
    query.eq.return_value = query
    query.order.return_value = query
    query.limit.return_value = query
    query.execute.side_effect = RuntimeError("database secret")
    client = SimpleNamespace(table=Mock(return_value=query))
    monkeypatch.setattr(supabase_service, "get_supabase_client", lambda: client)

    with pytest.raises(SupabaseConnectionError) as exc_info:
        supabase_service.get_successful_deletion_log("single_user", "document-id")

    assert "deletion success reconciliation" in str(exc_info.value)
    assert "database secret" not in str(exc_info.value)


def test_list_deletion_logs_omits_status_and_uses_descending_inclusive_range(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows = [{"id": "log-id"}]
    query = Mock()
    query.select.return_value = query
    query.eq.return_value = query
    query.order.return_value = query
    query.range.return_value = query
    query.execute.return_value = SimpleNamespace(data=rows)
    client = SimpleNamespace(table=Mock(return_value=query))
    monkeypatch.setattr(supabase_service, "get_supabase_client", lambda: client)

    result = supabase_service.list_deletion_logs(
        "single_user",
        status=None,
        limit=25,
        offset=50,
    )

    assert result == rows
    client.table.assert_called_once_with("deletion_logs")
    query.select.assert_called_once_with("*")
    query.eq.assert_called_once_with("user_id", "single_user")
    query.order.assert_called_once_with("created_at", desc=True)
    query.range.assert_called_once_with(50, 74)
    query.execute.assert_called_once_with()


def test_list_deletion_logs_applies_status_filter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    query = Mock()
    query.select.return_value = query
    query.eq.return_value = query
    query.order.return_value = query
    query.range.return_value = query
    query.execute.return_value = SimpleNamespace(data=[])
    client = SimpleNamespace(table=Mock(return_value=query))
    monkeypatch.setattr(supabase_service, "get_supabase_client", lambda: client)

    supabase_service.list_deletion_logs(
        "single_user",
        status="failed",
        limit=10,
        offset=0,
    )

    assert query.eq.call_args_list == [
        (("user_id", "single_user"),),
        (("status", "failed"),),
    ]


def test_list_deletion_logs_reports_safe_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    query = Mock()
    query.select.return_value = query
    query.eq.return_value = query
    query.order.return_value = query
    query.range.return_value = query
    query.execute.side_effect = RuntimeError("database secret")
    client = SimpleNamespace(table=Mock(return_value=query))
    monkeypatch.setattr(supabase_service, "get_supabase_client", lambda: client)

    with pytest.raises(SupabaseConnectionError) as exc_info:
        supabase_service.list_deletion_logs(
            "single_user",
            status=None,
            limit=10,
            offset=0,
        )

    message = str(exc_info.value)
    assert "deletion log list" in message
    assert "RuntimeError" in message
    assert "database secret" not in message
