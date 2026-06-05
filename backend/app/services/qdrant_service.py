from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams

from app.core.config import get_settings


class QdrantSetupError(RuntimeError):
    """Raised when Qdrant collection setup is missing or incompatible."""


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

    if not client.collection_exists(collection_name):
        client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
        )
        return

    collection = client.get_collection(collection_name)
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
