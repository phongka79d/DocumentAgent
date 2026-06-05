import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import Settings


def test_settings_allow_missing_supabase_values_for_basic_app_usage() -> None:
    settings = Settings(_env_file=None)

    assert settings.supabase_url is None
    assert settings.supabase_service_role_key is None
    assert settings.shopaikey_api_key is None
    assert settings.shopaikey_base_url is None
    assert settings.shopaikey_embedding_model is None
    assert settings.qdrant_url is None
    assert settings.qdrant_api_key is None
    assert settings.qdrant_collection is None
    assert settings.retrieval_semantic_top_k == 20
    assert settings.max_upload_bytes == 25_000_000
    assert settings.chunk_size_tokens == 1000
    assert settings.chunk_overlap_tokens == 150


def test_settings_allow_retrieval_semantic_top_k_override() -> None:
    settings = Settings(_env_file=None, retrieval_semantic_top_k=8)

    assert settings.retrieval_semantic_top_k == 8


@pytest.mark.parametrize("top_k", [0, 51])
def test_settings_reject_retrieval_semantic_top_k_outside_plan_bounds(top_k: int) -> None:
    with pytest.raises(ValueError):
        Settings(_env_file=None, retrieval_semantic_top_k=top_k)


def test_settings_allow_upload_size_override() -> None:
    settings = Settings(_env_file=None, max_upload_bytes=1_000)

    assert settings.max_upload_bytes == 1_000


def test_settings_allow_chunk_size_and_overlap_override() -> None:
    settings = Settings(
        _env_file=None,
        chunk_size_tokens=800,
        chunk_overlap_tokens=100,
    )

    assert settings.chunk_size_tokens == 800
    assert settings.chunk_overlap_tokens == 100


def test_settings_reject_overlap_greater_than_or_equal_to_chunk_size() -> None:
    with pytest.raises(ValueError, match="CHUNK_OVERLAP_TOKENS must be less than CHUNK_SIZE_TOKENS"):
        Settings(
            _env_file=None,
            chunk_size_tokens=150,
            chunk_overlap_tokens=150,
        )


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


def test_require_shopaikey_settings_raises_clear_error_without_secret_values() -> None:
    settings = Settings(
        _env_file=None,
        shopaikey_api_key="private-shopaikey-value",
        shopaikey_embedding_model="text-embedding-ada-002",
    )

    with pytest.raises(RuntimeError) as exc_info:
        settings.require_shopaikey_settings()

    message = str(exc_info.value)
    assert "SHOPAIKEY_BASE_URL" in message
    assert "private-shopaikey-value" not in message


def test_require_shopaikey_settings_returns_values_when_configured() -> None:
    settings = Settings(
        _env_file=None,
        shopaikey_api_key="shopaikey-key",
        shopaikey_base_url="https://api.shopaikey.com/v1",
        shopaikey_embedding_model="text-embedding-ada-002",
    )

    assert settings.require_shopaikey_settings() == {
        "api_key": "shopaikey-key",
        "base_url": "https://api.shopaikey.com/v1",
        "embedding_model": "text-embedding-ada-002",
    }


def test_require_qdrant_settings_raises_clear_error_without_secret_values() -> None:
    settings = Settings(
        _env_file=None,
        qdrant_api_key="private-qdrant-value",
        qdrant_collection="document_chunks",
    )

    with pytest.raises(RuntimeError) as exc_info:
        settings.require_qdrant_settings()

    message = str(exc_info.value)
    assert "QDRANT_URL" in message
    assert "private-qdrant-value" not in message


def test_require_qdrant_settings_returns_values_when_configured() -> None:
    settings = Settings(
        _env_file=None,
        qdrant_url="https://example-cluster.qdrant.io",
        qdrant_api_key="qdrant-key",
        qdrant_collection="document_chunks",
    )

    assert settings.require_qdrant_settings() == {
        "url": "https://example-cluster.qdrant.io",
        "api_key": "qdrant-key",
        "collection": "document_chunks",
    }
