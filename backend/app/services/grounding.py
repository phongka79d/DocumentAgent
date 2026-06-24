from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import ValidationError

from app.core.config import Settings, get_settings
from app.core.retry import RetryAttempt, retry_sync
from app.rag.formatting import extract_chat_content, normalize_text
from app.rag.prompts import build_grounding_messages
from app.models.schemas import GroundingResult
from app.services.citation_validation import assign_citation_keys
from app.services.shopaikey_client import create_shopaikey_client


class GroundingProviderError(RuntimeError):
    """Raised when grounding verification cannot produce a valid strict result."""


def _resolve_settings(settings: Settings | None = None) -> Settings:
    return settings if settings is not None else get_settings()


def cited_evidence_from_sources(
    *,
    context_chunks: Sequence[Mapping[str, Any]],
    cited_keys: Sequence[str],
) -> list[dict[str, str]]:
    keyed_context = assign_citation_keys(context_chunks)
    by_key = {
        str(chunk["citation_key"]): chunk
        for chunk in keyed_context
        if normalize_text(chunk.get("chunk_id") or chunk.get("id")) is not None
    }

    evidence: list[dict[str, str]] = []
    seen: set[str] = set()
    for key in cited_keys:
        if key in seen:
            continue
        seen.add(key)
        chunk = by_key.get(str(key))
        if chunk is None:
            continue
        chunk_id = normalize_text(chunk.get("chunk_id") or chunk.get("id"))
        text = normalize_text(chunk.get("content") or chunk.get("text"))
        if chunk_id is None or text is None:
            continue
        evidence.append(
            {
                "citation_key": str(key),
                "chunk_id": chunk_id,
                "text": text,
            }
        )
    return evidence


def _parse_grounding_result(content: str | None) -> GroundingResult:
    if content is None:
        raise GroundingProviderError("Grounding verifier returned empty content")
    payload = _extract_json_object(content)
    if payload is None:
        raise GroundingProviderError("Grounding verifier returned invalid JSON")
    try:
        return GroundingResult.model_validate(payload)
    except (ValidationError, TypeError) as exc:
        raise GroundingProviderError("Grounding verifier returned invalid JSON") from exc


def _extract_json_object(content: str) -> Any:
    text = content.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    decoder = json.JSONDecoder()
    for index, character in enumerate(text):
        if character != "{":
            continue
        try:
            payload, _ = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        return payload
    return None


def verify_answer_grounding(
    answer: str,
    *,
    evidence: Sequence[Mapping[str, Any]],
    settings: Settings | None = None,
    shopaikey_client: Any | None = None,
    retry_attempts: list[RetryAttempt] | None = None,
) -> GroundingResult:
    resolved_settings = _resolve_settings(settings)
    try:
        client = (
            shopaikey_client
            if shopaikey_client is not None
            else create_shopaikey_client(resolved_settings)
        )
        response = retry_sync(
            "grounding_verification",
            lambda: client.chat.completions.create(
                model=resolved_settings.SHOPAIKEY_INPUT_MODEL,
                messages=build_grounding_messages(answer=answer, evidence=evidence),
                temperature=0,
                max_tokens=resolved_settings.QUERY_PLANNER_MAX_TOKENS,
                response_format={"type": "json_object"},
            ),
            settings=resolved_settings,
            on_attempt=retry_attempts.append if retry_attempts is not None else None,
        )
    except Exception as exc:
        raise GroundingProviderError("Grounding verifier provider failure") from exc

    return _parse_grounding_result(extract_chat_content(response))


__all__ = [
    "GroundingProviderError",
    "cited_evidence_from_sources",
    "verify_answer_grounding",
]
