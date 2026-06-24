from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

from app.core.config import Settings
from app.graphs.query_steps.dependencies import QueryStepDependencies
from app.rag.formatting import normalize_text, resolve_context_chunks

logger = logging.getLogger(__name__)


def _resolve_settings(settings: Settings | None = None) -> Settings:
    from app.core.config import get_settings

    return settings if settings is not None else get_settings()


def save_message_optional_node(
    state: Mapping[str, Any],
    *,
    settings: Settings | None = None,
    deps: QueryStepDependencies,
    supabase_client: Any | None = None,
) -> dict[str, Any]:
    resolved_settings = _resolve_settings(settings)
    if not state.get("save_message"):
        return {}

    question = normalize_text(state.get("prepared_query") or state.get("question"))
    answer = normalize_text(state.get("answer"))
    if question is None or answer is None:
        return {}

    try:
        sources = state.get("sources")
        if isinstance(sources, list):
            normalized_sources = [
                dict(source) for source in sources if isinstance(source, Mapping)
            ]
        else:
            normalized_sources = deps.build_source_citations(resolve_context_chunks(state))

        deps.message_service.create_message(
            question=question,
            answer=answer,
            sources=normalized_sources,
            metadata=deps.message_metadata(state),
            settings=resolved_settings,
            supabase_client=supabase_client,
        )
    except Exception as exc:
        logger.warning("Message save failed: %s", exc)
    return {}
