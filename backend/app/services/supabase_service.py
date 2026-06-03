from supabase import Client, create_client

from app.core.config import get_settings


_supabase_client: Client | None = None


class SupabaseConnectionError(RuntimeError):
    """Raised when backend Supabase configuration or setup checks fail."""


def _format_operation_error(operation_name: str, failure_type: str) -> str:
    return f"Supabase operation '{operation_name}' failed: {failure_type}."


def _get_required_supabase_config() -> tuple[str, str]:
    try:
        config = get_settings().require_supabase_settings()
    except RuntimeError as exc:
        raise SupabaseConnectionError(f"Backend Supabase configuration error: {exc}") from exc

    return config["url"], config["service_role_key"]


def _raise_supabase_query_error(operation_name: str, exc: Exception) -> None:
    raise SupabaseConnectionError(
        _format_operation_error(operation_name, type(exc).__name__)
    ) from exc


def _raise_missing_storage_bucket_error(bucket_name: str) -> None:
    raise SupabaseConnectionError(
        f"Supabase storage setup failure: bucket '{bucket_name}' is missing or unavailable."
    )


def get_supabase_client() -> Client:
    global _supabase_client

    if _supabase_client is None:
        supabase_url, service_role_key = _get_required_supabase_config()
        try:
            _supabase_client = create_client(supabase_url, service_role_key)
        except Exception as exc:
            raise SupabaseConnectionError(
                _format_operation_error("client initialization", type(exc).__name__)
            ) from exc

    return _supabase_client
