import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import Settings


def test_settings_allow_missing_supabase_values_for_basic_app_usage() -> None:
    settings = Settings(_env_file=None)

    assert settings.supabase_url is None
    assert settings.supabase_service_role_key is None
    assert settings.max_upload_bytes == 25_000_000


def test_settings_allow_upload_size_override() -> None:
    settings = Settings(_env_file=None, max_upload_bytes=1_000)

    assert settings.max_upload_bytes == 1_000


def test_require_supabase_settings_raises_clear_error_when_url_missing() -> None:
    settings = Settings(
        _env_file=None,
        supabase_service_role_key="service-role-key",
    )

    with pytest.raises(RuntimeError, match="SUPABASE_URL"):
        settings.require_supabase_settings()


def test_require_supabase_settings_raises_clear_error_when_service_key_missing() -> None:
    settings = Settings(
        _env_file=None,
        supabase_url="https://example.supabase.co",
    )

    with pytest.raises(RuntimeError, match="SUPABASE_SERVICE_ROLE_KEY"):
        settings.require_supabase_settings()


def test_require_supabase_settings_returns_values_when_configured() -> None:
    settings = Settings(
        _env_file=None,
        supabase_url="https://example.supabase.co",
        supabase_service_role_key="service-role-key",
        supabase_storage_bucket="custom-bucket",
    )

    assert settings.require_supabase_settings() == {
        "url": "https://example.supabase.co",
        "service_role_key": "service-role-key",
        "storage_bucket": "custom-bucket",
    }
