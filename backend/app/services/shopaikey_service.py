import json
from typing import Any, TypeVar

import httpx

from app.core.config import get_settings


EMBEDDING_REQUEST_TIMEOUT_SECONDS = 30.0
CHAT_COMPLETION_REQUEST_TIMEOUT_SECONDS = 60.0
CHAT_COMPLETION_MAX_ATTEMPTS = 2
CandidateT = TypeVar("CandidateT")
RERANK_SYSTEM_PROMPT = (
    "You are a RAG reranker. Rank candidate chunks by relevance to the user's "
    "question from most relevant to least relevant. Return only JSON matching "
    '{"ranked_chunk_ids":["uuid_1","uuid_2"]}. Use only the provided chunk_id '
    "values and include every relevant candidate before less relevant ones."
)


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

    if not candidates or top_n <= 0:
        return []

    try:
        rerank_settings = settings.require_shopaikey_rerank_settings()
    except RuntimeError as exc:
        raise ShopAIKeyServiceError(str(exc)) from exc

    request_payload = {
        "model": rerank_settings["rerank_model"],
        "messages": [
            {
                "role": "system",
                "content": RERANK_SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": (
                    "Please process the following reranking request and return the result in json format: "
                    + json.dumps(
                        {
                            "question": question,
                            "top_n": top_n,
                            "candidates": [
                                _rerank_candidate_payload(candidate)
                                for candidate in candidates
                            ],
                        },
                        ensure_ascii=False,
                    )
                ),
            },
        ],
        "response_format": {"type": "json_object"},
    }

    for attempt in range(CHAT_COMPLETION_MAX_ATTEMPTS):
        try:
            response = httpx.post(
                _chat_completions_url(rerank_settings["base_url"]),
                headers={
                    "Authorization": f"Bearer {rerank_settings['api_key']}",
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
            raise ShopAIKeyServiceError("ShopAIKey rerank request timed out.") from exc
        except httpx.RequestError as exc:
            if attempt + 1 < CHAT_COMPLETION_MAX_ATTEMPTS:
                continue
            raise ShopAIKeyServiceError("ShopAIKey rerank request failed.") from exc
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
                f"ShopAIKey rerank request failed with status {status_code}."
            ) from exc

    try:
        response_payload = response.json()
    except ValueError as exc:
        raise ShopAIKeyServiceError(
            "ShopAIKey rerank response contained malformed JSON."
        ) from exc

    response_content = _extract_chat_completion_content(response_payload)
    ranked_chunk_ids = _extract_ranked_chunk_ids(response_content)
    return _order_candidates_by_ranked_ids(
        candidates,
        ranked_chunk_ids,
    )[:top_n]


def _rerank_candidate_payload(candidate: Any) -> dict[str, Any]:
    chunk_id = _candidate_value(candidate, "chunk_id")
    if chunk_id is None:
        raise ShopAIKeyServiceError("Rerank candidate did not include a chunk_id.")

    return {
        "chunk_id": str(chunk_id),
        "content": _candidate_value(candidate, "content")
        or _candidate_value(candidate, "content_preview"),
        "file_name": _candidate_value(candidate, "file_name"),
        "page_number": _candidate_value(candidate, "page_number"),
        "section_title": _candidate_value(candidate, "section_title"),
        "chunk_index": _candidate_value(candidate, "chunk_index"),
        "semantic_similarity": _candidate_value(candidate, "semantic_similarity"),
        "graph_relevance": _candidate_value(candidate, "graph_relevance"),
        "keyword_overlap": _candidate_value(candidate, "keyword_overlap"),
        "metadata_match": _candidate_value(candidate, "metadata_match"),
        "recency_or_position_score": _candidate_value(
            candidate,
            "recency_or_position_score",
        ),
        "final_score": _candidate_value(candidate, "final_score"),
        "retrieval_reason": _candidate_value(candidate, "retrieval_reason"),
    }


def _candidate_value(candidate: Any, key: str) -> Any:
    if isinstance(candidate, dict):
        return candidate.get(key)

    return getattr(candidate, key, None)


def _extract_ranked_chunk_ids(response_content: str) -> list[str]:
    try:
        payload = json.loads(response_content)
    except ValueError as exc:
        raise ShopAIKeyServiceError(
            "ShopAIKey rerank response contained malformed JSON."
        ) from exc

    if not isinstance(payload, dict):
        raise ShopAIKeyServiceError(
            "ShopAIKey rerank response did not include ranked chunk IDs."
        )

    ranked_chunk_ids = payload.get("ranked_chunk_ids")
    if not isinstance(ranked_chunk_ids, list) or not all(
        isinstance(chunk_id, str) for chunk_id in ranked_chunk_ids
    ):
        raise ShopAIKeyServiceError(
            "ShopAIKey rerank response did not include ranked chunk IDs."
        )

    return ranked_chunk_ids


def _order_candidates_by_ranked_ids(
    candidates: list[CandidateT],
    ranked_chunk_ids: list[str],
) -> list[CandidateT]:
    candidates_by_chunk_id = {
        str(_candidate_value(candidate, "chunk_id")): candidate for candidate in candidates
    }
    ordered_candidates: list[CandidateT] = []
    seen_chunk_ids: set[str] = set()

    for chunk_id in ranked_chunk_ids:
        candidate = candidates_by_chunk_id.get(chunk_id)
        if candidate is None or chunk_id in seen_chunk_ids:
            continue

        ordered_candidates.append(candidate)
        seen_chunk_ids.add(chunk_id)

    for candidate in candidates:
        chunk_id = str(_candidate_value(candidate, "chunk_id"))
        if chunk_id not in seen_chunk_ids:
            ordered_candidates.append(candidate)
            seen_chunk_ids.add(chunk_id)

    return ordered_candidates


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


def _ensure_json_word_in_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    processed = [dict(msg) for msg in messages]
    has_lowercase_json = False
    for msg in processed:
        content = msg.get("content", "")
        if isinstance(content, str) and "json" in content:
            has_lowercase_json = True
            break

    if not has_lowercase_json:
        system_msg = next((m for m in processed if m.get("role") == "system"), None)
        if system_msg and isinstance(system_msg.get("content"), str):
            system_msg["content"] += "\n\nNote: Return response in json format."
        elif processed and isinstance(processed[-1].get("content"), str):
            processed[-1]["content"] += "\n\nNote: Return response in json format."

    return processed



def chat_completion(
    messages: list[dict[str, Any]],
    response_format: dict[str, Any] | None = None,
) -> str:
    try:
        settings = get_settings().require_shopaikey_chat_settings()
    except RuntimeError as exc:
        raise ShopAIKeyServiceError(str(exc)) from exc

    processed_messages = messages
    if response_format and response_format.get("type") == "json_object":
        processed_messages = _ensure_json_word_in_messages(messages)

    request_payload: dict[str, Any] = {
        "model": settings["chat_model"],
        "messages": processed_messages,
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
