import re

from app.agents.schemas import VerificationAgentOutput, VerifiedChunk
from app.services.evidence_quote_service import normalize_quote_text


NO_VERIFIED_CHUNKS_CONFIDENCE_CAP = 0.2
CONTRADICTION_CONFIDENCE_CAP = 0.4
CONTRADICTION_VERIFICATION_REASON = (
    "Potential contradiction detected: verified chunks contain unresolved "
    "conflicting evidence."
)

_MONTH_BY_NAME = {
    "january": "01",
    "february": "02",
    "march": "03",
    "april": "04",
    "may": "05",
    "june": "06",
    "july": "07",
    "august": "08",
    "september": "09",
    "october": "10",
    "november": "11",
    "december": "12",
}
_DATE_PATTERN = re.compile(
    r"\b(?P<iso>\d{4}[-/]\d{1,2}[-/]\d{1,2})\b"
    r"|\b(?P<numeric>\d{1,2}[-/]\d{1,2}[-/]\d{2,4})\b"
    r"|\b(?P<month>"
    r"january|february|march|april|may|june|july|august|september|october|"
    r"november|december"
    r")\s+(?P<day>\d{1,2}),?\s+(?P<year>\d{4})\b",
    re.IGNORECASE,
)
_NEGATION_PATTERN = re.compile(
    r"\b(?:not|no|never|cannot|can't|does\s+not|do\s+not|did\s+not|"
    r"is\s+not|are\s+not|was\s+not|were\s+not|khong|kh\u00f4ng|"
    r"chua|ch\u01b0a)\b",
    re.IGNORECASE,
)
_CLAIM_HELPER_VERB_PATTERN = re.compile(
    r"\b(?:is|are|was|were|be|being|been|does|do|did|can|may|must|will|"
    r"should|du|d\u1ee7)\b",
    re.IGNORECASE,
)


def _normalize_date_match(match: re.Match[str]) -> str:
    if match.group("iso"):
        year, month, day = re.split(r"[-/]", match.group("iso"))
        return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"

    if match.group("numeric"):
        first, second, third = re.split(r"[-/]", match.group("numeric"))
        if len(third) == 2:
            third = f"20{third}"
        return f"{int(third):04d}-{int(second):02d}-{int(first):02d}"

    month = _MONTH_BY_NAME[match.group("month").lower()]
    return f"{int(match.group('year')):04d}-{month}-{int(match.group('day')):02d}"


def _date_conflict_key(text: str) -> tuple[str, tuple[str, ...]] | None:
    dates = tuple(_normalize_date_match(match) for match in _DATE_PATTERN.finditer(text))
    if not dates:
        return None

    without_dates = _DATE_PATTERN.sub(" <date> ", text.lower())
    key = normalize_quote_text(re.sub(r"[^a-z0-9<>\s]", " ", without_dates))
    return key, dates


def _has_clear_date_conflict(verified_chunks: list[VerifiedChunk]) -> bool:
    dates_by_statement_key: dict[str, tuple[str, ...]] = {}

    for verified_chunk in verified_chunks:
        conflict_key = _date_conflict_key(verified_chunk.quote)
        if conflict_key is None:
            continue

        statement_key, dates = conflict_key
        existing_dates = dates_by_statement_key.get(statement_key)
        if existing_dates is not None and existing_dates != dates:
            return True
        dates_by_statement_key[statement_key] = dates

    return False


def _claim_conflict_key(text: str) -> tuple[str, bool] | None:
    normalized_text = normalize_quote_text(text.lower())
    if len(normalized_text) > 180:
        return None

    has_negation = bool(_NEGATION_PATTERN.search(normalized_text))
    without_negation = _NEGATION_PATTERN.sub(" ", normalized_text)
    without_helper_verbs = _CLAIM_HELPER_VERB_PATTERN.sub(" ", without_negation)
    key = normalize_quote_text(re.sub(r"[^a-z0-9\s]", " ", without_helper_verbs))
    return (key, has_negation) if key else None


def _has_clear_short_claim_conflict(verified_chunks: list[VerifiedChunk]) -> bool:
    polarity_by_claim_key: dict[str, bool] = {}

    for verified_chunk in verified_chunks:
        conflict_key = _claim_conflict_key(verified_chunk.quote)
        if conflict_key is None:
            continue

        claim_key, has_negation = conflict_key
        existing_negation = polarity_by_claim_key.get(claim_key)
        if existing_negation is not None and existing_negation != has_negation:
            return True
        polarity_by_claim_key[claim_key] = has_negation

    return False


def _append_contradiction_reason(verified_chunk: VerifiedChunk) -> VerifiedChunk:
    if "contradict" in verified_chunk.verification_reason.lower():
        return verified_chunk

    return verified_chunk.model_copy(
        update={
            "verification_reason": (
                f"{verified_chunk.verification_reason} "
                f"{CONTRADICTION_VERIFICATION_REASON}"
            )
        }
    )


def apply_missing_information_adjustments(
    verification_output: VerificationAgentOutput,
) -> VerificationAgentOutput:
    if not verification_output.verified_chunks:
        return verification_output.model_copy(
            update={
                "missing_information": True,
                "confidence": min(
                    verification_output.confidence,
                    NO_VERIFIED_CHUNKS_CONFIDENCE_CAP,
                ),
            }
        )

    has_conflict = _has_clear_date_conflict(
        verification_output.verified_chunks
    ) or _has_clear_short_claim_conflict(verification_output.verified_chunks)
    if not has_conflict:
        return verification_output

    return verification_output.model_copy(
        update={
            "verified_chunks": [
                _append_contradiction_reason(chunk)
                for chunk in verification_output.verified_chunks
            ],
            "missing_information": True,
            "confidence": min(
                verification_output.confidence,
                CONTRADICTION_CONFIDENCE_CAP,
            ),
        }
    )


__all__ = [
    "CONTRADICTION_CONFIDENCE_CAP",
    "CONTRADICTION_VERIFICATION_REASON",
    "NO_VERIFIED_CHUNKS_CONFIDENCE_CAP",
    "apply_missing_information_adjustments",
]
