from typing import Any

import httpx

from app.core.config import get_settings


EMBEDDING_REQUEST_TIMEOUT_SECONDS = 30.0


class ShopAIKeyServiceError(RuntimeError):
    """Raised when the ShopAIKey embedding provider cannot return a usable vector."""


def _embeddings_url(base_url: str) -> str:
    return f"{base_url.rstrip('/')}/embeddings"


def _extract_embedding(response_payload: dict[str, Any]) -> list[float]:
    try:
        embedding = response_payload["data"][0]["embedding"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ShopAIKeyServiceError(
            "ShopAIKey embedding response did not include an embedding vector."
        ) from exc

    if not isinstance(embedding, list) or not all(
        isinstance(value, int | float) for value in embedding
    ):
        raise ShopAIKeyServiceError(
            "ShopAIKey embedding response did not include a numeric embedding vector."
        )

    return [float(value) for value in embedding]


def create_embedding(text: str) -> list[float]:
    try:
        settings = get_settings().require_shopaikey_settings()
    except RuntimeError as exc:
        raise ShopAIKeyServiceError(str(exc)) from exc

    try:
        response = httpx.post(
            _embeddings_url(settings["base_url"]),
            headers={
                "Authorization": f"Bearer {settings['api_key']}",
            },
            json={
                "model": settings["embedding_model"],
                "input": text,
            },
            timeout=EMBEDDING_REQUEST_TIMEOUT_SECONDS,
        )
    except httpx.TimeoutException as exc:
        raise ShopAIKeyServiceError("ShopAIKey embedding request timed out.") from exc
    except httpx.RequestError as exc:
        raise ShopAIKeyServiceError("ShopAIKey embedding request failed.") from exc

    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        status_code = exc.response.status_code if exc.response is not None else "unknown"
        raise ShopAIKeyServiceError(
            f"ShopAIKey embedding request failed with status {status_code}."
        ) from exc

    try:
        response_payload = response.json()
    except ValueError as exc:
        raise ShopAIKeyServiceError(
            "ShopAIKey embedding response contained malformed JSON."
        ) from exc

    return _extract_embedding(response_payload)
