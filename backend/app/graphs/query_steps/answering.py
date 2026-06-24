from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.core.config import Settings
from app.core.retry import RetryAttempt, retry_sync
from app.graphs.query_steps.dependencies import QueryStepDependencies
from app.rag.formatting import normalize_text
from app.rag.formatting import resolve_context_chunks
from app.rag.prompts import ANSWER_SYSTEM_PROMPT, ANSWER_USER_PROMPT_TEMPLATE
from app.rag.prompts import NO_RELEVANT_INFORMATION_MESSAGE
from app.rag.prompts import build_answer_messages, build_regeneration_messages


DEFAULT_QUERY_ERROR = "Query failed"


def _resolve_settings(settings: Settings | None = None) -> Settings:
    from app.core.config import get_settings

    return settings if settings is not None else get_settings()


def _question_text(state: Mapping[str, Any]) -> str | None:
    return normalize_text(state.get("prepared_query") or state.get("question"))


def generate_answer_node(
    state: Mapping[str, Any],
    *,
    settings: Settings | None = None,
    deps: QueryStepDependencies,
    shopaikey_client: Any | None = None,
) -> dict[str, Any]:
    resolved_settings = _resolve_settings(settings)
    question = _question_text(state)
    if question is None:
        return {"error_message": "prepared_query is required"}

    context_chunks = resolve_context_chunks(state)
    if not context_chunks:
        return {
            "answer": NO_RELEVANT_INFORMATION_MESSAGE,
            "sources": [],
        }

    try:
        client = (
            shopaikey_client
            if shopaikey_client is not None
            else deps.create_shopaikey_client(resolved_settings)
        )
        context_chunks = deps.citation_validation.assign_citation_keys(context_chunks)
        context = deps.build_context_prompt(context_chunks)
        attempts: list[RetryAttempt] = []
        response = retry_sync(
            "answer_generation",
            lambda: client.chat.completions.create(
                model=resolved_settings.SHOPAIKEY_CHAT_MODEL,
                messages=build_answer_messages(context=context, question=question),
                temperature=resolved_settings.TEMPERATURE,
                max_tokens=resolved_settings.MAX_OUTPUT_TOKENS,
            ),
            settings=resolved_settings,
            on_attempt=attempts.append,
        )
        answer = deps.extract_chat_content(response)
        if answer is None:
            return {
                "error_message": "Chat completion returned empty content",
            }
        return {
            "answer": answer,
            "sources": deps.build_source_citations(context_chunks),
            "retrieval_metrics": {},
        }
    except Exception as exc:
        return {
            "error_message": f"Failed to generate answer: {exc}",
        }


def _compact_grounding_feedback(state: Mapping[str, Any]) -> str:
    validation = state.get("citation_validation_result")
    result = state.get("grounding_result")
    parts: list[str] = []
    if validation is not None and not getattr(validation, "valid", False):
        invalid_keys = getattr(validation, "invalid_keys", [])
        if invalid_keys:
            parts.append(f"Invalid citation keys: {', '.join(invalid_keys)}.")
        if getattr(validation, "missing_citations", False):
            parts.append("Factual claims need valid [S<number>] citations.")
    if result is not None:
        unsupported = getattr(result, "unsupported_claims", [])
        missing = getattr(result, "missing_citations", [])
        if unsupported:
            parts.append(f"Unsupported claims: {'; '.join(unsupported[:3])}.")
        if missing:
            parts.append(f"Missing citations: {'; '.join(missing[:3])}.")
    return " ".join(parts) or "Previous answer was not verified. Use only cited context."


def regenerate_answer_node(
    state: Mapping[str, Any],
    *,
    settings: Settings | None = None,
    deps: QueryStepDependencies,
    shopaikey_client: Any | None = None,
) -> dict[str, Any]:
    resolved_settings = _resolve_settings(settings)
    question = _question_text(state)
    if question is None:
        return {"error_message": "prepared_query is required"}

    context_chunks = resolve_context_chunks(state)
    if not context_chunks:
        return {
            "answer": NO_RELEVANT_INFORMATION_MESSAGE,
            "sources": [],
        }

    try:
        client = (
            shopaikey_client
            if shopaikey_client is not None
            else deps.create_shopaikey_client(resolved_settings)
        )
        context_chunks = deps.citation_validation.assign_citation_keys(context_chunks)
        context = deps.build_context_prompt(context_chunks)
        attempts: list[RetryAttempt] = []
        response = retry_sync(
            "answer_regeneration",
            lambda: client.chat.completions.create(
                model=resolved_settings.SHOPAIKEY_CHAT_MODEL,
                messages=build_regeneration_messages(
                    context=context,
                    question=question,
                    feedback=_compact_grounding_feedback(state),
                ),
                temperature=resolved_settings.TEMPERATURE,
                max_tokens=resolved_settings.MAX_OUTPUT_TOKENS,
            ),
            settings=resolved_settings,
            on_attempt=attempts.append,
        )
        answer = deps.extract_chat_content(response)
        if answer is None:
            return {
                "error_message": "Chat completion returned empty content",
            }
        return {
            "answer": answer,
            "sources": deps.build_source_citations(context_chunks),
            "retrieval_metrics": {},
        }
    except Exception as exc:
        return {
            "error_message": f"Failed to regenerate answer: {exc}",
        }
