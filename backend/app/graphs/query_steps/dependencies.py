from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class QueryStepDependencies:
    retrieval: Any
    retrieval_context: Any
    query_planning: Any
    relations: Any
    grounding: Any
    citation_validation: Any
    message_service: Any
    build_context_prompt: Callable[..., str]
    build_source_citations: Callable[..., list[dict[str, Any]]]
    extract_chat_content: Callable[..., str | None]
    message_metadata: Callable[..., dict[str, Any]]
    create_shopaikey_client: Callable[..., Any]
