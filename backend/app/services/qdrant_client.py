from qdrant_client import QdrantClient

from app.core import config as config_module
from app.core.config import Settings


def _resolve_settings(settings: Settings | None = None) -> Settings:
    return settings if settings is not None else config_module.get_settings()


def create_qdrant_client(settings: Settings | None = None) -> QdrantClient:
    resolved_settings = _resolve_settings(settings)
    return QdrantClient(
        url=resolved_settings.QDRANT_URL,
        api_key=resolved_settings.QDRANT_API_KEY,
        check_compatibility=False,
    )

