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


def _get_configured_storage_bucket() -> str:
    return get_settings().supabase_storage_bucket


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


def _bucket_matches(bucket: object, bucket_name: str) -> bool:
    if isinstance(bucket, dict):
        return bucket.get("id") == bucket_name or bucket.get("name") == bucket_name

    return (
        getattr(bucket, "id", None) == bucket_name
        or getattr(bucket, "name", None) == bucket_name
    )


def check_supabase_connection() -> dict[str, bool]:
    client = get_supabase_client()
    bucket_name = _get_configured_storage_bucket()

    try:
        client.table("documents").select("id").limit(1).execute()
    except Exception as exc:
        _raise_supabase_query_error("documents connectivity check", exc)

    try:
        buckets = client.storage.list_buckets()
    except Exception as exc:
        _raise_supabase_query_error("storage bucket connectivity check", exc)

    if not any(_bucket_matches(bucket, bucket_name) for bucket in buckets):
        _raise_missing_storage_bucket_error(bucket_name)

    return {"database": True, "storage": True}


def upload_document_file(
    storage_path: str,
    content: bytes,
    *,
    content_type: str | None = None,
) -> str:
    client = get_supabase_client()
    bucket_name = _get_configured_storage_bucket()

    file_options = {"upsert": "false"}
    if content_type:
        file_options["content-type"] = content_type

    try:
        client.storage.from_(bucket_name).upload(storage_path, content, file_options)
    except Exception as exc:
        _raise_supabase_query_error("storage upload", exc)

    return storage_path


def _first_response_row(operation_name: str, response: object) -> dict:
    data = getattr(response, "data", None)
    if not data:
        raise SupabaseConnectionError(
            _format_operation_error(operation_name, "empty result")
        )

    return data[0]


def insert_document_metadata(document_row: dict) -> dict:
    client = get_supabase_client()

    try:
        response = client.table("documents").insert(document_row).execute()
    except Exception as exc:
        _raise_supabase_query_error("document metadata insert", exc)

    return _first_response_row("document metadata insert", response)


def list_document_metadata(user_id: str) -> list[dict]:
    client = get_supabase_client()

    try:
        response = (
            client.table("documents")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .execute()
        )
    except Exception as exc:
        _raise_supabase_query_error("document metadata list", exc)

    return getattr(response, "data", None) or []


def get_document_metadata(document_id: str, user_id: str) -> dict | None:
    client = get_supabase_client()

    try:
        response = (
            client.table("documents")
            .select("*")
            .eq("id", document_id)
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
    except Exception as exc:
        _raise_supabase_query_error("document metadata detail", exc)

    data = getattr(response, "data", None) or []
    if not data:
        return None

    return data[0]
