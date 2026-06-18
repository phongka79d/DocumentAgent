from openai import OpenAI

from app.core import config as config_module
from app.core.config import Settings


def _resolve_settings(settings: Settings | None = None) -> Settings:
    return settings if settings is not None else config_module.get_settings()


def create_shopaikey_client(settings: Settings | None = None) -> OpenAI:
    resolved_settings = _resolve_settings(settings)
    return OpenAI(
        api_key=resolved_settings.SHOPAIKEY_API_KEY,
        base_url=resolved_settings.SHOPAIKEY_BASE_URL,
    )

