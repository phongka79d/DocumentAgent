import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.security import require_admin_token
from app.main import create_app


ALL_SETTINGS_FIELDS = {
    "APP_ENV",
    "FRONTEND_ORIGIN",
    "ADMIN_API_TOKEN",
    "SUPABASE_URL",
    "SUPABASE_SERVICE_ROLE_KEY",
    "SUPABASE_STORAGE_BUCKET",
    "SHOPAIKEY_API_KEY",
    "SHOPAIKEY_BASE_URL",
    "SHOPAIKEY_CHAT_MODEL",
    "SHOPAIKEY_EMBEDDING_MODEL",
    "QDRANT_URL",
    "QDRANT_API_KEY",
    "QDRANT_COLLECTION",
    "ENABLE_RERANK",
    "JINA_API_KEY",
    "JINA_RERANK_MODEL",
    "RETRIEVAL_SEMANTIC_TOP_K",
    "RETRIEVAL_FINAL_TOP_K",
    "RETRIEVAL_CONTEXT_WINDOW",
    "RETRIEVAL_CONTEXT_MAX_CANDIDATES",
    "CHUNK_SIZE_TOKENS",
    "CHUNK_OVERLAP_TOKENS",
    "MAX_UPLOAD_BYTES",
    "TEMPERATURE",
    "MAX_OUTPUT_TOKENS",
}


def _clear_settings_env(monkeypatch):
    for name in ALL_SETTINGS_FIELDS:
        monkeypatch.delenv(name, raising=False)


def test_health_endpoint_returns_ok(client):
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_application_title_is_ragdocument_api(app_factory):
    app = app_factory()

    assert app.title == "RagDocument API"


def test_settings_load_defaults_from_master_plan(monkeypatch):
    _clear_settings_env(monkeypatch)

    settings = Settings(_env_file=None)

    assert set(settings.model_dump().keys()) == ALL_SETTINGS_FIELDS
    assert settings.APP_ENV == "development"
    assert settings.FRONTEND_ORIGIN == "http://localhost:5173"
    assert settings.ADMIN_API_TOKEN == ""
    assert settings.SUPABASE_STORAGE_BUCKET == "documents"
    assert settings.SHOPAIKEY_BASE_URL == "https://api.shopaikey.com/v1"
    assert settings.QDRANT_COLLECTION == "document_chunks_v1"
    assert settings.ENABLE_RERANK is True
    assert settings.RETRIEVAL_SEMANTIC_TOP_K == 40
    assert settings.RETRIEVAL_FINAL_TOP_K == 5
    assert settings.RETRIEVAL_CONTEXT_WINDOW == 1
    assert settings.RETRIEVAL_CONTEXT_MAX_CANDIDATES == 8
    assert settings.CHUNK_SIZE_TOKENS == 500
    assert settings.CHUNK_OVERLAP_TOKENS == 150
    assert settings.MAX_UPLOAD_BYTES == 25000000
    assert settings.TEMPERATURE == 0.2
    assert settings.MAX_OUTPUT_TOKENS == 1200


def test_settings_read_environment_overrides(monkeypatch):
    _clear_settings_env(monkeypatch)
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("FRONTEND_ORIGIN", "https://frontend.example")
    monkeypatch.setenv("ADMIN_API_TOKEN", "secret-token")
    monkeypatch.setenv("ENABLE_RERANK", "false")
    monkeypatch.setenv("RETRIEVAL_FINAL_TOP_K", "7")
    monkeypatch.setenv("MAX_OUTPUT_TOKENS", "2048")

    settings = Settings(_env_file=None)

    assert settings.APP_ENV == "production"
    assert settings.FRONTEND_ORIGIN == "https://frontend.example"
    assert settings.ADMIN_API_TOKEN == "secret-token"
    assert settings.ENABLE_RERANK is False
    assert settings.RETRIEVAL_FINAL_TOP_K == 7
    assert settings.MAX_OUTPUT_TOKENS == 2048


def test_cors_uses_frontend_origin_from_settings():
    origin = "http://frontend.example"
    app = create_app(settings=Settings(FRONTEND_ORIGIN=origin))

    with TestClient(app) as test_client:
        response = test_client.options(
            "/api/health",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "GET",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin


def test_require_admin_token_allows_empty_admin_token():
    settings = Settings(ADMIN_API_TOKEN="")

    assert require_admin_token(settings=settings, x_admin_api_token=None) is None
    assert require_admin_token(settings=settings, x_admin_api_token="anything") is None


def test_require_admin_token_accepts_matching_token_when_configured():
    settings = Settings(ADMIN_API_TOKEN="expected-token")

    assert (
        require_admin_token(settings=settings, x_admin_api_token="expected-token")
        is None
    )


def test_require_admin_token_rejects_wrong_token_when_configured():
    settings = Settings(ADMIN_API_TOKEN="expected-token")

    with pytest.raises(HTTPException) as excinfo:
        require_admin_token(settings=settings, x_admin_api_token="wrong-token")

    assert excinfo.value.status_code == 401
    assert excinfo.value.detail == "Invalid or missing X-Admin-API-Token"
