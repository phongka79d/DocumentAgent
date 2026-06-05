from json import loads
from typing import Any
from uuid import UUID

from qdrant_client import QdrantClient
from qdrant_client.http.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchAny,
    MatchValue,
    PointStruct,
    ScoredPoint,
    VectorParams,
)

from app.core.config import get_settings
from app.schemas.embeddings import IndexedChunkPayload


class QdrantSetupError(RuntimeError):
    """Raised when Qdrant collection setup is missing or incompatible."""


class QdrantUpsertError(RuntimeError):
    """Raised when a Qdrant point upsert fails."""


def get_qdrant_client() -> QdrantClient:
    try:
        settings = get_settings().require_qdrant_settings()
    except RuntimeError as exc:
        raise QdrantSetupError(str(exc)) from exc

    return QdrantClient(
        url=settings["url"],
        api_key=settings["api_key"],
    )


def ensure_collection(vector_size: int) -> None:
    if vector_size <= 0:
        raise QdrantSetupError("Qdrant collection vector size must be greater than zero.")

    try:
        settings = get_settings().require_qdrant_settings()
    except RuntimeError as exc:
        raise QdrantSetupError(str(exc)) from exc
    collection_name = settings["collection"]
    client = get_qdrant_client()

    try:
        collection_exists = client.collection_exists(collection_name)
    except Exception as exc:
        raise QdrantSetupError("Qdrant collection check failed.") from exc

    if not collection_exists:
        try:
            client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
            )
        except Exception as exc:
            raise QdrantSetupError("Qdrant collection creation failed.") from exc
        return

    try:
        collection = client.get_collection(collection_name)
    except Exception as exc:
        raise QdrantSetupError("Qdrant collection configuration lookup failed.") from exc

    existing_vector = _extract_vector_params(collection)
    existing_size = _get_vector_value(existing_vector, "size")
    existing_distance = _get_vector_value(existing_vector, "distance")

    if existing_size != vector_size:
        raise QdrantSetupError(
            f"Qdrant collection '{collection_name}' has incompatible vector size "
            f"{existing_size}; expected {vector_size}. Please verify collection setup."
        )

    if _normalize_distance(existing_distance) != _normalize_distance(Distance.COSINE):
        raise QdrantSetupError(
            f"Qdrant collection '{collection_name}' has incompatible distance "
            f"{existing_distance}; expected {Distance.COSINE}. Please verify collection setup."
        )


def build_chunk_payload(
    *,
    user_id: str,
    document_id: UUID | str,
    chunk_id: UUID | str,
    file_name: str,
    file_type: str,
    page_number: int | None,
    section_title: str | None,
    chunk_index: int,
    content: str,
) -> IndexedChunkPayload:
    return IndexedChunkPayload(
        user_id=user_id,
        document_id=document_id,
        chunk_id=chunk_id,
        file_name=file_name,
        file_type=file_type,
        page_number=page_number,
        section_title=section_title,
        chunk_index=chunk_index,
        content_preview=content[:500],
    )


def upsert_chunk_vector(
    point_id: str,
    vector: list[float],
    payload: IndexedChunkPayload,
) -> str:
    if not point_id:
        raise QdrantUpsertError("Qdrant point ID is required for chunk vector upsert.")

    try:
        settings = get_settings().require_qdrant_settings()
    except RuntimeError as exc:
        raise QdrantUpsertError(str(exc)) from exc

    point = PointStruct(
        id=point_id,
        vector=vector,
        payload=_payload_to_qdrant(payload),
    )

    try:
        get_qdrant_client().upsert(
            collection_name=settings["collection"],
            points=[point],
        )
    except Exception as exc:
        if _looks_like_vector_size_error(exc):
            raise QdrantSetupError(
                "Qdrant vector-size mismatch during chunk vector upsert. "
                "Please verify collection setup."
            ) from exc
        raise QdrantUpsertError("Qdrant chunk vector upsert failed.") from exc

    return point_id


def search_vectors(
    query_vector: list[float],
    top_k: int,
    document_ids: list[UUID | str] | None = None,
) -> list[ScoredPoint]:
    try:
        settings = get_settings()
        qdrant_settings = settings.require_qdrant_settings()
    except RuntimeError as exc:
        raise QdrantSetupError(str(exc)) from exc

    filter_conditions = [
        FieldCondition(
            key="user_id",
            match=MatchValue(value=settings.single_user_id),
        )
    ]
    if document_ids:
        filter_conditions.append(
            FieldCondition(
                key="document_id",
                match=MatchAny(any=[str(document_id) for document_id in document_ids]),
            )
        )

    query_filter = Filter(must=filter_conditions)

    response = get_qdrant_client().query_points(
        collection_name=qdrant_settings["collection"],
        query=query_vector,
        query_filter=query_filter,
        limit=top_k,
        with_payload=True,
    )
    return response.points


def _payload_to_qdrant(payload: IndexedChunkPayload) -> dict[str, Any]:
    if hasattr(payload, "model_dump"):
        data = payload.model_dump(mode="json")
    else:
        data = loads(payload.json())

    return data


def _extract_vector_params(collection: Any) -> Any:
    vectors = collection.config.params.vectors
    if isinstance(vectors, dict):
        if len(vectors) != 1:
            raise QdrantSetupError(
                "Qdrant collection uses multiple named vectors; please verify collection setup."
            )
        return next(iter(vectors.values()))
    return vectors


def _get_vector_value(vector_params: Any, name: str) -> Any:
    if isinstance(vector_params, dict):
        return vector_params.get(name)
    return getattr(vector_params, name, None)


def _normalize_distance(distance: Any) -> str:
    value = getattr(distance, "value", distance)
    return str(value).lower()


def _looks_like_vector_size_error(exc: Exception) -> bool:
    message = str(exc).lower()
    vector_terms = ("vector", "dimension", "dimensions")
    size_terms = ("size", "dim", "expected")
    return any(term in message for term in vector_terms) and any(
        term in message for term in size_terms
    )
