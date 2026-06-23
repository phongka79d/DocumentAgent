from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any


ANSWER_SYSTEM_PROMPT = (
    "You are a personal document RAG assistant.\n\n"
    "Rules:\n"
    "- Answer using only the provided context.\n"
    "- If the context does not contain enough information, say that the indexed documents do not contain enough information.\n"
    "- Do not invent facts.\n"
    "- Do not invent sources.\n"
    "- Cite every factual claim with one or more prompt-local source keys using [S1] syntax.\n"
    "- Use only source keys present in the context; do not cite document IDs, file names, headings, or invented labels.\n"
    "- The insufficient-context response does not need a citation.\n"
    "- Keep the answer clear and practical."
)
ANSWER_USER_PROMPT_TEMPLATE = (
    "Context:\n"
    "{context}\n\n"
    "Question:\n"
    "{question}\n\n"
    "Answer using only the context and cite factual claims with [S<number>] source keys."
)
NO_RELEVANT_INFORMATION_MESSAGE = "No relevant information found in indexed documents."
SAFE_INSUFFICIENT_CONTEXT_MESSAGE = (
    "The indexed documents do not contain enough verified information to answer this question."
)
GROUNDING_SYSTEM_PROMPT = (
    "You are a strict grounding verifier for a document RAG answer.\n"
    "Use only the provided cited evidence text.\n"
    "Return JSON only. No prose.\n"
    "The JSON must contain exactly these fields: grounded, score, unsupported_claims, missing_citations."
)
GROUNDING_USER_PROMPT_TEMPLATE = (
    "Answer to verify:\n"
    "{answer}\n\n"
    "Cited evidence JSON:\n"
    "{evidence_json}\n\n"
    "Return strict JSON in this shape:\n"
    "{{\"grounded\": true, \"score\": 0.95, \"unsupported_claims\": [], \"missing_citations\": []}}"
)
REGENERATION_SYSTEM_PROMPT = (
    ANSWER_SYSTEM_PROMPT
    + "\n- Revise the previous draft using the verifier feedback.\n"
    + "- Remove unsupported claims instead of guessing."
)
REGENERATION_USER_PROMPT_TEMPLATE = (
    "Context:\n"
    "{context}\n\n"
    "Question:\n"
    "{question}\n\n"
    "Verifier feedback:\n"
    "{feedback}\n\n"
    "Regenerate the answer using only the context and cite factual claims with [S<number>] source keys."
)

QUERY_PLANNING_SYSTEM_PROMPT = (
    "You plan bounded retrieval for a document RAG system.\n"
    "Return JSON only. No prose.\n"
    "Use only these strategies: semantic, keyword, hybrid, metadata, relation.\n"
    "Do not add, remove, rewrite, infer, or widen document_ids.\n"
    "Only infer filters from the user's question when they are clear.\n"
    "Explicit filters are fixed constraints and override inferred filters.\n"
    "For compound questions, create separate focused subqueries for each part.\n"
    "For exact identifiers or codes, include the identifier exactly in a focused subquery."
)
QUERY_PLANNING_USER_PROMPT_TEMPLATE = (
    "Plan a retrieval query using this input JSON:\n"
    "{request_json}\n\n"
    "Required JSON shape:\n"
    "{{"
    '"is_complex": true, '
    '"strategy": "hybrid", '
    '"subqueries": [{{"id": "q1", "text": "focused question"}}], '
    '"inferred_filters": {{'
    '"mime_types": [], '
    '"heading": null, '
    '"section_path": [], '
    '"page_start": null, '
    '"page_end": null'
    '}}, '
    '"needs_relations": false'
    "}}\n"
    "Use at most {max_subqueries} subqueries. Keep subqueries focused and bounded."
)
QUERY_PLANNING_JSON_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "is_complex",
        "strategy",
        "subqueries",
        "inferred_filters",
        "needs_relations",
    ],
    "properties": {
        "is_complex": {"type": "boolean"},
        "strategy": {
            "type": "string",
            "enum": ["semantic", "keyword", "hybrid", "metadata", "relation"],
        },
        "subqueries": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["id", "text"],
                "properties": {
                    "id": {"type": "string", "minLength": 1},
                    "text": {"type": "string"},
                },
            },
        },
        "inferred_filters": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "mime_types",
                "heading",
                "section_path",
                "page_start",
                "page_end",
            ],
            "properties": {
                "mime_types": {"type": "array", "items": {"type": "string"}},
                "heading": {"type": ["string", "null"]},
                "section_path": {"type": "array", "items": {"type": "string"}},
                "page_start": {"type": ["integer", "null"], "minimum": 0},
                "page_end": {"type": ["integer", "null"], "minimum": 0},
            },
        },
        "needs_relations": {"type": "boolean"},
    },
}
QUERY_PLANNING_RESPONSE_FORMAT = {
    "type": "json_schema",
    "json_schema": {
        "name": "query_plan",
        "strict": True,
        "schema": QUERY_PLANNING_JSON_SCHEMA,
    },
}


def build_answer_messages(*, context: str, question: str) -> list[Mapping[str, str]]:
    return [
        {"role": "system", "content": ANSWER_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": ANSWER_USER_PROMPT_TEMPLATE.format(
                context=context,
                question=question,
            ),
        },
    ]


def build_grounding_messages(
    *,
    answer: str,
    evidence: Sequence[Mapping[str, Any]],
) -> list[Mapping[str, str]]:
    evidence_json = json.dumps(list(evidence), ensure_ascii=False)
    return [
        {"role": "system", "content": GROUNDING_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": GROUNDING_USER_PROMPT_TEMPLATE.format(
                answer=answer,
                evidence_json=evidence_json,
            ),
        },
    ]


def build_regeneration_messages(
    *,
    context: str,
    question: str,
    feedback: str,
) -> list[Mapping[str, str]]:
    return [
        {"role": "system", "content": REGENERATION_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": REGENERATION_USER_PROMPT_TEMPLATE.format(
                context=context,
                question=question,
                feedback=feedback,
            ),
        },
    ]


def build_query_planning_messages(
    *,
    question: str,
    document_ids: Sequence[Any],
    explicit_filters: Mapping[str, Any] | None,
    max_subqueries: int,
) -> list[Mapping[str, str]]:
    request_json = json.dumps(
        {
            "question": question,
            "document_ids": [str(document_id) for document_id in document_ids],
            "explicit_filters": explicit_filters,
            "max_subqueries": max_subqueries,
        }
    )
    return [
        {"role": "system", "content": QUERY_PLANNING_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": QUERY_PLANNING_USER_PROMPT_TEMPLATE.format(
                request_json=request_json,
                max_subqueries=max_subqueries,
            ),
        },
    ]


__all__ = [
    "ANSWER_SYSTEM_PROMPT",
    "ANSWER_USER_PROMPT_TEMPLATE",
    "GROUNDING_SYSTEM_PROMPT",
    "GROUNDING_USER_PROMPT_TEMPLATE",
    "NO_RELEVANT_INFORMATION_MESSAGE",
    "REGENERATION_SYSTEM_PROMPT",
    "REGENERATION_USER_PROMPT_TEMPLATE",
    "SAFE_INSUFFICIENT_CONTEXT_MESSAGE",
    "QUERY_PLANNING_JSON_SCHEMA",
    "QUERY_PLANNING_RESPONSE_FORMAT",
    "QUERY_PLANNING_SYSTEM_PROMPT",
    "QUERY_PLANNING_USER_PROMPT_TEMPLATE",
    "build_answer_messages",
    "build_grounding_messages",
    "build_query_planning_messages",
    "build_regeneration_messages",
]
