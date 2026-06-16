from __future__ import annotations

import re


SENTENCE_BOUNDARY_PATTERN = re.compile(r"(?<=[.!?])(?P<closing_quote>['\"]?)\s+")
ELLIPSIS_MARKER_PATTERN = re.compile(
    r"\s*(?:\[\s*(?:\.{3}|\u2026)\s*\]|\.{3}|\u2026)\s*"
)
QUOTE_TOKEN_PATTERN = re.compile(r"[a-z0-9]+(?:'[a-z0-9]+)?", re.IGNORECASE)
ORDERED_QUOTE_MIN_TOKENS = 6
ORDERED_QUOTE_MAX_EXTRA_TOKENS = 30
ORDERED_QUOTE_MAX_SPAN_TOKEN_MULTIPLIER = 4
ORDERED_QUOTE_MAX_SPAN_CHARS = 1200


def canonical_source_quote_for_candidate(
    quote: str,
    content: str | None,
) -> str | None:
    canonical_quote = source_span_for_case_insensitive_quote(quote, content)
    if canonical_quote is not None:
        return canonical_quote

    canonical_quote = source_span_for_ellipsized_quote(quote, content)
    if canonical_quote is not None:
        return canonical_quote

    canonical_quote = source_span_for_token_sequence_quote(quote, content)
    if canonical_quote is not None:
        return canonical_quote

    return source_span_for_ordered_token_quote(quote, content)


def source_span_for_ellipsized_quote(
    quote: str,
    content: str | None,
) -> str | None:
    normalized_quote = normalize_quote_text(quote)
    if not ELLIPSIS_MARKER_PATTERN.search(normalized_quote):
        return None

    fragments = [
        fragment.strip()
        for fragment in ELLIPSIS_MARKER_PATTERN.split(normalized_quote)
        if fragment.strip()
    ]
    if len(fragments) < 2:
        return None

    normalized_content = normalize_quote_text(content or "")
    span_start: int | None = None
    span_end: int | None = None
    search_start = 0
    for fragment in fragments:
        fragment_start = normalized_content.find(fragment, search_start)
        if fragment_start < 0:
            return None
        if span_start is None:
            span_start = fragment_start
        span_end = fragment_start + len(fragment)
        search_start = span_end

    if span_start is None or span_end is None:
        return None
    return normalized_content[span_start:span_end].strip()


def source_span_for_token_sequence_quote(
    quote: str,
    content: str | None,
) -> str | None:
    normalized_quote = normalize_quote_text(quote)
    normalized_content = normalize_quote_text(content or "")
    quote_tokens = [
        match.group(0).casefold()
        for match in QUOTE_TOKEN_PATTERN.finditer(normalized_quote)
    ]
    if len(quote_tokens) < 4:
        return None

    content_token_matches = list(QUOTE_TOKEN_PATTERN.finditer(normalized_content))
    content_tokens = [match.group(0).casefold() for match in content_token_matches]
    matches: list[tuple[int, int]] = []
    window_size = len(quote_tokens)
    for start in range(0, len(content_tokens) - window_size + 1):
        if content_tokens[start : start + window_size] == quote_tokens:
            span_start = content_token_matches[start].start()
            span_end = content_token_matches[start + window_size - 1].end()
            matches.append((span_start, span_end))

    if len(matches) != 1:
        return None
    span_start, span_end = matches[0]
    return normalized_content[span_start:span_end].strip()


def source_span_for_ordered_token_quote(
    quote: str,
    content: str | None,
) -> str | None:
    normalized_quote = normalize_quote_text(quote)
    normalized_content = normalize_quote_text(content or "")
    quote_tokens = [
        match.group(0).casefold()
        for match in QUOTE_TOKEN_PATTERN.finditer(normalized_quote)
    ]
    if len(quote_tokens) < ORDERED_QUOTE_MIN_TOKENS:
        return None

    content_token_matches = list(QUOTE_TOKEN_PATTERN.finditer(normalized_content))
    content_tokens = [match.group(0).casefold() for match in content_token_matches]
    max_span_tokens = max(
        len(quote_tokens) + ORDERED_QUOTE_MAX_EXTRA_TOKENS,
        len(quote_tokens) * ORDERED_QUOTE_MAX_SPAN_TOKEN_MULTIPLIER,
    )
    spans: list[tuple[int, int, int]] = []

    for start_index, token in enumerate(content_tokens):
        if token != quote_tokens[0]:
            continue

        quote_index = 1
        end_index = start_index
        for content_index in range(start_index + 1, len(content_tokens)):
            if content_tokens[content_index] != quote_tokens[quote_index]:
                continue
            quote_index += 1
            end_index = content_index
            if quote_index == len(quote_tokens):
                break

        if quote_index != len(quote_tokens):
            continue

        span_token_count = end_index - start_index + 1
        span_start = content_token_matches[start_index].start()
        span_end = content_token_matches[end_index].end()
        if span_token_count > max_span_tokens:
            continue
        if span_end - span_start > ORDERED_QUOTE_MAX_SPAN_CHARS:
            continue
        spans.append((span_token_count, span_start, span_end))

    if not spans:
        return None

    shortest_span_token_count = min(span[0] for span in spans)
    shortest_spans = {
        (span_start, span_end)
        for span_token_count, span_start, span_end in spans
        if span_token_count == shortest_span_token_count
    }
    if len(shortest_spans) != 1:
        return None

    span_start, span_end = next(iter(shortest_spans))
    return normalized_content[span_start:span_end].strip()


def source_span_for_case_insensitive_quote(
    quote: str,
    content: str | None,
) -> str | None:
    normalized_quote = normalize_quote_text(quote)
    normalized_content = normalize_quote_text(content or "")
    if not normalized_quote:
        return None

    normalized_content_key = normalized_content.casefold()
    normalized_quote_key = normalized_quote.casefold()
    quote_start = normalized_content_key.find(normalized_quote_key)
    quote_end = quote_start + len(normalized_quote)
    if quote_start >= 0:
        return normalized_content[quote_start:quote_end].strip()

    quote_without_terminal_punctuation = re.sub(
        r"[.,:;!?]+(?='?$)",
        "",
        normalized_quote,
    )
    if quote_without_terminal_punctuation == normalized_quote:
        return None

    quote_key_without_terminal_punctuation = (
        quote_without_terminal_punctuation.casefold()
    )
    quote_start = normalized_content_key.find(
        quote_key_without_terminal_punctuation
    )
    if quote_start < 0:
        return None
    quote_end = quote_start + len(quote_without_terminal_punctuation)
    source_quote_end = quote_end
    if quote_end < len(normalized_content) and normalized_content[quote_end] in ".,:;!?":
        source_quote_end += 1
    return normalized_content[quote_start:source_quote_end].strip()


def normalize_quote_text(value: str) -> str:
    text = " ".join(value.split())
    text = text.replace("â€œ", "'").replace("â€", "'").replace("â€ž", "'").replace("â€Ÿ", "'")
    text = text.replace("â€˜", "'").replace("â€™", "'").replace("â€š", "'").replace("â€›", "'")
    text = text.replace('"', "'")
    return text


def quote_matches_candidate_content(quote: str, content: str | None) -> bool:
    return canonical_source_quote_for_candidate(quote, content) is not None


def expanded_quote_with_surrounding_context(
    quote: str,
    content: str | None,
) -> str | None:
    normalized_quote = normalize_quote_text(quote)
    normalized_content = normalize_quote_text(content or "")
    if not normalized_quote or normalized_quote not in normalized_content:
        return None

    quote_start = normalized_content.find(normalized_quote)
    quote_end = quote_start + len(normalized_quote)
    sentence_spans = sentence_spans_for_text(normalized_content)

    overlapping_indexes = overlapping_sentence_indexes_for_quote(
        sentence_spans,
        quote_start,
        quote_end,
    )
    if not overlapping_indexes:
        return None

    start_index = max(0, overlapping_indexes[0] - 1)
    end_index = overlapping_indexes[-1] + 1
    expanded_quote = normalize_quote_text(
        " ".join(
            sentence
            for _sentence_start, _sentence_end, sentence in sentence_spans[
                start_index:end_index
            ]
        )
    )
    if expanded_quote == normalized_quote:
        return None
    return expanded_quote


def expanded_quotes_with_surrounding_context(
    quote: str,
    content: str | None,
) -> list[str] | None:
    normalized_quote = normalize_quote_text(quote)
    normalized_content = normalize_quote_text(content or "")
    if not normalized_quote or normalized_quote not in normalized_content:
        return None

    quote_start = normalized_content.find(normalized_quote)
    quote_end = quote_start + len(normalized_quote)
    sentence_spans = sentence_spans_for_text(normalized_content)
    overlapping_indexes = overlapping_sentence_indexes_for_quote(
        sentence_spans,
        quote_start,
        quote_end,
    )
    if not overlapping_indexes:
        return None

    quotes: list[str] = []
    previous_index = overlapping_indexes[0] - 1
    if previous_index >= 0:
        context_quote = trim_preceding_context_sentence(
            sentence_spans[previous_index][2]
        )
        if (
            context_quote
            and context_quote != normalized_quote
            and context_quote in normalized_content
        ):
            quotes.append(context_quote)

    if normalized_quote not in {normalize_quote_text(value) for value in quotes}:
        quotes.append(normalized_quote)

    if len(quotes) <= 1:
        return None
    return quotes


def sentence_spans_for_text(
    content: str,
) -> list[tuple[int, int, str]]:
    spans = []
    sentence_start = 0
    for boundary in SENTENCE_BOUNDARY_PATTERN.finditer(content):
        sentence_end = boundary.start() + len(boundary.group("closing_quote"))
        raw_sentence = content[sentence_start:sentence_end]
        sentence = raw_sentence.strip()
        if sentence:
            leading_trim = len(raw_sentence) - len(raw_sentence.lstrip())
            trailing_trim = len(raw_sentence) - len(raw_sentence.rstrip())
            spans.append(
                (
                    sentence_start + leading_trim,
                    sentence_end - trailing_trim,
                    sentence,
                )
            )
        sentence_start = boundary.end()

    raw_sentence = content[sentence_start:]
    sentence = raw_sentence.strip()
    if sentence:
        leading_trim = len(raw_sentence) - len(raw_sentence.lstrip())
        trailing_trim = len(raw_sentence) - len(raw_sentence.rstrip())
        spans.append(
            (
                sentence_start + leading_trim,
                len(content) - trailing_trim,
                sentence,
            )
        )

    return spans


def overlapping_sentence_indexes_for_quote(
    sentence_spans: list[tuple[int, int, str]],
    quote_start: int,
    quote_end: int,
) -> list[int]:
    return [
        index
        for index, (sentence_start, sentence_end, _sentence) in enumerate(
            sentence_spans
        )
        if sentence_start < quote_end and quote_start < sentence_end
    ]


def trim_preceding_context_sentence(sentence: str) -> str:
    leading_clause, separator, _remaining = sentence.partition(";")
    if separator and len(leading_clause.split()) >= 6:
        return f"{leading_clause.strip()};"
    return sentence


def candidate_source_excerpt(content: str | None) -> str | None:
    excerpt = (content or "").strip()
    return excerpt or None


__all__ = [
    "canonical_source_quote_for_candidate",
    "candidate_source_excerpt",
    "expanded_quote_with_surrounding_context",
    "expanded_quotes_with_surrounding_context",
    "normalize_quote_text",
    "quote_matches_candidate_content",
]
