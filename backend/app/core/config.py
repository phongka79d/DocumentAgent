from __future__ import annotations

from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    APP_ENV: str = "development"
    FRONTEND_ORIGIN: str = "http://localhost:5173"
    ADMIN_API_TOKEN: str = ""

    SUPABASE_URL: str = "https://your-project.supabase.co"
    SUPABASE_SERVICE_ROLE_KEY: str = "your-supabase-service-role-key"
    SUPABASE_STORAGE_BUCKET: str = "documents"

    SHOPAIKEY_API_KEY: str = "your-key"
    SHOPAIKEY_BASE_URL: str = "https://api.shopaikey.com/v1"
    SHOPAIKEY_CHAT_MODEL: str = "gpt-4o-mini"
    SHOPAIKEY_INPUT_MODEL: str = "gpt-5-nano"
    SHOPAIKEY_EMBEDDING_MODEL: str = "text-embedding-3-small"

    QDRANT_URL: str = "https://your-cluster-url.cloud.qdrant.io"
    QDRANT_API_KEY: str = "your-qdrant-key"
    QDRANT_COLLECTION: str = "document_chunks_v1"

    ENABLE_RERANK: bool = True
    ENABLE_KEYWORD_SEARCH: bool = True
    ENABLE_SUMMARIES: bool = True
    ENABLE_RELATION_RETRIEVAL: bool = True
    ENABLE_WORKFLOW_TRACING: bool = True
    JINA_API_KEY: str = "your-jina-key"
    JINA_RERANK_MODEL: str = "jina-reranker-v2-base-multilingual"

    RETRIEVAL_SEMANTIC_TOP_K: int = 40
    RETRIEVAL_FINAL_TOP_K: int = 5
    RETRIEVAL_CONTEXT_MODE: str = "section_aware"
    RETRIEVAL_CONTEXT_WINDOW: int = 1
    RETRIEVAL_SECTION_SIBLING_WINDOW: int = 1
    RETRIEVAL_CONTEXT_MAX_CANDIDATES: int = 8
    RETRIEVAL_HINT_TEMPERATURE: float = 0.0
    RETRIEVAL_HINT_MAX_TOKENS: int = 120
    RETRIEVAL_BOUNDARY_START_CHUNKS: int = 2
    RETRIEVAL_BOUNDARY_END_CHUNKS: int = 2
    RETRIEVAL_KEYWORD_TOP_K: int = Field(default=40, ge=1, le=1000)
    RETRIEVAL_FUSION_TOP_K: int = Field(default=40, ge=1, le=1000)
    RETRIEVAL_RRF_CONSTANT: int = Field(default=60, ge=1, le=10_000)
    RETRIEVAL_RERANK_CANDIDATE_TOP_K: int = Field(default=20, ge=1, le=1000)
    RETRIEVAL_CONTEXT_MAX_TOKENS: int = Field(default=4000, ge=1, le=1_000_000)

    QUERY_MAX_SUBQUERIES: int = Field(default=4, ge=1, le=20)
    QUERY_PLANNER_TEMPERATURE: float = Field(default=0.0, ge=0.0, le=2.0)
    QUERY_PLANNER_MAX_TOKENS: int = Field(default=500, ge=1, le=100_000)

    SUMMARY_SECTION_MAX_TOKENS: int = Field(default=200, ge=1, le=100_000)
    SUMMARY_DOCUMENT_MAX_TOKENS: int = Field(default=400, ge=1, le=100_000)
    RELATION_MAX_RELATED_DOCUMENTS: int = Field(default=5, ge=1, le=100)
    GROUNDING_MIN_SCORE: float = Field(default=0.80, ge=0.0, le=1.0)
    GROUNDING_MAX_REGENERATIONS: int = Field(default=1, ge=0, le=10)

    WORKFLOW_MAX_ATTEMPTS: int = Field(default=3, ge=1, le=10)
    WORKFLOW_RETRY_BASE_DELAY_SECONDS: float = Field(default=0.25, ge=0.0, le=300.0)
    WORKFLOW_RETRY_MAX_DELAY_SECONDS: float = Field(default=2.0, ge=0.0, le=300.0)

    CHUNKING_STRATEGY: str = "smart_section"
    HEADER_SCORE_THRESHOLD: int = 4
    TABLE_CHUNK_MAX_TOKENS: int = 500

    CHUNK_SIZE_TOKENS: int = 500
    CHUNK_OVERLAP_TOKENS: int = 150

    MAX_UPLOAD_BYTES: int = 25_000_000
    TEMPERATURE: float = 0.2
    MAX_OUTPUT_TOKENS: int = 1200

    @model_validator(mode="after")
    def validate_phase3_setting_relationships(self) -> Settings:
        if self.WORKFLOW_RETRY_BASE_DELAY_SECONDS > self.WORKFLOW_RETRY_MAX_DELAY_SECONDS:
            raise ValueError(
                "WORKFLOW_RETRY_BASE_DELAY_SECONDS must not exceed "
                "WORKFLOW_RETRY_MAX_DELAY_SECONDS"
            )
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
