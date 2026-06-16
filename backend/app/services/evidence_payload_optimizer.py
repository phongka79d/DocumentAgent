from __future__ import annotations

import re

from app.agents.schemas import RetrievalCandidate


_WORD_PATTERN = re.compile(r"[\w']+", re.UNICODE)
_SENTENCE_BOUNDARY_PATTERN = re.compile("(?<=[.!?\u3002\uff01\uff1f])\\s+")


def optimize_candidates_for_verification(
    *,
    question: str,
    candidates: list[RetrievalCandidate],
    max_candidates: int,
    snippet_max_chars: int,
    context_sentences: int,
) -> list[RetrievalCandidate]:
    selected_candidates = candidates[:max_candidates]
    return [
        candidate.model_copy(
            update={
                "content": _snippet_for_candidate(
                    question=question,
                    content=candidate.content,
                    snippet_max_chars=snippet_max_chars,
                    context_sentences=context_sentences,
                )
            }
        )
        for candidate in selected_candidates
    ]


def _snippet_for_candidate(
    *,
    question: str,
    content: str | None,
    snippet_max_chars: int,
    context_sentences: int,
) -> str | None:
    if content is None:
        return None

    normalized_content = content.strip()
    if len(normalized_content) <= snippet_max_chars:
        return normalized_content

    sentence_spans = _sentence_spans(normalized_content)
    if not sentence_spans:
        return normalized_content[:snippet_max_chars].rstrip()

    question_terms = _content_terms(question)
    scored_indexes = sorted(
        range(len(sentence_spans)),
        key=lambda index: (
            _sentence_score(
                normalized_content[
                    sentence_spans[index][0] : sentence_spans[index][1]
                ],
                question_terms,
            ),
            -index,
        ),
        reverse=True,
    )
    best_index = scored_indexes[0]
    start_index = max(0, best_index - context_sentences)
    end_index = min(len(sentence_spans), best_index + context_sentences + 1)

    while start_index > 0 or end_index < len(sentence_spans):
        start_char = sentence_spans[start_index][0]
        end_char = sentence_spans[end_index - 1][1]
        if end_char - start_char >= snippet_max_chars:
            break

        left_score = (
            _sentence_score(
                normalized_content[
                    sentence_spans[start_index - 1][0] : sentence_spans[
                        start_index - 1
                    ][1]
                ],
                question_terms,
            )
            if start_index > 0
            else -1
        )
        right_score = (
            _sentence_score(
                normalized_content[
                    sentence_spans[end_index][0] : sentence_spans[end_index][1]
                ],
                question_terms,
            )
            if end_index < len(sentence_spans)
            else -1
        )

        if right_score > left_score and end_index < len(sentence_spans):
            next_end = sentence_spans[end_index][1]
            if next_end - start_char > snippet_max_chars:
                break
            end_index += 1
        elif start_index > 0:
            next_start = sentence_spans[start_index - 1][0]
            if end_char - next_start > snippet_max_chars:
                break
            start_index -= 1
        else:
            break

    snippet = normalized_content[
        sentence_spans[start_index][0] : sentence_spans[end_index - 1][1]
    ].strip()
    if len(snippet) <= snippet_max_chars:
        return snippet

    best_sentence = normalized_content[
        sentence_spans[best_index][0] : sentence_spans[best_index][1]
    ].strip()
    return best_sentence[:snippet_max_chars].rstrip()


def _content_terms(value: str | None) -> set[str]:
    if not value:
        return set()
    return {
        token.lower()
        for token in _WORD_PATTERN.findall(value)
        if len(token) > 2
    }


def _sentence_score(sentence: str, question_terms: set[str]) -> int:
    if not question_terms:
        return 0
    sentence_terms = _content_terms(sentence)
    return len(sentence_terms & question_terms)


def _sentence_spans(content: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    cursor = 0
    for part in _SENTENCE_BOUNDARY_PATTERN.split(content):
        if not part:
            continue
        start = content.find(part, cursor)
        if start < 0:
            continue
        end = start + len(part)
        spans.append((start, end))
        cursor = end
    return spans


__all__ = ["optimize_candidates_for_verification"]
