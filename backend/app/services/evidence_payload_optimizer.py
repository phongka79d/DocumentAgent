from __future__ import annotations

import json

from app.agents.schemas import RetrievalCandidate
from app.services import shopaikey_service


OPTIMIZER_SYSTEM_PROMPT = (
    "You optimize RAG evidence payloads for verification. For each candidate "
    "chunk, extract the most relevant continuous sentence window or snippet "
    "that helps answer the user's question. The optimized_content must be "
    "copied from the candidate content, must not exceed snippet_max_chars, and "
    "must be null when the candidate has no usable content. Return only JSON "
    'matching {"optimized_snippets":[{"chunk_id":"string",'
    '"optimized_content":"string or null"}]}. Include one result for each '
    "candidate chunk_id."
)


def optimize_candidates_for_verification(
    *,
    question: str,
    candidates: list[RetrievalCandidate],
    max_candidates: int,
    snippet_max_chars: int,
    context_sentences: int,
) -> list[RetrievalCandidate]:
    selected_candidates = candidates[:max_candidates]
    if not selected_candidates:
        return []

    try:
        response_content = shopaikey_service.chat_completion(
            [
                {
                    "role": "system",
                    "content": OPTIMIZER_SYSTEM_PROMPT,
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "question": question,
                            "snippet_max_chars": snippet_max_chars,
                            "context_sentences": context_sentences,
                            "candidates": [
                                {
                                    "chunk_id": str(candidate.chunk_id),
                                    "content": candidate.content,
                                    "file_name": candidate.file_name,
                                    "page_number": candidate.page_number,
                                    "section_title": candidate.section_title,
                                    "chunk_index": candidate.chunk_index,
                                }
                                for candidate in selected_candidates
                            ],
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
            response_format={"type": "json_object"},
        )
        optimized_content_by_chunk_id = _parse_optimized_content(
            response_content,
            snippet_max_chars=snippet_max_chars,
        )
    except Exception:
        return _fallback_truncated_candidates(
            selected_candidates,
            snippet_max_chars=snippet_max_chars,
        )

    return [
        candidate.model_copy(
            update={
                "content": optimized_content_by_chunk_id.get(
                    str(candidate.chunk_id),
                    _truncate_content(candidate.content, snippet_max_chars),
                )
            }
        )
        for candidate in selected_candidates
    ]


def _parse_optimized_content(
    response_content: str,
    *,
    snippet_max_chars: int,
) -> dict[str, str | None]:
    response_payload = json.loads(response_content)
    if not isinstance(response_payload, dict):
        raise ValueError("Optimizer response must be a JSON object.")

    optimized_snippets = response_payload.get("optimized_snippets")
    if not isinstance(optimized_snippets, list):
        raise ValueError("Optimizer response must include optimized_snippets.")

    optimized_content_by_chunk_id: dict[str, str | None] = {}
    for item in optimized_snippets:
        if not isinstance(item, dict):
            continue

        chunk_id = item.get("chunk_id")
        if not isinstance(chunk_id, str) or not chunk_id:
            continue

        optimized_content = item.get("optimized_content")
        if optimized_content is not None and not isinstance(optimized_content, str):
            continue

        optimized_content_by_chunk_id[chunk_id] = _truncate_content(
            optimized_content,
            snippet_max_chars,
        )

    return optimized_content_by_chunk_id


def _fallback_truncated_candidates(
    candidates: list[RetrievalCandidate],
    *,
    snippet_max_chars: int,
) -> list[RetrievalCandidate]:
    return [
        candidate.model_copy(
            update={
                "content": _truncate_content(candidate.content, snippet_max_chars),
            }
        )
        for candidate in candidates
    ]


def _truncate_content(content: str | None, snippet_max_chars: int) -> str | None:
    if content is None:
        return None

    return content[:snippet_max_chars].rstrip()


__all__ = ["optimize_candidates_for_verification"]
