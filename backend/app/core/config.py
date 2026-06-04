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


@lru_cache
def get_settings() -> Settings:
    return Settings()
