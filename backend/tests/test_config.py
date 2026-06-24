import importlib
import tomllib
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.core import config as config_module
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
    "SHOPAIKEY_INPUT_MODEL",
    "SHOPAIKEY_EMBEDDING_MODEL",
    "QDRANT_URL",
    "QDRANT_API_KEY",
    "QDRANT_COLLECTION",
    "ENABLE_RERANK",
    "ENABLE_KEYWORD_SEARCH",
    "ENABLE_SUMMARIES",
    "ENABLE_RELATION_RETRIEVAL",
    "ENABLE_WORKFLOW_TRACING",
    "JINA_API_KEY",
    "JINA_RERANK_MODEL",
    "RETRIEVAL_SEMANTIC_TOP_K",
    "RETRIEVAL_FINAL_TOP_K",
    "RETRIEVAL_CONTEXT_MODE",
    "RETRIEVAL_CONTEXT_WINDOW",
    "RETRIEVAL_SECTION_SIBLING_WINDOW",
    "RETRIEVAL_CONTEXT_MAX_CANDIDATES",
    "RETRIEVAL_HINT_TEMPERATURE",
    "RETRIEVAL_HINT_MAX_TOKENS",
    "RETRIEVAL_BOUNDARY_START_CHUNKS",
    "RETRIEVAL_BOUNDARY_END_CHUNKS",
    "RETRIEVAL_KEYWORD_TOP_K",
    "RETRIEVAL_FUSION_TOP_K",
    "RETRIEVAL_RRF_CONSTANT",
    "RETRIEVAL_RERANK_SEMANTIC_PER_PATH_TOP_K",
    "RETRIEVAL_RERANK_KEYWORD_PER_PATH_TOP_K",
    "RETRIEVAL_RERANK_FUSED_TOP_K",
    "RETRIEVAL_RERANK_CANDIDATE_TOP_K",
    "RETRIEVAL_CONTEXT_MAX_TOKENS",
    "QUERY_MAX_SUBQUERIES",
    "QUERY_PLANNER_TEMPERATURE",
    "QUERY_PLANNER_MAX_TOKENS",
    "SUMMARY_SECTION_MAX_TOKENS",
    "SUMMARY_DOCUMENT_MAX_TOKENS",
    "RELATION_MAX_RELATED_DOCUMENTS",
    "GROUNDING_MIN_SCORE",
    "GROUNDING_MAX_REGENERATIONS",
    "WORKFLOW_MAX_ATTEMPTS",
    "WORKFLOW_RETRY_BASE_DELAY_SECONDS",
    "WORKFLOW_RETRY_MAX_DELAY_SECONDS",
    "ENSURE_QDRANT_PAYLOAD_INDEXES_ON_STARTUP",
    "CHUNKING_STRATEGY",
    "HEADER_SCORE_THRESHOLD",
    "TABLE_CHUNK_MAX_TOKENS",
    "CHUNK_SIZE_TOKENS",
    "CHUNK_OVERLAP_TOKENS",
    "MAX_UPLOAD_BYTES",
    "TEMPERATURE",
    "MAX_OUTPUT_TOKENS",
}

ENV_EXAMPLE_PATH = Path(__file__).resolve().parents[1] / ".env.example"
ACTIVE_DOC_PATHS = [
    Path(__file__).resolve().parents[2] / "README.md",
    Path(__file__).resolve().parents[1] / "README.md",
]


def _env_example_values() -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in ENV_EXAMPLE_PATH.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition("=")
        assert separator == "=", f"Invalid env example line: {raw_line}"
        values[key] = value
    return values


def _project_dependencies() -> set[str]:
    pyproject_path = Path(__file__).resolve().parents[1] / "pyproject.toml"
    project_data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    dependencies = project_data["project"]["dependencies"]
    return {
        dependency.split("[", 1)[0]
        .split("<", 1)[0]
        .split(">", 1)[0]
        .split("=", 1)[0]
        .strip()
        .lower()
        for dependency in dependencies
    }


def _clear_settings_env(monkeypatch):
    for name in ALL_SETTINGS_FIELDS:
        monkeypatch.delenv(name, raising=False)


def test_jina_reranker_uses_httpx_without_conflicting_jina_sdk_dependency():
    dependencies = _project_dependencies()

    assert "httpx" in dependencies
    assert "jina" not in dependencies


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
    assert settings.SUPABASE_URL == ""
    assert settings.SUPABASE_SERVICE_ROLE_KEY == ""
    assert settings.SUPABASE_STORAGE_BUCKET == "documents"
    assert settings.SHOPAIKEY_API_KEY == ""
    assert settings.SHOPAIKEY_BASE_URL == "https://api.shopaikey.com/v1"
    assert settings.SHOPAIKEY_CHAT_MODEL == "gpt-5-mini"
    assert settings.SHOPAIKEY_INPUT_MODEL == "gpt-5-mini"
    assert settings.QDRANT_URL == ""
    assert settings.QDRANT_API_KEY == ""
    assert settings.QDRANT_COLLECTION == "document_chunks_v1"
    assert settings.JINA_API_KEY == ""
    assert settings.ENABLE_RERANK is True
    assert settings.RETRIEVAL_SEMANTIC_TOP_K == 40
    assert settings.RETRIEVAL_FINAL_TOP_K == 5
    assert settings.RETRIEVAL_CONTEXT_MODE == "section_aware"
    assert settings.RETRIEVAL_CONTEXT_WINDOW == 1
    assert settings.RETRIEVAL_SECTION_SIBLING_WINDOW == 1
    assert settings.RETRIEVAL_CONTEXT_MAX_CANDIDATES == 8
    assert settings.RETRIEVAL_HINT_TEMPERATURE == 0.0
    assert settings.RETRIEVAL_HINT_MAX_TOKENS == 120
    assert settings.RETRIEVAL_BOUNDARY_START_CHUNKS == 2
    assert settings.RETRIEVAL_BOUNDARY_END_CHUNKS == 2
    assert settings.ENABLE_KEYWORD_SEARCH is True
    assert settings.RETRIEVAL_KEYWORD_TOP_K == 40
    assert settings.RETRIEVAL_FUSION_TOP_K == 40
    assert settings.RETRIEVAL_RRF_CONSTANT == 60
    assert settings.RETRIEVAL_RERANK_CANDIDATE_TOP_K == 40
    assert settings.RETRIEVAL_CONTEXT_MAX_TOKENS == 4000
    assert settings.RETRIEVAL_RERANK_SEMANTIC_PER_PATH_TOP_K == 5
    assert settings.RETRIEVAL_RERANK_KEYWORD_PER_PATH_TOP_K == 2
    assert settings.RETRIEVAL_RERANK_FUSED_TOP_K == 10
    assert settings.ENSURE_QDRANT_PAYLOAD_INDEXES_ON_STARTUP is True
    assert settings.QUERY_MAX_SUBQUERIES == 4
    assert settings.QUERY_PLANNER_TEMPERATURE == 0.0
    assert settings.QUERY_PLANNER_MAX_TOKENS == 500
    assert settings.ENABLE_SUMMARIES is True
    assert settings.SUMMARY_SECTION_MAX_TOKENS == 200
    assert settings.SUMMARY_DOCUMENT_MAX_TOKENS == 400
    assert settings.ENABLE_RELATION_RETRIEVAL is True
    assert settings.RELATION_MAX_RELATED_DOCUMENTS == 5
    assert settings.GROUNDING_MIN_SCORE == 0.8
    assert settings.GROUNDING_MAX_REGENERATIONS == 1
    assert settings.WORKFLOW_MAX_ATTEMPTS == 3
    assert settings.WORKFLOW_RETRY_BASE_DELAY_SECONDS == 0.25
    assert settings.WORKFLOW_RETRY_MAX_DELAY_SECONDS == 2.0
    assert settings.ENABLE_WORKFLOW_TRACING is True
    assert settings.CHUNKING_STRATEGY == "smart_section"
    assert settings.HEADER_SCORE_THRESHOLD == 4
    assert settings.TABLE_CHUNK_MAX_TOKENS == 500
    assert settings.CHUNK_SIZE_TOKENS == 500
    assert settings.CHUNK_OVERLAP_TOKENS == 150
    assert settings.MAX_UPLOAD_BYTES == 25000000
    assert settings.TEMPERATURE == 0.2
    assert settings.MAX_OUTPUT_TOKENS == 1200


def test_env_example_lists_every_settings_field():
    values = _env_example_values()

    assert set(values) == ALL_SETTINGS_FIELDS


def test_active_docs_do_not_duplicate_backend_env_values():
    assignment_names = tuple(sorted(ALL_SETTINGS_FIELDS))
    for path in ACTIVE_DOC_PATHS:
        text = path.read_text(encoding="utf-8")
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            assert not any(
                stripped.startswith(f"{name}=") for name in assignment_names
            ), f"{path} duplicates backend env value line: {stripped}"


def test_service_placeholder_values_live_only_in_env_example():
    settings = Settings(_env_file=None)

    assert settings.SUPABASE_URL == ""
    assert settings.SUPABASE_SERVICE_ROLE_KEY == ""
    assert settings.SHOPAIKEY_API_KEY == ""
    assert settings.QDRANT_URL == ""
    assert settings.QDRANT_API_KEY == ""
    assert settings.JINA_API_KEY == ""


def test_settings_read_environment_overrides(monkeypatch):
    _clear_settings_env(monkeypatch)
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("FRONTEND_ORIGIN", "https://frontend.example")
    monkeypatch.setenv("ADMIN_API_TOKEN", "secret-token")
    monkeypatch.setenv("ENABLE_RERANK", "false")
    monkeypatch.setenv("RETRIEVAL_CONTEXT_MODE", "neighbor")
    monkeypatch.setenv("RETRIEVAL_SECTION_SIBLING_WINDOW", "2")
    monkeypatch.setenv("RETRIEVAL_FINAL_TOP_K", "7")
    monkeypatch.setenv("RETRIEVAL_HINT_TEMPERATURE", "0.1")
    monkeypatch.setenv("RETRIEVAL_HINT_MAX_TOKENS", "160")
    monkeypatch.setenv("RETRIEVAL_BOUNDARY_START_CHUNKS", "3")
    monkeypatch.setenv("RETRIEVAL_BOUNDARY_END_CHUNKS", "4")
    monkeypatch.setenv("MAX_OUTPUT_TOKENS", "2048")
    monkeypatch.setenv("ENABLE_KEYWORD_SEARCH", "false")
    monkeypatch.setenv("QUERY_MAX_SUBQUERIES", "6")
    monkeypatch.setenv("GROUNDING_MIN_SCORE", "0.9")
    monkeypatch.setenv("WORKFLOW_MAX_ATTEMPTS", "4")

    settings = Settings(_env_file=None)

    assert settings.APP_ENV == "production"
    assert settings.FRONTEND_ORIGIN == "https://frontend.example"
    assert settings.ADMIN_API_TOKEN == "secret-token"
    assert settings.ENABLE_RERANK is False
    assert settings.RETRIEVAL_CONTEXT_MODE == "neighbor"
    assert settings.RETRIEVAL_SECTION_SIBLING_WINDOW == 2
    assert settings.RETRIEVAL_FINAL_TOP_K == 7
    assert settings.RETRIEVAL_HINT_TEMPERATURE == 0.1
    assert settings.RETRIEVAL_HINT_MAX_TOKENS == 160
    assert settings.RETRIEVAL_BOUNDARY_START_CHUNKS == 3
    assert settings.RETRIEVAL_BOUNDARY_END_CHUNKS == 4
    assert settings.MAX_OUTPUT_TOKENS == 2048
    assert settings.ENABLE_KEYWORD_SEARCH is False
    assert settings.QUERY_MAX_SUBQUERIES == 6
    assert settings.GROUNDING_MIN_SCORE == 0.9
    assert settings.WORKFLOW_MAX_ATTEMPTS == 4


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("RETRIEVAL_KEYWORD_TOP_K", 0),
        ("QUERY_MAX_SUBQUERIES", 0),
        ("QUERY_PLANNER_TEMPERATURE", -0.1),
        ("GROUNDING_MIN_SCORE", 1.01),
        ("GROUNDING_MAX_REGENERATIONS", -1),
        ("WORKFLOW_MAX_ATTEMPTS", 0),
        ("WORKFLOW_RETRY_BASE_DELAY_SECONDS", -0.1),
    ],
)
def test_phase3_settings_reject_out_of_bounds_values(name, value):
    with pytest.raises(ValueError):
        Settings(_env_file=None, **{name: value})


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


class _CallCapture:
    def __init__(self, result=None):
        self.result = object() if result is None else result
        self.args = None
        self.kwargs = None

    def __call__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        return self.result


def _service_settings() -> Settings:
    return Settings(
        _env_file=None,
        SUPABASE_URL="https://example.supabase.co",
        SUPABASE_SERVICE_ROLE_KEY="service-role-key",
        SHOPAIKEY_API_KEY="shopai-key",
        SHOPAIKEY_BASE_URL="https://api.shopaikey.com/v1",
        QDRANT_URL="https://qdrant.example.com",
        QDRANT_API_KEY="qdrant-key",
        JINA_API_KEY="jina-key",
        JINA_RERANK_MODEL="jina-reranker-v2-base-multilingual",
    )


def test_service_client_modules_import_without_creating_clients(monkeypatch):
    import httpx
    import openai
    import qdrant_client
    import supabase

    def _fail(*args, **kwargs):
        raise AssertionError("client created during module import")

    monkeypatch.setattr(supabase, "create_client", _fail)
    monkeypatch.setattr(qdrant_client, "QdrantClient", _fail)
    monkeypatch.setattr(openai, "OpenAI", _fail)
    monkeypatch.setattr(httpx, "Client", _fail)

    import app.services.supabase_client as supabase_module
    import app.services.qdrant_client as qdrant_module
    import app.services.shopaikey_client as shopaikey_module
    import app.services.jina_client as jina_module

    try:
        importlib.reload(supabase_module)
        importlib.reload(qdrant_module)
        importlib.reload(shopaikey_module)
        importlib.reload(jina_module)
    finally:
        monkeypatch.undo()
        importlib.reload(supabase_module)
        importlib.reload(qdrant_module)
        importlib.reload(shopaikey_module)
        importlib.reload(jina_module)


def test_supabase_client_factory_reads_settings_without_network_calls(monkeypatch):
    _clear_settings_env(monkeypatch)
    settings = _service_settings()
    monkeypatch.setattr(config_module, "get_settings", lambda: settings)

    from app.services import supabase_client as module

    capture = _CallCapture()
    monkeypatch.setattr(module, "create_client", capture)

    client = module.create_supabase_client()

    assert client is capture.result
    assert capture.args == (
        settings.SUPABASE_URL,
        settings.SUPABASE_SERVICE_ROLE_KEY,
    )
    assert capture.kwargs == {}


def test_qdrant_client_factory_reads_settings_without_network_calls(monkeypatch):
    _clear_settings_env(monkeypatch)
    settings = _service_settings()
    monkeypatch.setattr(config_module, "get_settings", lambda: settings)

    from app.services import qdrant_client as module

    capture = _CallCapture()
    monkeypatch.setattr(module, "QdrantClient", capture)

    client = module.create_qdrant_client()

    assert client is capture.result
    assert capture.args == ()
    assert capture.kwargs == {
        "url": settings.QDRANT_URL,
        "api_key": settings.QDRANT_API_KEY,
        "check_compatibility": False,
    }


def test_shopaikey_client_factory_reads_settings_without_network_calls(monkeypatch):
    _clear_settings_env(monkeypatch)
    settings = _service_settings()
    monkeypatch.setattr(config_module, "get_settings", lambda: settings)

    from app.services import shopaikey_client as module

    capture = _CallCapture()
    monkeypatch.setattr(module, "OpenAI", capture)

    client = module.create_shopaikey_client()

    assert client is capture.result
    assert capture.args == ()
    assert capture.kwargs == {
        "api_key": settings.SHOPAIKEY_API_KEY,
        "base_url": settings.SHOPAIKEY_BASE_URL,
    }


def test_jina_client_factory_reads_settings_without_network_calls(monkeypatch):
    _clear_settings_env(monkeypatch)
    settings = _service_settings()
    monkeypatch.setattr(config_module, "get_settings", lambda: settings)

    from app.services import jina_client as module

    capture = _CallCapture()
    monkeypatch.setattr(module.httpx, "Client", capture)

    client = module.create_jina_client()

    assert client.http_client is capture.result
    assert client.model == settings.JINA_RERANK_MODEL
    assert capture.args == ()
    assert capture.kwargs["base_url"] == module.DEFAULT_JINA_RERANK_BASE_URL
    assert capture.kwargs["headers"] == {
        "Authorization": f"Bearer {settings.JINA_API_KEY}",
        "Accept": "application/json",
    }
