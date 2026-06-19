from __future__ import annotations

from typing import Any, TypedDict


class QueryState(TypedDict, total=False):
    question: str
    document_ids: list[str]
    save_message: bool

    prepared_query: str
    query_embedding: list[float]
    retrieval_hints: dict[str, list[str]]

    retrieved_chunks: list[dict[str, Any]]
    reranked_chunks: list[dict[str, Any]]
    context_chunks: list[dict[str, Any]]

    answer: str
    sources: list[dict[str, Any]]

    error_message: str | None
