from __future__ import annotations

from dataclasses import dataclass
import re

from app.agents.schemas import (
    AnswerAgentOutput,
    AnswerGroundingReview,
    Citation,
    RejectedChunk,
    VerificationAgentOutput,
    VerifiedChunk,
)


class AnswerEvidenceValidationError(ValueError):
    """Raised when visible answer evidence violates the Agent 3 contract."""


@dataclass(frozen=True)
class AnswerEvidenceLookup:
    """Immutable lookup sets derived from Agent 2 verification output."""

    verified_quotes: frozenset[str]
    verified_file_names: frozenset[str]
    verified_citation_pairs: frozenset[tuple[str, str]]
    verified_chunk_ids: frozenset[str]
    rejected_quotes: frozenset[str]
    rejected_file_names: frozenset[str]
    rejected_citation_pairs: frozenset[tuple[str, str]]
    rejected_chunk_ids: frozenset[str]


_CHUNK_ID_LABEL_PATTERN = re.compile(r"\bchunk[\s_-]*id\b", re.IGNORECASE)
MIN_REJECTED_VISIBLE_TEXT_MATCH_CHARS = 24


def format_citation(citation: Citation) -> str:
    """Render a structured citation in the normal-user display format."""
    return f'{citation.file_name}: "{citation.quote}"'


def validate_answer_evidence_contract(
    output: AnswerAgentOutput,
    verification: VerificationAgentOutput,
) -> None:
    """Validate citation and visible-evidence rules that require Agent 2 output."""
    evidence_lookup = build_answer_evidence_lookup(verification)
    validate_citation_presence(output.citations)
    validate_citations_against_evidence(output.citations, evidence_lookup)
    validate_visible_text(
        text=output.final_answer,
        evidence_lookup=evidence_lookup,
        field_name="final_answer",
    )
    validate_visible_text(
        text=output.reasoning_summary,
        evidence_lookup=evidence_lookup,
        field_name="reasoning_summary",
    )


def validate_draft_citation_quotes_against_verified_evidence(
    output: AnswerAgentOutput,
    verification: VerificationAgentOutput,
) -> None:
    """Validate that every draft citation quote exactly matches verified evidence."""
    evidence_lookup = build_answer_evidence_lookup(verification)
    for citation in output.citations:
        citation_pair = (citation.file_name, citation.quote)
        if (
            citation_pair in evidence_lookup.rejected_citation_pairs
            or citation.quote in evidence_lookup.rejected_quotes
        ):
            raise AnswerEvidenceValidationError(
                f"Citation uses rejected evidence: {format_citation(citation)}"
            )
        if citation.quote not in evidence_lookup.verified_quotes:
            raise AnswerEvidenceValidationError(
                f"Citation quote is not present in verified evidence: "
                f"{format_citation(citation)}"
            )


def canonicalize_answer_citations(
    output: AnswerAgentOutput,
    verification: VerificationAgentOutput,
) -> AnswerAgentOutput:
    """Replace source subquote citations with their unique verified quote."""
    canonical_citations = [
        canonicalize_citation(citation, verification)
        for citation in output.citations
    ]
    if canonical_citations == output.citations:
        return output
    return output.model_copy(update={"citations": canonical_citations})


def canonicalize_grounding_review_citations(
    review: AnswerGroundingReview,
    verification: VerificationAgentOutput,
) -> AnswerGroundingReview:
    """Replace grounding subquote support with its unique verified quote."""
    field_reviews = []
    for field_review in review.field_reviews:
        claims = []
        for claim in field_review.claims:
            claims.append(
                claim.model_copy(
                    update={
                        "supporting_citations": [
                            canonicalize_citation(citation, verification)
                            for citation in claim.supporting_citations
                        ]
                    }
                )
            )
        field_reviews.append(field_review.model_copy(update={"claims": claims}))
    return review.model_copy(update={"field_reviews": field_reviews})


def canonicalize_citation(
    citation: Citation,
    verification: VerificationAgentOutput,
) -> Citation:
    normalized_citation_quote = normalize_evidence_quote(citation.quote)
    for rejected_chunk in verification.rejected_chunks:
        if (
            rejected_chunk.file_name == citation.file_name
            and normalize_evidence_quote(rejected_chunk.quote)
            == normalized_citation_quote
        ):
            return citation
        if (
            rejected_chunk.file_name == citation.file_name
            and terminal_punctuation_insensitive_quote_key(rejected_chunk.quote)
            == terminal_punctuation_insensitive_quote_key(citation.quote)
        ):
            return Citation(
                file_name=rejected_chunk.file_name,
                quote=rejected_chunk.quote,
            )

    exact_matches = [
        chunk
        for chunk in verification.verified_chunks
        if chunk.file_name == citation.file_name and chunk.quote == citation.quote
    ]
    if len(exact_matches) == 1:
        return citation

    terminal_punctuation_matches = [
        chunk
        for chunk in verification.verified_chunks
        if (
            chunk.file_name == citation.file_name
            and terminal_punctuation_insensitive_quote_key(chunk.quote)
            == terminal_punctuation_insensitive_quote_key(citation.quote)
        )
    ]
    if len(terminal_punctuation_matches) == 1:
        matched_chunk = terminal_punctuation_matches[0]
        return Citation(file_name=matched_chunk.file_name, quote=matched_chunk.quote)
    if len(terminal_punctuation_matches) > 1:
        raise AnswerEvidenceValidationError(
            f"Citation quote matches multiple verified evidence quotes: "
            f"{format_citation(citation)}"
        )

    verified_substring_matches = [
        chunk
        for chunk in verification.verified_chunks
        if (
            chunk.file_name == citation.file_name
            and citation_quote_matches_verified_quote(
                citation.quote,
                chunk.quote,
            )
        )
    ]
    if len(verified_substring_matches) == 1:
        matched_chunk = verified_substring_matches[0]
        return Citation(file_name=matched_chunk.file_name, quote=matched_chunk.quote)
    if len(verified_substring_matches) > 1:
        raise AnswerEvidenceValidationError(
            f"Citation quote matches multiple verified evidence quotes: "
            f"{format_citation(citation)}"
        )
    return citation


def normalize_evidence_quote(value: str) -> str:
    return " ".join(value.split())


def terminal_punctuation_insensitive_quote_key(value: str) -> str:
    return re.sub(r"[.,:;!?]+(?='?$)", "", normalize_evidence_quote(value))


def citation_quote_matches_verified_quote(
    citation_quote: str,
    verified_quote: str,
) -> bool:
    normalized_citation_quote = normalize_evidence_quote(citation_quote)
    normalized_verified_quote = normalize_evidence_quote(verified_quote)
    if not normalized_citation_quote:
        return False
    if normalized_citation_quote in normalized_verified_quote:
        return True

    punctuation_insensitive_citation = terminal_punctuation_insensitive_quote_key(
        citation_quote
    )
    punctuation_insensitive_verified = terminal_punctuation_insensitive_quote_key(
        verified_quote
    )
    return (
        punctuation_insensitive_citation != normalized_citation_quote
        and punctuation_insensitive_citation in punctuation_insensitive_verified
    )


def build_answer_evidence_lookup(
    verification: VerificationAgentOutput,
) -> AnswerEvidenceLookup:
    """Build immutable verified/rejected evidence sets for Agent 3 checks."""
    return AnswerEvidenceLookup(
        verified_quotes=frozenset(chunk.quote for chunk in verification.verified_chunks),
        verified_file_names=frozenset(
            chunk.file_name
            for chunk in verification.verified_chunks
            if chunk.file_name is not None
        ),
        verified_citation_pairs=evidence_citation_pairs(verification.verified_chunks),
        verified_chunk_ids=frozenset(
            str(chunk.chunk_id) for chunk in verification.verified_chunks
        ),
        rejected_quotes=frozenset(chunk.quote for chunk in verification.rejected_chunks),
        rejected_file_names=frozenset(
            chunk.file_name
            for chunk in verification.rejected_chunks
            if chunk.file_name is not None
        ),
        rejected_citation_pairs=evidence_citation_pairs(verification.rejected_chunks),
        rejected_chunk_ids=frozenset(
            str(chunk.chunk_id) for chunk in verification.rejected_chunks
        ),
    )


def validate_citation_presence(citations: list[Citation]) -> None:
    if not citations:
        raise AnswerEvidenceValidationError(
            "Grounded answer output must include at least one citation."
        )


def validate_citations_against_evidence(
    citations: list[Citation],
    evidence_lookup: AnswerEvidenceLookup,
) -> None:
    for citation in citations:
        citation_pair = (citation.file_name, citation.quote)
        if (
            citation_pair in evidence_lookup.rejected_citation_pairs
            or citation.quote in evidence_lookup.rejected_quotes
        ):
            raise AnswerEvidenceValidationError(
                f"Citation uses rejected evidence: {format_citation(citation)}"
            )
        if citation.quote not in evidence_lookup.verified_quotes:
            raise AnswerEvidenceValidationError(
                f"Citation quote is not present in verified evidence: "
                f"{format_citation(citation)}"
            )
        if citation_pair not in evidence_lookup.verified_citation_pairs:
            raise AnswerEvidenceValidationError(
                f"Citation file_name and quote do not match verified evidence: "
                f"{format_citation(citation)}"
            )


def validate_visible_text(
    *,
    text: str,
    evidence_lookup: AnswerEvidenceLookup,
    field_name: str,
) -> None:
    if _CHUNK_ID_LABEL_PATTERN.search(text):
        raise AnswerEvidenceValidationError(
            f"{field_name} must not expose internal chunk ID fields."
        )

    for chunk_id in [
        *evidence_lookup.verified_chunk_ids,
        *evidence_lookup.rejected_chunk_ids,
    ]:
        if chunk_id in text:
            raise AnswerEvidenceValidationError(
                f"{field_name} must not expose internal chunk ID values."
            )

    for rejected_quote in evidence_lookup.rejected_quotes:
        if rejected_quote_matches_visible_text(rejected_quote, text):
            raise AnswerEvidenceValidationError(
                f"{field_name} must not copy rejected evidence into normal output."
            )


def evidence_citation_pairs(
    chunks: list[VerifiedChunk] | list[RejectedChunk],
) -> frozenset[tuple[str, str]]:
    return frozenset(
        (chunk.file_name, chunk.quote)
        for chunk in chunks
        if chunk.file_name is not None
    )


def rejected_quote_matches_visible_text(rejected_quote: str, text: str) -> bool:
    normalized_rejected_quote = terminal_punctuation_insensitive_quote_key(
        rejected_quote
    ).casefold()
    normalized_text = terminal_punctuation_insensitive_quote_key(text).casefold()
    if len(normalized_rejected_quote) < MIN_REJECTED_VISIBLE_TEXT_MATCH_CHARS:
        return rejected_quote in text
    return normalized_rejected_quote in normalized_text


__all__ = [
    "AnswerEvidenceLookup",
    "AnswerEvidenceValidationError",
    "build_answer_evidence_lookup",
    "canonicalize_answer_citations",
    "canonicalize_citation",
    "canonicalize_grounding_review_citations",
    "citation_quote_matches_verified_quote",
    "evidence_citation_pairs",
    "format_citation",
    "normalize_evidence_quote",
    "rejected_quote_matches_visible_text",
    "terminal_punctuation_insensitive_quote_key",
    "validate_answer_evidence_contract",
    "validate_citation_presence",
    "validate_citations_against_evidence",
    "validate_draft_citation_quotes_against_verified_evidence",
    "validate_visible_text",
]
