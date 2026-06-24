from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.core.config import Settings
from app.graphs.query_steps.dependencies import QueryStepDependencies
from app.rag.formatting import normalize_text, resolve_context_chunks
from app.rag.prompts import NO_RELEVANT_INFORMATION_MESSAGE, SAFE_INSUFFICIENT_CONTEXT_MESSAGE


def _resolve_settings(settings: Settings | None = None) -> Settings:
    from app.core.config import get_settings

    return settings if settings is not None else get_settings()


def validate_citations_node(
    state: Mapping[str, Any],
    *,
    settings: Settings | None = None,
    deps: QueryStepDependencies,
) -> dict[str, Any]:
    _resolve_settings(settings)
    answer = state.get("answer")
    context_chunks = resolve_context_chunks(state)
    validation_output = deps.citation_validation.validate_answer_citations(
        str(answer) if answer is not None else None,
        context_chunks,
    )
    metrics = dict(state.get("retrieval_metrics") or {})
    metrics.update(
        deps.citation_validation.evidence_group_coverage(
            context_chunks=context_chunks,
            cited_keys=validation_output.validation.cited_keys,
        )
    )
    return {
        "citation_validation_result": validation_output.validation,
        "sources": validation_output.sources,
        "retrieval_metrics": metrics,
    }


def verify_grounding_node(
    state: Mapping[str, Any],
    *,
    settings: Settings | None = None,
    deps: QueryStepDependencies,
    shopaikey_client: Any | None = None,
) -> dict[str, Any]:
    resolved_settings = _resolve_settings(settings)
    answer = normalize_text(state.get("answer"))
    validation = state.get("citation_validation_result")
    verification_attempt_count = int(state.get("verification_attempt_count") or 0) + 1

    if answer is None:
        return {
            "answer_verified": False,
            "verification_attempt_count": verification_attempt_count,
        }

    if answer == NO_RELEVANT_INFORMATION_MESSAGE or "indexed documents do not contain enough information" in answer.lower():
        return {
            "grounding_result": deps.grounding.GroundingResult(
                grounded=True,
                score=1.0,
                unsupported_claims=[],
                missing_citations=[],
            ),
            "answer_verified": True,
            "verification_attempt_count": verification_attempt_count,
        }

    citations_valid = bool(getattr(validation, "valid", False))
    cited_keys = list(getattr(validation, "cited_keys", []) or [])
    evidence = deps.grounding.cited_evidence_from_sources(
        context_chunks=resolve_context_chunks(state),
        cited_keys=cited_keys,
    )
    if not citations_valid or not evidence:
        result = deps.grounding.GroundingResult(
            grounded=False,
            score=0.0,
            unsupported_claims=[],
            missing_citations=[] if cited_keys else ["valid citations"],
        )
        return {
            "grounding_result": result,
            "answer_verified": False,
            "verification_attempt_count": verification_attempt_count,
        }

    try:
        result = deps.grounding.verify_answer_grounding(
            answer,
            evidence=evidence,
            settings=resolved_settings,
            shopaikey_client=shopaikey_client,
        )
    except deps.grounding.GroundingProviderError:
        return {
            "answer_verified": False,
            "grounding_provider_failed": True,
            "verification_attempt_count": verification_attempt_count,
        }

    return {
        "grounding_result": result,
        "answer_verified": result.grounded and result.score >= resolved_settings.GROUNDING_MIN_SCORE,
        "verification_attempt_count": verification_attempt_count,
    }


def finalize_answer_node(
    state: Mapping[str, Any],
    *,
    settings: Settings | None = None,
    deps: QueryStepDependencies,
) -> dict[str, Any]:
    _resolve_settings(settings)
    if state.get("answer_verified") is False:
        return {
            "answer": SAFE_INSUFFICIENT_CONTEXT_MESSAGE,
            "sources": [],
        }
    return {}
