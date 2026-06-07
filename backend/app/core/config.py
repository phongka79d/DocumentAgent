from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    app_env: str = "development"
    single_user_id: str = "single_user"
    frontend_origin: str = "http://localhost:5173"
    supabase_url: str | None = None
    supabase_service_role_key: str | None = None
    supabase_storage_bucket: str = "documents"
    shopaikey_api_key: str | None = None
    shopaikey_base_url: str | None = None
    shopaikey_chat_model: str | None = None
    shopaikey_embedding_model: str | None = None
    graph_extraction_enabled: bool = True
    qdrant_url: str | None = None
    qdrant_api_key: str | None = None
    qdrant_collection: str | None = None
    retrieval_semantic_top_k: int = Field(default=20, ge=1, le=50)
    max_upload_bytes: int | None = 25_000_000
    chunk_size_tokens: int = Field(default=1000, gt=0)
    chunk_overlap_tokens: int = Field(default=150, ge=0)

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @model_validator(mode="after")
    def validate_chunking_settings(self) -> "Settings":
        if self.chunk_overlap_tokens >= self.chunk_size_tokens:
            raise ValueError("CHUNK_OVERLAP_TOKENS must be less than CHUNK_SIZE_TOKENS")
        return self

    def require_supabase_settings(self) -> dict[str, Any]:
        if not self.supabase_url:
            raise RuntimeError(
                "Missing SUPABASE_URL. Configure it in the backend environment before using Supabase services."
            )
        if not self.supabase_service_role_key:
            raise RuntimeError(
                "Missing SUPABASE_SERVICE_ROLE_KEY. Configure it in the backend environment before using Supabase services."
            )

        return {
            "url": self.supabase_url,
            "service_role_key": self.supabase_service_role_key,
            "storage_bucket": self.supabase_storage_bucket,
        }

    def require_shopaikey_settings(self) -> dict[str, Any]:
        missing = []
        if not self.shopaikey_api_key:
            missing.append("SHOPAIKEY_API_KEY")
        if not self.shopaikey_base_url:
            missing.append("SHOPAIKEY_BASE_URL")
        if not self.shopaikey_embedding_model:
            missing.append("SHOPAIKEY_EMBEDDING_MODEL")

        if missing:
            raise RuntimeError(
                f"Missing {', '.join(missing)}. Configure ShopAIKey settings in the backend environment before using embedding services."
            )

        return {
            "api_key": self.shopaikey_api_key,
            "base_url": self.shopaikey_base_url,
            "embedding_model": self.shopaikey_embedding_model,
        }

    def require_shopaikey_chat_settings(self) -> dict[str, Any]:
        missing = []
        if not self.shopaikey_api_key:
            missing.append("SHOPAIKEY_API_KEY")
        if not self.shopaikey_base_url:
            missing.append("SHOPAIKEY_BASE_URL")
        if not self.shopaikey_chat_model:
            missing.append("SHOPAIKEY_CHAT_MODEL")

        if missing:
            raise RuntimeError(
                f"Missing {', '.join(missing)}. Configure ShopAIKey settings in the backend environment before using chat completion services."
            )

        return {
            "api_key": self.shopaikey_api_key,
            "base_url": self.shopaikey_base_url,
            "chat_model": self.shopaikey_chat_model,
        }

    def require_qdrant_settings(self) -> dict[str, Any]:
        missing = []
        if not self.qdrant_url:
            missing.append("QDRANT_URL")
        if not self.qdrant_api_key:
            missing.append("QDRANT_API_KEY")
        if not self.qdrant_collection:
            missing.append("QDRANT_COLLECTION")

        if missing:
            raise RuntimeError(
                f"Missing {', '.join(missing)}. Configure Qdrant settings in the backend environment before using vector indexing services."
            )

        return {
            "url": self.qdrant_url,
            "api_key": self.qdrant_api_key,
            "collection": self.qdrant_collection,
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()
