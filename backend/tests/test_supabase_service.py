import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

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
