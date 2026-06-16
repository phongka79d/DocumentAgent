from typing import Any, TypeVar

import httpx

from app.core.config import get_settings


EMBEDDING_REQUEST_TIMEOUT_SECONDS = 30.0
CHAT_COMPLETION_REQUEST_TIMEOUT_SECONDS = 60.0
CHAT_COMPLETION_MAX_ATTEMPTS = 2
CandidateT = TypeVar("CandidateT")


class ShopAIKeyServiceError(RuntimeError):
    """Raised when the ShopAIKey provider cannot return a usable response."""


def _embeddings_url(base_url: str) -> str:
    return f"{base_url.rstrip('/')}/embeddings"


def _chat_completions_url(base_url: str) -> str:
    return f"{base_url.rstrip('/')}/chat/completions"


def _is_retryable_chat_status(status_code: int) -> bool:
    return status_code in {408, 429} or status_code >= 500


def estimate_chat_messages_chars(messages: list[dict[str, Any]]) -> int:
    return sum(len(str(message.get("content", ""))) for message in messages)


def rerank_candidates(
    question: str,
    candidates: list[CandidateT],
    *,
    top_n: int,
) -> list[CandidateT]:
    settings = get_settings()
    if not getattr(settings, "enable_rerank", False):
        return candidates

    try:
        settings.require_shopaikey_rerank_settings()
    except RuntimeError as exc:
        raise ShopAIKeyServiceError(str(exc)) from exc

    raise ShopAIKeyServiceError(
        "ShopAIKey rerank is not implemented. Disable ENABLE_RERANK to return hybrid candidates without rerank."
    )


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


def _extract_chat_completion_content(response_payload: dict[str, Any]) -> str:
    try:
        content = response_payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ShopAIKeyServiceError(
            "ShopAIKey chat completion response did not include chat completion content."
        ) from exc

    if not isinstance(content, str):
        raise ShopAIKeyServiceError(
            "ShopAIKey chat completion response did not include chat completion content."
        )

    return content


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


def chat_completion(
    messages: list[dict[str, Any]],
    response_format: dict[str, Any] | None = None,
) -> str:
    try:
        settings = get_settings().require_shopaikey_chat_settings()
    except RuntimeError as exc:
        raise ShopAIKeyServiceError(str(exc)) from exc

    request_payload: dict[str, Any] = {
        "model": settings["chat_model"],
        "messages": messages,
    }
    if response_format is not None:
        request_payload["response_format"] = response_format

    for attempt in range(CHAT_COMPLETION_MAX_ATTEMPTS):
        try:
            response = httpx.post(
                _chat_completions_url(settings["base_url"]),
                headers={
                    "Authorization": f"Bearer {settings['api_key']}",
                    "Content-Type": "application/json",
                },
                json=request_payload,
                timeout=CHAT_COMPLETION_REQUEST_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            break
        except httpx.TimeoutException as exc:
            if attempt + 1 < CHAT_COMPLETION_MAX_ATTEMPTS:
                continue
            raise ShopAIKeyServiceError(
                "ShopAIKey chat completion request timed out."
            ) from exc
        except httpx.RequestError as exc:
            if attempt + 1 < CHAT_COMPLETION_MAX_ATTEMPTS:
                continue
            raise ShopAIKeyServiceError(
                "ShopAIKey chat completion request failed."
            ) from exc
        except httpx.HTTPStatusError as exc:
            status_code = (
                exc.response.status_code
                if exc.response is not None
                else "unknown"
            )
            if (
                isinstance(status_code, int)
                and _is_retryable_chat_status(status_code)
                and attempt + 1 < CHAT_COMPLETION_MAX_ATTEMPTS
            ):
                continue
            raise ShopAIKeyServiceError(
                f"ShopAIKey chat completion request failed with status {status_code}."
            ) from exc

    try:
        response_payload = response.json()
    except ValueError as exc:
        raise ShopAIKeyServiceError(
            "ShopAIKey chat completion response contained malformed JSON."
        ) from exc

    return _extract_chat_completion_content(response_payload)
