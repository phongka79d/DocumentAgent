from app.core.config import Settings
from app.services import retrieval_diversity


def _settings() -> Settings:
    return Settings(
        _env_file=None,
        RETRIEVAL_CONTEXT_WINDOW=1,
        CHUNK_SIZE_TOKENS=500,
        CHUNK_OVERLAP_TOKENS=150,
    )


def _candidate(chunk_id: str, index: int, content: str) -> dict:
    return {
        "chunk_id": chunk_id,
        "document_id": "document-a",
        "chunk_index": index,
        "content": content,
        "section_path": [],
    }


def test_assign_evidence_groups_clusters_adjacent_overlapping_chunks():
    shared = "shared overlap words from a continued paragraph"
    grouped = retrieval_diversity.assign_evidence_groups(
        [
            _candidate("a", 10, f"opening {shared}"),
            _candidate("b", 11, f"{shared} closing"),
            _candidate("c", 30, "independent evidence elsewhere"),
        ],
        settings=_settings(),
    )

    assert grouped[0]["evidence_group_id"] == grouped[1]["evidence_group_id"]
    assert grouped[0]["evidence_group_id"] != grouped[2]["evidence_group_id"]


def test_select_group_diverse_keeps_first_ranked_item_and_distinct_groups():
    candidates = [
        {**_candidate("top", 0, "top"), "evidence_group_id": "g1"},
        {**_candidate("duplicate", 1, "duplicate"), "evidence_group_id": "g1"},
        {**_candidate("second", 20, "second"), "evidence_group_id": "g2"},
        {**_candidate("third", 40, "third"), "evidence_group_id": "g3"},
    ]

    selected = retrieval_diversity.select_group_diverse(candidates, limit=3)

    assert [item["chunk_id"] for item in selected] == ["top", "second", "third"]


def test_select_group_diverse_fills_by_original_rank_after_group_coverage():
    candidates = [
        {**_candidate("a", 0, "a"), "evidence_group_id": "g1"},
        {**_candidate("b", 1, "b"), "evidence_group_id": "g1"},
        {**_candidate("c", 20, "c"), "evidence_group_id": "g2"},
    ]

    selected = retrieval_diversity.select_group_diverse(candidates, limit=3)

    assert [item["chunk_id"] for item in selected] == ["a", "c", "b"]
