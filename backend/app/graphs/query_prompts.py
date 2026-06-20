from __future__ import annotations

from collections.abc import Mapping


ANSWER_SYSTEM_PROMPT = (
    "You are a personal document RAG assistant.\n\n"
    "Rules:\n"
    "- Answer using only the provided context.\n"
    "- If the context does not contain enough information, say that the indexed documents do not contain enough information.\n"
    "- Do not invent facts.\n"
    "- Do not invent sources.\n"
    "- Cite the source chunks used in the answer.\n"
    "- Keep the answer clear and practical."
)
ANSWER_USER_PROMPT_TEMPLATE = (
    "Context:\n"
    "{context}\n\n"
    "Question:\n"
    "{question}\n\n"
    "Answer using only the context."
)
NO_RELEVANT_INFORMATION_MESSAGE = "No relevant information found in indexed documents."


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


__all__ = [
    "ANSWER_SYSTEM_PROMPT",
    "ANSWER_USER_PROMPT_TEMPLATE",
    "NO_RELEVANT_INFORMATION_MESSAGE",
    "build_answer_messages",
]
