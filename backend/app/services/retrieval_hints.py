from __future__ import annotations

import json
import logging
from collections.abc import Mapping, Sequence
from typing import Any

from app.core.config import Settings, get_settings
from app.core.contracts import RetrievalBoundary
from app.services.shopaikey_client import create_shopaikey_client

logger = logging.getLogger(__name__)


def _retrieval_boundary_schema_values() -> str:
    return "|".join(
        f'"{boundary.value}"'
        for boundary in (RetrievalBoundary.BEGINNING, RetrievalBoundary.END)
    )


RETRIEVAL_HINT_SYSTEM_PROMPT = (
    "You extract retrieval hints for a document RAG system.\n"
    "Return compact JSON only. No prose.\n"
    f"Use this schema: {{\"boundary_positions\": [{_retrieval_boundary_schema_values()}]}}.\n"
    "Use an empty list when the question does not ask about a document boundary."
)
RETRIEVAL_HINT_USER_PROMPT_TEMPLATE = "Question:\n{question}"
_RETRIEVAL_BOUNDARIES = {boundary.value for boundary in RetrievalBoundary}
def _empty_retrieval_hints() -> dict[str, list[str]]:
    return {"boundary_positions": []}


def _resolve_settings(settings: Settings | None = None) -> Settings:
    return settings if settings is not None else get_settings()


def _resolve_shopaikey_client(shopaikey_client: Any | None = None) -> Any:
    return (
        shopaikey_client
        if shopaikey_client is not None
        else create_shopaikey_client()
    )


def _normalize_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _extract_chat_content(response: Any) -> str | None:
    output_text = getattr(response, "output_text", None)
    normalized_output_text = _normalize_text(output_text)
    if normalized_output_text is not None:
        return normalized_output_text

    choices = getattr(response, "choices", None)
    if choices is None and isinstance(response, Mapping):
        choices = response.get("choices")
    if not choices:
        return None

    first_choice = choices[0]
    message = getattr(first_choice, "message", None)
    if message is None and isinstance(first_choice, Mapping):
        message = first_choice.get("message")
    if message is not None:
        content = getattr(message, "content", None)
        if content is None and isinstance(message, Mapping):
            content = message.get("content")
        normalized_content = _normalize_text(content)
        if normalized_content is not None:
            return normalized_content

    text = getattr(first_choice, "text", None)
    if text is None and isinstance(first_choice, Mapping):
        text = first_choice.get("text")
    return _normalize_text(text)


def _normalize_retrieval_hints(value: Any) -> dict[str, list[str]]:
    if not isinstance(value, Mapping):
        return {"boundary_positions": []}

    raw_positions = value.get("boundary_positions")
    if not isinstance(raw_positions, Sequence) or isinstance(raw_positions, (str, bytes)):
        return {"boundary_positions": []}

    positions: list[str] = []
    seen: set[str] = set()
    for raw_position in raw_positions:
        position = _normalize_text(raw_position)
        if position is None:
            continue
        position = position.lower()
        if position not in _RETRIEVAL_BOUNDARIES or position in seen:
            continue
        positions.append(position)
        seen.add(position)
    return {"boundary_positions": positions}


def extract_retrieval_hints(
    question: str,
    *,
    settings: Settings | None = None,
    shopaikey_client: Any | None = None,
) -> dict[str, list[str]]:
    resolved_settings = _resolve_settings(settings)
    normalized_question = _normalize_text(question)
    if normalized_question is None:
        raise ValueError("question is required")

    client = _resolve_shopaikey_client(shopaikey_client)
    chat = getattr(client, "chat", None)
    completions = getattr(chat, "completions", None) if chat is not None else None
    if completions is None:
        return _empty_retrieval_hints()

    try:
        response = completions.create(
            model=resolved_settings.SHOPAIKEY_CHAT_MODEL,
            messages=[
                {"role": "system", "content": RETRIEVAL_HINT_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": RETRIEVAL_HINT_USER_PROMPT_TEMPLATE.format(
                        question=normalized_question
                    ),
                },
            ],
            temperature=resolved_settings.RETRIEVAL_HINT_TEMPERATURE,
            max_tokens=resolved_settings.RETRIEVAL_HINT_MAX_TOKENS,
        )
        content = _extract_chat_content(response)
        if content is None:
            return _empty_retrieval_hints()
        return _normalize_retrieval_hints(json.loads(content))
    except Exception as exc:  # pragma: no cover - fallback is intentional
        logger.warning("Retrieval hint extraction failed: %s", exc)
        return _empty_retrieval_hints()
