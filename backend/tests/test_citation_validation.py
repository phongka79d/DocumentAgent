from __future__ import annotations

from app.services.citation_validation import (
    assign_citation_keys,
    validate_answer_citations,
)


def _chunks() -> list[dict[str, object]]:
    return [
        {
            "document_id": "doc-a",
            "chunk_id": "chunk-a",
            "file_name": "alpha.pdf",
            "chunk_index": 0,
            "content": "Alpha pricing is usage based.",
        },
        {
            "document_id": "doc-b",
            "chunk_id": "chunk-b",
            "file_name": "bravo.pdf",
            "chunk_index": 1,
            "content": "Bravo enterprise pricing is custom.",
        },
    ]


def test_assign_citation_keys_after_context_order():
    keyed_chunks = assign_citation_keys(_chunks())

    assert [chunk["citation_key"] for chunk in keyed_chunks] == ["S1", "S2"]
    assert [chunk["chunk_id"] for chunk in keyed_chunks] == ["chunk-a", "chunk-b"]


def test_valid_markers_map_to_exact_chunk_ids_in_first_citation_order():
    keyed_chunks = assign_citation_keys(_chunks())

    result = validate_answer_citations(
        "Enterprise pricing is custom [S2]. Usage pricing also applies [S1].",
        keyed_chunks,
    )

    assert result.validation.valid is True
    assert result.validation.cited_keys == ["S2", "S1"]
    assert result.validation.cited_chunk_ids == ["chunk-b", "chunk-a"]
    assert [source["chunk_id"] for source in result.sources] == ["chunk-b", "chunk-a"]


def test_unknown_marker_fails_validation_and_returns_only_known_cited_sources():
    keyed_chunks = assign_citation_keys(_chunks())

    result = validate_answer_citations(
        "Usage pricing applies [S1], and another claim cites an unknown chunk [S3].",
        keyed_chunks,
    )

    assert result.validation.valid is False
    assert result.validation.cited_keys == ["S1"]
    assert result.validation.cited_chunk_ids == ["chunk-a"]
    assert result.validation.invalid_keys == ["S3"]
    assert [source["chunk_id"] for source in result.sources] == ["chunk-a"]


def test_malformed_marker_fails_validation():
    keyed_chunks = assign_citation_keys(_chunks())

    result = validate_answer_citations("Usage pricing applies [S01].", keyed_chunks)

    assert result.validation.valid is False
    assert result.validation.cited_keys == []
    assert result.validation.invalid_keys == ["S01"]
    assert result.sources == []


def test_non_empty_factual_answer_without_valid_citation_is_invalid():
    keyed_chunks = assign_citation_keys(_chunks())

    result = validate_answer_citations(
        "Usage pricing applies according to alpha.pdf and the Pricing heading.",
        keyed_chunks,
    )

    assert result.validation.valid is False
    assert result.validation.missing_citations is True
    assert result.sources == []


def test_duplicate_markers_are_deduplicated_in_first_citation_order():
    keyed_chunks = assign_citation_keys(_chunks())

    result = validate_answer_citations(
        "Usage pricing applies [S1]. Usage pricing applies again [S1]. Enterprise is custom [S2].",
        keyed_chunks,
    )

    assert result.validation.valid is True
    assert result.validation.cited_keys == ["S1", "S2"]
    assert result.validation.cited_chunk_ids == ["chunk-a", "chunk-b"]
    assert [source["chunk_id"] for source in result.sources] == ["chunk-a", "chunk-b"]


def test_safe_insufficient_context_answer_needs_no_citation():
    keyed_chunks = assign_citation_keys(_chunks())

    result = validate_answer_citations(
        "The indexed documents do not contain enough information to answer.",
        keyed_chunks,
    )

    assert result.validation.valid is True
    assert result.validation.missing_citations is False
    assert result.sources == []


def test_cited_evidence_group_coverage_counts_distinct_groups():
    from app.services import citation_validation

    context = [
        {"chunk_id": "a", "citation_key": "S1", "evidence_group_id": "g1"},
        {"chunk_id": "b", "citation_key": "S2", "evidence_group_id": "g1"},
        {"chunk_id": "c", "citation_key": "S3", "evidence_group_id": "g2"},
    ]

    metrics = citation_validation.evidence_group_coverage(
        context_chunks=context,
        cited_keys=["S1", "S2"],
    )

    assert metrics == {
        "selected_evidence_group_count": 2,
        "cited_evidence_group_count": 1,
        "evidence_group_coverage_rate": 0.5,
    }
