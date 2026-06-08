from typing import Any

from supabase import Client, create_client

from app.core.config import get_settings
from app.schemas.graph import EntityDraft, RelationshipDraft
from app.schemas.parsing import ChunkDraft


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


def _response_rows(response: object) -> list[dict]:
    return getattr(response, "data", None) or []


def _get_single_user_id() -> str:
    return get_settings().single_user_id


def _chunk_insert_row(
    chunk: ChunkDraft,
    document_id: str,
    user_id: str,
) -> dict[str, Any]:
    return {
        "document_id": document_id,
        "user_id": user_id,
        "chunk_index": chunk.chunk_index,
        "content": chunk.content,
        "page_number": chunk.page_number,
        "section_title": chunk.section_title,
        "token_count": chunk.token_count,
        "qdrant_point_id": None,
    }


def _entity_insert_row(
    entity: EntityDraft,
    document_id: str,
    user_id: str,
) -> dict[str, Any]:
    if not isinstance(entity, EntityDraft):
        raise ValueError("document entity inserts require validated EntityDraft items")

    return {
        "document_id": document_id,
        "chunk_id": str(entity.chunk_id),
        "user_id": user_id,
        "entity_name": entity.entity_name,
        "entity_type": entity.entity_type,
        "description": entity.description,
    }


def _relationship_insert_row(
    relationship: RelationshipDraft,
    document_id: str,
) -> dict[str, Any]:
    if not isinstance(relationship, RelationshipDraft):
        raise ValueError(
            "document relationship inserts require validated RelationshipDraft items"
        )

    return {
        "document_id": document_id,
        "source_type": relationship.source_type,
        "source_id": relationship.source_id,
        "target_type": relationship.target_type,
        "target_id": relationship.target_id,
        "relationship_type": relationship.relationship_type,
        "weight": relationship.weight,
        "description": relationship.description,
    }


def insert_document_metadata(document_row: dict) -> dict:
    client = get_supabase_client()

    try:
        response = client.table("documents").insert(document_row).execute()
    except Exception as exc:
        _raise_supabase_query_error("document metadata insert", exc)

    return _first_response_row("document metadata insert", response)


def insert_agent_step_log(
    *,
    agent_run_id: str,
    step_name: str,
    agent_name: str,
    input_payload: dict[str, Any],
    output_payload: dict[str, Any],
    status: str,
    error_message: str | None = None,
) -> dict:
    client = get_supabase_client()
    row = {
        "agent_run_id": agent_run_id,
        "step_name": step_name,
        "agent_name": agent_name,
        "input": input_payload,
        "output": output_payload,
        "status": status,
        "error_message": error_message,
    }

    try:
        response = client.table("agent_steps").insert(row).execute()
    except Exception as exc:
        _raise_supabase_query_error("agent step log insert", exc)

    return _first_response_row("agent step log insert", response)


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


def get_processing_document(document_id: str) -> dict | None:
    """Load one document for the configured single user."""
    return get_document_metadata(document_id, _get_single_user_id())


def get_indexing_document(document_id: str) -> dict | None:
    """Load one document for indexing for the configured single user."""
    return get_document_metadata(document_id, _get_single_user_id())


def get_graph_document(document_id: str) -> dict | None:
    """Load one document for graph building for the configured single user."""
    return get_document_metadata(document_id, _get_single_user_id())


def download_original_document_file(storage_path: str) -> bytes:
    client = get_supabase_client()
    bucket_name = _get_configured_storage_bucket()

    try:
        content = client.storage.from_(bucket_name).download(storage_path)
    except Exception as exc:
        _raise_supabase_query_error("storage download", exc)

    if not isinstance(content, bytes):
        raise SupabaseConnectionError(
            _format_operation_error("storage download", "invalid response")
        )

    return content


def insert_document_chunks(document_id: str, chunks: list[ChunkDraft]) -> list[dict]:
    if not chunks:
        return []

    client = get_supabase_client()
    user_id = _get_single_user_id()
    rows = [_chunk_insert_row(chunk, document_id, user_id) for chunk in chunks]

    try:
        response = client.table("document_chunks").insert(rows).execute()
    except Exception as exc:
        _raise_supabase_query_error("document chunk insert", exc)

    return _response_rows(response)


def list_chunks_needing_indexing(document_id: str) -> list[dict]:
    client = get_supabase_client()

    try:
        response = (
            client.table("document_chunks")
            .select(
                "id, document_id, user_id, chunk_index, content, page_number, "
                "section_title, token_count, qdrant_point_id"
            )
            .eq("document_id", document_id)
            .eq("user_id", _get_single_user_id())
            .is_("qdrant_point_id", "null")
            .order("chunk_index")
            .execute()
        )
    except Exception as exc:
        _raise_supabase_query_error("document chunks indexing list", exc)

    return _response_rows(response)


def list_document_chunks(document_id: str) -> list[dict]:
    client = get_supabase_client()

    try:
        response = (
            client.table("document_chunks")
            .select(
                "id, document_id, user_id, chunk_index, content, page_number, "
                "section_title, token_count, qdrant_point_id"
            )
            .eq("document_id", document_id)
            .eq("user_id", _get_single_user_id())
            .order("chunk_index")
            .execute()
        )
    except Exception as exc:
        _raise_supabase_query_error("document chunks graph list", exc)

    return _response_rows(response)


def clear_document_graph_rows(document_id: str) -> None:
    client = get_supabase_client()
    user_id = _get_single_user_id()

    try:
        (
            client.table("document_relationships")
            .delete()
            .eq("document_id", document_id)
            .execute()
        )
        (
            client.table("document_entities")
            .delete()
            .eq("document_id", document_id)
            .eq("user_id", user_id)
            .execute()
        )
    except Exception as exc:
        _raise_supabase_query_error("document graph rows clear", exc)


def insert_document_entities(
    document_id: str,
    entities: list[EntityDraft],
) -> list[dict]:
    if not entities:
        return []

    client = get_supabase_client()
    user_id = _get_single_user_id()
    rows = [_entity_insert_row(entity, document_id, user_id) for entity in entities]

    try:
        response = client.table("document_entities").insert(rows).execute()
    except Exception as exc:
        _raise_supabase_query_error("document entity insert", exc)

    return _response_rows(response)


def find_document_entity(
    document_id: str,
    entity_name: str,
    entity_type: str,
) -> dict | None:
    client = get_supabase_client()
    normalized_name = entity_name.strip()

    try:
        response = (
            client.table("document_entities")
            .select("*")
            .eq("document_id", document_id)
            .eq("user_id", _get_single_user_id())
            .eq("entity_name", normalized_name)
            .eq("entity_type", entity_type)
            .limit(1)
            .execute()
        )
    except Exception as exc:
        _raise_supabase_query_error("document entity lookup", exc)

    rows = _response_rows(response)
    if not rows:
        return None

    return rows[0]


def insert_document_relationships(
    document_id: str,
    relationships: list[RelationshipDraft],
) -> list[dict]:
    if not relationships:
        return []

    client = get_supabase_client()
    rows = [
        _relationship_insert_row(relationship, document_id)
        for relationship in relationships
    ]

    try:
        response = client.table("document_relationships").insert(rows).execute()
    except Exception as exc:
        _raise_supabase_query_error("document relationship insert", exc)

    return _response_rows(response)


def get_chunk_content_by_ids(chunk_ids: list[str]) -> dict[str, str | None]:
    if not chunk_ids:
        return {}

    client = get_supabase_client()

    try:
        response = (
            client.table("document_chunks")
            .select("id, content")
            .in_("id", chunk_ids)
            .eq("user_id", _get_single_user_id())
            .execute()
        )
    except Exception as exc:
        _raise_supabase_query_error("document chunk content lookup", exc)

    return {
        str(row["id"]): row.get("content")
        for row in _response_rows(response)
        if row.get("id") is not None
    }


def update_chunk_qdrant_point_id(
    document_id: str,
    chunk_id: str,
    qdrant_point_id: str,
) -> dict:
    client = get_supabase_client()

    try:
        response = (
            client.table("document_chunks")
            .update({"qdrant_point_id": qdrant_point_id})
            .eq("id", chunk_id)
            .eq("document_id", document_id)
            .eq("user_id", _get_single_user_id())
            .execute()
        )
    except Exception as exc:
        _raise_supabase_query_error("document chunk qdrant point update", exc)

    return _first_response_row("document chunk qdrant point update", response)


def update_document_status(
    document_id: str,
    status: str,
    *,
    error_message: str | None = None,
) -> dict:
    client = get_supabase_client()

    try:
        response = (
            client.table("documents")
            .update({"status": status, "error_message": error_message})
            .eq("id", document_id)
            .eq("user_id", _get_single_user_id())
            .execute()
        )
    except Exception as exc:
        _raise_supabase_query_error("document status update", exc)

    return _first_response_row("document status update", response)


def update_document_chunk_count(document_id: str, chunk_count: int) -> dict:
    client = get_supabase_client()

    try:
        response = (
            client.table("documents")
            .update({"chunk_count": chunk_count})
            .eq("id", document_id)
            .eq("user_id", _get_single_user_id())
            .execute()
        )
    except Exception as exc:
        _raise_supabase_query_error("document chunk count update", exc)

    return _first_response_row("document chunk count update", response)
