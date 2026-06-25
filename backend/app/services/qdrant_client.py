from collections.abc import Iterable, Mapping
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.http import models as qdrant_models

from app.core import config as config_module
from app.core.config import Settings
from app.core.contracts import QdrantPayloadKey


# Typed payload-index registry for filterable Qdrant fields.
# Maps payload field keys to their required Qdrant payload schema types.
FILTERABLE_PAYLOAD_INDEXES: dict[str, qdrant_models.PayloadSchemaType] = {
    QdrantPayloadKey.DOCUMENT_ID: qdrant_models.PayloadSchemaType.KEYWORD,
    QdrantPayloadKey.MIME_TYPE: qdrant_models.PayloadSchemaType.KEYWORD,
    QdrantPayloadKey.HEADING: qdrant_models.PayloadSchemaType.TEXT,
    QdrantPayloadKey.SECTION_PATH: qdrant_models.PayloadSchemaType.KEYWORD,
    QdrantPayloadKey.PAGE_START: qdrant_models.PayloadSchemaType.INTEGER,
    QdrantPayloadKey.PAGE_END: qdrant_models.PayloadSchemaType.INTEGER,
    QdrantPayloadKey.CHUNK_TYPE: qdrant_models.PayloadSchemaType.KEYWORD,
}


def _resolve_settings(settings: Settings | None = None) -> Settings:
    return settings if settings is not None else config_module.get_settings()


def create_qdrant_client(settings: Settings | None = None) -> QdrantClient:
    resolved_settings = _resolve_settings(settings)
    api_key = resolved_settings.QDRANT_API_KEY.strip() or None
    return QdrantClient(
        url=resolved_settings.QDRANT_URL,
        api_key=api_key,
        check_compatibility=False,
    )


def get_qdrant_payload_schema(
    client: Any,
    collection_name: str,
) -> dict[str, int]:
    """Inspect a Qdrant collection and return its existing payload schema.

    Returns a dict mapping field names to their PayloadSchemaType integer values.
    Returns an empty dict if the collection does not exist.
    """
    try:
        info = client.get_collection(collection_name)
    except Exception:
        return {}

    if info is None:
        return {}

    # The payload_schema may be accessible as an attribute or via model_dump
    payload_schema: dict[str, Any] = {}
    if hasattr(info, "payload_schema"):
        raw = info.payload_schema
        if isinstance(raw, dict):
            payload_schema = dict(raw)
        elif isinstance(raw, Iterable):
            for item in raw:
                if hasattr(item, "name") and hasattr(item, "data_type"):
                    payload_schema[item.name] = item.data_type
    elif isinstance(info, Mapping):
        raw = info.get("payload_schema") or {}
        if isinstance(raw, dict):
            payload_schema = dict(raw)

    result: dict[str, int] = {}
    for field_name, schema_info in payload_schema.items():
        if isinstance(schema_info, Mapping):
            data_type = schema_info.get("data_type")
            if data_type is not None:
                result[str(field_name)] = int(data_type)
        elif hasattr(schema_info, "data_type"):
            result[str(field_name)] = int(schema_info.data_type)
        elif isinstance(schema_info, int):
            result[str(field_name)] = schema_info
    return result


def ensure_qdrant_payload_indexes(
    client: Any,
    collection_name: str,
    field_names: Iterable[str] | None = None,
) -> list[str]:
    """Ensure the specified payload indexes exist on a Qdrant collection.

    Inspects the collection's existing payload schema and creates any missing
    indexes defined in FILTERABLE_PAYLOAD_INDEXES. Returns a list of field names
    that were created.

    If the collection does not exist, returns an empty list without creating it.
    Missing collections are not created implicitly because vector dimension and
    distance configuration remain deployment-owned.
    """
    if field_names is not None:
        requested = set(field_names)
        fields_to_ensure = {
            name: schema_type
            for name, schema_type in FILTERABLE_PAYLOAD_INDEXES.items()
            if name in requested
        }
    else:
        fields_to_ensure = dict(FILTERABLE_PAYLOAD_INDEXES)

    if not fields_to_ensure:
        return []

    existing_schema = get_qdrant_payload_schema(client, collection_name)
    if not existing_schema:
        # Collection doesn't exist or has no payload schema
        return []

    created: list[str] = []
    for field_name, schema_type in fields_to_ensure.items():
        if field_name not in existing_schema:
            client.create_payload_index(
                collection_name=collection_name,
                field_name=field_name,
                field_type=schema_type,
                wait=True,
            )
            created.append(field_name)
    return created


def ensure_qdrant_filter_indexes(
    client: Any,
    collection_name: str,
    filters: Mapping[str, Any] | None,
) -> None:
    """Ensure payload indexes exist for active retrieval filters.

    Wraps ensure_qdrant_payload_indexes for convenience. Logs failures but does
    not raise, so that a missing index does not block the query path.
    """
    if not filters:
        return

    active_filter_fields: set[str] = set()
    for key, value in filters.items():
        if value is not None and value != [] and value != "":
            active_filter_fields.add(key)

    if not active_filter_fields:
        return

    try:
        ensure_qdrant_payload_indexes(
            client,
            collection_name=collection_name,
            field_names=active_filter_fields,
        )
    except Exception:
        import logging
        logging.getLogger(__name__).warning(
            "Failed to ensure Qdrant payload indexes for fields %s on collection %s",
            active_filter_fields,
            collection_name,
        )

