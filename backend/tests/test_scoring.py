import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.utils.scoring import (
    FINAL_SCORE_WEIGHTS,
    clamp_score,
    final_score,
    keyword_overlap_score,
    metadata_match_score,
    position_score,
    recency_or_position_score,
)


def test_final_score_weights_are_exact_plan_8_values() -> None:
    assert FINAL_SCORE_WEIGHTS == {
        "semantic_similarity": 0.45,
        "graph_relevance": 0.25,
        "keyword_overlap": 0.15,
        "metadata_match": 0.10,
        "recency_or_position_score": 0.05,
    }


def test_clamp_score_normalizes_invalid_and_out_of_range_values() -> None:
    assert clamp_score(-0.5) == 0.0
    assert clamp_score(0.25) == 0.25
    assert clamp_score(2.0) == 1.0
    assert clamp_score(None) == 0.0
    assert clamp_score("not-a-score") == 0.0
    assert clamp_score(math.nan) == 0.0
    assert clamp_score(math.inf) == 0.0


def test_keyword_overlap_score_uses_unique_question_token_coverage() -> None:
    score = keyword_overlap_score(
        "Alpha beta beta gamma",
        "Alpha and gamma are present, but not the other term.",
    )

    assert score == 2 / 3


def test_metadata_match_score_combines_document_page_section_and_file_matches() -> None:
    candidate = {
        "document_id": "doc-1",
        "page_number": 3,
        "section_title": "Policy Benefits",
        "file_name": "contract.pdf",
    }

    score = metadata_match_score(
        "Show contract policy on page 3",
        candidate,
        selected_document_ids=["doc-1"],
    )

    assert score == pytest.approx(0.9)


def test_position_score_rewards_early_summary_and_date_metadata_with_clamp() -> None:
    candidate = {
        "chunk_index": 0,
        "section_title": "Executive Summary",
        "metadata": {"updated_at": "2026-06-08T00:00:00Z"},
    }

    assert position_score(candidate) == 1.0
    assert recency_or_position_score(candidate) == 1.0


def test_position_score_returns_zero_for_late_chunks_without_position_signals() -> None:
    candidate = {
        "chunk_index": 12,
        "page_number": 9,
        "section_title": "Appendix",
        "metadata": {},
    }

    assert position_score(candidate) == 0.0


def test_final_score_all_one_components_produces_one() -> None:
    components = {
        "semantic_similarity": 1.0,
        "graph_relevance": 1.0,
        "keyword_overlap": 1.0,
        "metadata_match": 1.0,
        "recency_or_position_score": 1.0,
    }

    assert final_score(components) == 1.0


def test_final_score_all_zero_components_produces_zero() -> None:
    components = {
        "semantic_similarity": 0.0,
        "graph_relevance": 0.0,
        "keyword_overlap": 0.0,
        "metadata_match": 0.0,
        "recency_or_position_score": 0.0,
    }

    assert final_score(components) == 0.0


def test_final_score_uses_exact_weighted_formula_for_mixed_components() -> None:
    components = {
        "semantic_similarity": 0.8,
        "graph_relevance": 0.6,
        "keyword_overlap": 0.4,
        "metadata_match": 0.2,
        "recency_or_position_score": 0.1,
    }

    expected = (0.45 * 0.8) + (0.25 * 0.6) + (0.15 * 0.4) + (0.10 * 0.2) + (0.05 * 0.1)

    assert final_score(components) == expected


def test_final_score_clamps_invalid_component_bounds_before_weighting() -> None:
    components = {
        "semantic_similarity": 2.0,
        "graph_relevance": -4.0,
        "keyword_overlap": math.nan,
        "metadata_match": "invalid",
        "recency_or_position_score": math.inf,
    }

    assert final_score(components) == 0.45
