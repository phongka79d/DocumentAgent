from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


DEFAULT_THRESHOLDS = {
    "min_recall": 0.80,
    "min_citation_validity": 1.00,
    "min_grounding_pass": 0.90,
    "max_unexpected_no_result": 0.10,
    "max_forbidden_term_rate": 0.00,
}


def _validate_k(k: int) -> None:
    if k <= 0:
        raise ValueError("k must be greater than zero")


def _content(chunk: Mapping[str, Any]) -> str:
    return str(chunk.get("content") or chunk.get("text") or "").casefold()


def _relevant_count(
    chunks: Sequence[Mapping[str, Any]],
    expected_chunk_contains: Sequence[str],
    *,
    k: int,
) -> int:
    unmatched = [term.casefold() for term in expected_chunk_contains if term.strip()]
    if not unmatched:
        return 0
    seen_ids: set[str] = set()
    relevant_count = 0
    for position, chunk in enumerate(chunks[:k]):
        chunk_id = str(chunk.get("chunk_id") or chunk.get("id") or position)
        if chunk_id in seen_ids:
            continue
        seen_ids.add(chunk_id)
        content = _content(chunk)
        match_index = next(
            (index for index, term in enumerate(unmatched) if term in content), None
        )
        if match_index is None:
            continue
        relevant_count += 1
        unmatched.pop(match_index)
        if not unmatched:
            break
    return relevant_count


def recall_at_k(
    chunks: Sequence[Mapping[str, Any]],
    expected_chunk_contains: Sequence[str],
    *,
    k: int,
) -> float:
    """Relevant chunks in the first k divided by expected relevant chunks."""
    _validate_k(k)
    denominator = len(expected_chunk_contains)
    if denominator == 0:
        return 0.0
    return _relevant_count(chunks, expected_chunk_contains, k=k) / denominator


def precision_at_k(
    chunks: Sequence[Mapping[str, Any]],
    expected_chunk_contains: Sequence[str],
    *,
    k: int,
) -> float:
    """Relevant chunks divided by k, or the actual result count when below k."""
    _validate_k(k)
    denominator = min(k, len(chunks))
    if denominator == 0:
        return 0.0
    return _relevant_count(chunks, expected_chunk_contains, k=k) / denominator


def rerank_lift(
    pre_rerank: Sequence[Mapping[str, Any]],
    post_rerank: Sequence[Mapping[str, Any]],
    expected_chunk_contains: Sequence[str],
    *,
    final_k: int,
) -> float:
    _validate_k(final_k)
    return recall_at_k(
        post_rerank, expected_chunk_contains, k=final_k
    ) - recall_at_k(pre_rerank, expected_chunk_contains, k=final_k)


def _answered(outcome: Mapping[str, Any]) -> bool:
    return bool(str(outcome.get("answer") or "").strip())


def no_result_rate(outcomes: Sequence[Mapping[str, Any]]) -> float:
    if not outcomes:
        return 0.0
    empty_count = sum(not outcome.get("pre_rerank") for outcome in outcomes)
    return empty_count / len(outcomes)


def unexpected_no_result_rate(outcomes: Sequence[Mapping[str, Any]]) -> float:
    positive = [outcome for outcome in outcomes if not outcome.get("expected_no_result")]
    if not positive:
        return 0.0
    empty_count = sum(not outcome.get("pre_rerank") for outcome in positive)
    return empty_count / len(positive)


def _mapping(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    return {}


def citation_validity_rate(outcomes: Sequence[Mapping[str, Any]]) -> float:
    answered = [outcome for outcome in outcomes if _answered(outcome)]
    if not answered:
        return 0.0

    valid_count = 0
    for outcome in answered:
        validation = _mapping(outcome.get("citation_validation"))
        context_ids = {
            str(chunk.get("chunk_id") or chunk.get("id"))
            for chunk in outcome.get("context") or []
            if isinstance(chunk, Mapping)
            and (chunk.get("chunk_id") is not None or chunk.get("id") is not None)
        }
        cited_ids = {str(value) for value in validation.get("cited_chunk_ids") or []}
        if bool(validation.get("valid")) and cited_ids <= context_ids:
            valid_count += 1
    return valid_count / len(answered)


def grounding_pass_rate(outcomes: Sequence[Mapping[str, Any]]) -> float:
    answered = [outcome for outcome in outcomes if _answered(outcome)]
    if not answered:
        return 0.0
    return sum(bool(outcome.get("grounding_passed")) for outcome in answered) / len(
        answered
    )


def _term_rate(outcomes: Sequence[Mapping[str, Any]], field: str) -> float:
    present = 0
    denominator = 0
    for outcome in outcomes:
        answer = str(outcome.get("answer") or "").casefold()
        for term in outcome.get(field) or []:
            normalized = str(term).strip().casefold()
            if not normalized:
                continue
            denominator += 1
            present += normalized in answer
    if denominator == 0:
        return 0.0
    return present / denominator


def answer_term_coverage(outcomes: Sequence[Mapping[str, Any]]) -> float:
    return _term_rate(outcomes, "required_answer_terms")


def forbidden_term_rate(outcomes: Sequence[Mapping[str, Any]]) -> float:
    return _term_rate(outcomes, "forbidden_answer_terms")


def calculate_metrics(
    outcomes: Sequence[Mapping[str, Any]], *, k: int
) -> dict[str, float]:
    _validate_k(k)
    expected_count = sum(
        len(outcome.get("expected_chunk_contains") or []) for outcome in outcomes
    )
    pre_relevant = sum(
        _relevant_count(
            outcome.get("pre_rerank") or [],
            outcome.get("expected_chunk_contains") or [],
            k=k,
        )
        for outcome in outcomes
    )
    post_relevant = sum(
        _relevant_count(
            outcome.get("post_rerank") or [],
            outcome.get("expected_chunk_contains") or [],
            k=k,
        )
        for outcome in outcomes
    )
    precision_denominator = sum(
        min(k, len(outcome.get("pre_rerank") or [])) for outcome in outcomes
    )
    recall_before = pre_relevant / expected_count if expected_count else 0.0
    recall_after = post_relevant / expected_count if expected_count else 0.0
    return {
        f"recall_at_{k}": recall_before,
        f"precision_at_{k}": (
            pre_relevant / precision_denominator if precision_denominator else 0.0
        ),
        "rerank_lift": recall_after - recall_before,
        "no_result_rate": no_result_rate(outcomes),
        "unexpected_no_result_rate": unexpected_no_result_rate(outcomes),
        "citation_validity_rate": citation_validity_rate(outcomes),
        "grounding_pass_rate": grounding_pass_rate(outcomes),
        "answer_term_coverage": answer_term_coverage(outcomes),
        "forbidden_term_rate": forbidden_term_rate(outcomes),
    }


def evaluate_thresholds(
    metrics: Mapping[str, float],
    *,
    k: int,
    min_recall: float = DEFAULT_THRESHOLDS["min_recall"],
    min_citation_validity: float = DEFAULT_THRESHOLDS["min_citation_validity"],
    min_grounding_pass: float = DEFAULT_THRESHOLDS["min_grounding_pass"],
    max_unexpected_no_result: float = DEFAULT_THRESHOLDS[
        "max_unexpected_no_result"
    ],
    max_forbidden_term_rate: float = DEFAULT_THRESHOLDS["max_forbidden_term_rate"],
) -> list[dict[str, float | str]]:
    gates = (
        (f"recall_at_{k}", ">=", min_recall),
        ("citation_validity_rate", ">=", min_citation_validity),
        ("grounding_pass_rate", ">=", min_grounding_pass),
        ("unexpected_no_result_rate", "<=", max_unexpected_no_result),
        ("forbidden_term_rate", "<=", max_forbidden_term_rate),
    )
    failures: list[dict[str, float | str]] = []
    for name, operator, threshold in gates:
        actual = float(metrics.get(name, 0.0))
        passed = actual >= threshold if operator == ">=" else actual <= threshold
        if not passed:
            failures.append(
                {
                    "metric": name,
                    "operator": operator,
                    "threshold": threshold,
                    "actual": actual,
                }
            )
    return failures


__all__ = [
    "DEFAULT_THRESHOLDS",
    "answer_term_coverage",
    "calculate_metrics",
    "citation_validity_rate",
    "evaluate_thresholds",
    "forbidden_term_rate",
    "grounding_pass_rate",
    "no_result_rate",
    "precision_at_k",
    "recall_at_k",
    "rerank_lift",
    "unexpected_no_result_rate",
]
