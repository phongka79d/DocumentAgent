from supabase import Client, create_client

from app.core.config import get_settings


_supabase_client: Client | None = None


def _get_required_supabase_config() -> tuple[str, str]:
    config = get_settings().require_supabase_settings()
    return config["url"], config["service_role_key"]


def get_supabase_client() -> Client:
    global _supabase_client

    if _supabase_client is None:
        supabase_url, service_role_key = _get_required_supabase_config()
        _supabase_client = create_client(supabase_url, service_role_key)

    return _supabase_client
