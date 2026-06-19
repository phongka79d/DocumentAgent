from __future__ import annotations

from app.chunking.heading_detection import is_heading_candidate, score_heading_candidate
from app.parsing.structure import build_heading_block, build_paragraph_block


def _paragraph_block(text: str, metadata: dict | None = None) -> dict:
    block = build_paragraph_block(text, page_number=None)
    if metadata:
        block["metadata"].update(metadata)
    return block


def test_explicit_heading_type_adds_five_points():
    heading_block = build_heading_block(
        "Overview",
        heading_level=2,
        page_number=None,
        metadata=None,
    )
    paragraph_block = _paragraph_block("Overview")

    heading_score = score_heading_candidate(heading_block, None, None)
    paragraph_score = score_heading_candidate(paragraph_block, None, None)

    assert heading_score - paragraph_score == 5
    assert is_heading_candidate(heading_block) is True


def test_markdown_heading_marker_adds_four_points():
    marker_block = _paragraph_block("# Overview")
    plain_block = _paragraph_block("Overview")

    assert score_heading_candidate(marker_block, None, None) - score_heading_candidate(
        plain_block,
        None,
        None,
    ) == 4


def test_numbered_heading_pattern_adds_three_points():
    numbered_block = _paragraph_block("2.3 Pricing")
    plain_block = _paragraph_block("Pricing")

    assert score_heading_candidate(numbered_block, None, None) - score_heading_candidate(
        plain_block,
        None,
        None,
    ) == 3
    assert is_heading_candidate(numbered_block) is True


def test_table_of_contents_metadata_adds_two_points():
    plain_block = _paragraph_block("Appendix")
    toc_block = _paragraph_block("Appendix", {"is_toc_entry": True})

    assert score_heading_candidate(toc_block, None, None) - score_heading_candidate(
        plain_block,
        None,
        None,
    ) == 2


def test_short_unpunctuated_text_adds_one_point():
    block = _paragraph_block("Pricing")

    assert score_heading_candidate(block, None, None) == 1
    assert is_heading_candidate(block) is False


def test_uppercase_text_adds_one_point():
    block = _paragraph_block("PRICING")

    assert score_heading_candidate(block, None, None) == 2


def test_bold_metadata_adds_one_point():
    plain_block = _paragraph_block("Pricing")
    bold_block = _paragraph_block("Pricing", {"is_bold": True})

    assert score_heading_candidate(bold_block, None, None) - score_heading_candidate(
        plain_block,
        None,
        None,
    ) == 1


def test_larger_font_size_than_nearby_body_text_adds_one_point():
    previous_block = _paragraph_block("Body copy")
    previous_block["metadata"]["font_size"] = 12
    next_block = _paragraph_block("More body copy")
    next_block["metadata"]["font_size"] = 11

    plain_block = _paragraph_block("Section")
    large_font_block = _paragraph_block("Section")
    large_font_block["metadata"]["font_size"] = 18

    assert score_heading_candidate(large_font_block, previous_block, next_block) - score_heading_candidate(
        plain_block,
        previous_block,
        next_block,
    ) == 1


def test_sentence_ending_punctuation_penalizes_heading_score():
    sentence_block = _paragraph_block(
        "Pricing is based on usage tiers and customer volume for enterprise clients."
    )

    assert score_heading_candidate(sentence_block, None, None) == -2
    assert is_heading_candidate(sentence_block) is False


def test_long_uppercase_paragraph_does_not_pass_threshold():
    long_uppercase_block = _paragraph_block(
        "ALPHA BETA GAMMA DELTA EPSILON ZETA ETA THETA IOTA KAPPA LAMBDA MU NU XI OMICRON PI RHO SIGMA TAU"
    )

    assert score_heading_candidate(long_uppercase_block, None, None) == -2
    assert is_heading_candidate(long_uppercase_block) is False


def test_default_threshold_accepts_score_four_candidates():
    block = _paragraph_block("2.3 Pricing")

    assert is_heading_candidate(block) is True
    assert is_heading_candidate(block, threshold=5) is False
