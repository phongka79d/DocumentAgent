from functools import lru_cache

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
    SHOPAIKEY_CHAT_MODEL: str = "gpt-5-mini"
    SHOPAIKEY_EMBEDDING_MODEL: str = "text-embedding-3-small"

    QDRANT_URL: str = "https://your-cluster-url.cloud.qdrant.io"
    QDRANT_API_KEY: str = "your-qdrant-key"
    QDRANT_COLLECTION: str = "document_chunks_v1"

    ENABLE_RERANK: bool = True
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

    CHUNKING_STRATEGY: str = "smart_section"
    HEADER_SCORE_THRESHOLD: int = 4
    TABLE_CHUNK_MAX_TOKENS: int = 500

    CHUNK_SIZE_TOKENS: int = 500
    CHUNK_OVERLAP_TOKENS: int = 150

    MAX_UPLOAD_BYTES: int = 25_000_000
    TEMPERATURE: float = 0.2
    MAX_OUTPUT_TOKENS: int = 1200


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
