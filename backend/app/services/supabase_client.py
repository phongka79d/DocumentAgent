from supabase import Client, create_client

from app.core import config as config_module
from app.core.config import Settings


def _resolve_settings(settings: Settings | None = None) -> Settings:
    return settings if settings is not None else config_module.get_settings()


def create_supabase_client(settings: Settings | None = None) -> Client:
    resolved_settings = _resolve_settings(settings)
    return create_client(
        resolved_settings.SUPABASE_URL,
        resolved_settings.SUPABASE_SERVICE_ROLE_KEY,
    )

