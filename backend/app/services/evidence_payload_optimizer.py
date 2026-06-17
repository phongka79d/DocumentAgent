from __future__ import annotations

import re

from app.agents.schemas import RetrievalCandidate


_WORD_PATTERN = re.compile(r"[\w']+", re.UNICODE)
_SENTENCE_BOUNDARY_PATTERN = re.compile("(?<=[.!?\u3002\uff01\uff1f])\\s+")
_DATE_OR_DURATION_PATTERN = re.compile(
    r"\b(?:"
    r"\d{1,4}[-/]\d{1,2}(?:[-/]\d{1,4})?"
    r"|(?:january|february|march|april|may|june|july|august|september|"
    r"october|november|december)\s+\d{1,2},?\s+\d{4}"
    r"|\d+\s+(?:day|days|week|weeks|month|months|year|years)"
    r"|\d+\s+(?:ngay|ngày|tuan|tuần|thang|tháng|nam|năm)"
    r")\b",
    re.IGNORECASE,
)
_TEMPORAL_QUESTION_TERMS = frozenset(
    {
        "when",
        "date",
        "day",
        "month",
        "year",
        "start",
        "starts",
        "started",
        "begin",
        "begins",
        "began",
        "duration",
        "period",
        "official",
        "bao",
        "gio",
        "ngay",
        "ngày",
        "thang",
        "tháng",
        "nam",
        "năm",
        "bat",
        "bắt",
        "dau",
        "đầu",
        "thoi",
        "thời",
        "gian",
        "thu",
        "thử",
        "viec",
        "việc",
        "chinh",
        "chính",
        "thuc",
        "thức",
        "giờ",
    }
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
    terms: set[str] = set()
    for token in _WORD_PATTERN.findall(value):
        lowered = token.lower()
        if len(lowered) <= 2:
            continue

        terms.add(lowered)
        canonical = _canonical_term(lowered)
        if len(canonical) > 2:
            terms.add(canonical)

    return terms


def _canonical_term(token: str) -> str:
    if token.endswith("'s") and len(token) > 4:
        token = token[:-2]

    if token.endswith("ies") and len(token) > 4:
        return token[:-3] + "y"

    if token.endswith("ves") and len(token) > 4:
        return token[:-3] + "f"

    if token.endswith("ed") and len(token) > 4:
        stem = token[:-2]
        if len(stem) > 3 and stem[-1] == stem[-2]:
            stem = stem[:-1]
        return stem

    if token.endswith("ing") and len(token) > 5:
        stem = token[:-3]
        if len(stem) > 3 and stem[-1] == stem[-2]:
            stem = stem[:-1]
        return stem

    if token.endswith("s") and len(token) > 3:
        return token[:-1]

    return token


def _sentence_score(sentence: str, question_terms: set[str]) -> int:
    signal_score = 0
    if question_terms & _TEMPORAL_QUESTION_TERMS and _DATE_OR_DURATION_PATTERN.search(
        sentence
    ):
        signal_score += 4
    if not question_terms:
        return signal_score
    sentence_terms = _content_terms(sentence)
    return len(sentence_terms & question_terms) + signal_score


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
