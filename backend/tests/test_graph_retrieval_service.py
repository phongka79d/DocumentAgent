import sys
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services import graph_retrieval_service


class FakeGraphRepository:
    def __init__(self, entity_rows=None, relationship_rows=None, chunk_rows=None) -> None:
        self.entity_rows = entity_rows or []
        self.relationship_rows = relationship_rows or []
        self.chunk_rows = chunk_rows or []
        self.entity_calls = []
        self.relationship_calls = []
        self.chunk_calls = []

    def list_document_entities(self, document_ids):
        self.entity_calls.append(document_ids)
        return self.entity_rows

    def list_document_relationships(self, document_ids):
        self.relationship_calls.append(document_ids)
        return self.relationship_rows

    def list_document_chunks_by_ids(self, chunk_ids):
        self.chunk_calls.append(chunk_ids)
        return self.chunk_rows


def _settings(top_k: int = 8) -> SimpleNamespace:
    return SimpleNamespace(retrieval_graph_top_k=top_k)


def test_graph_retrieval_service_imports_contract() -> None:
    assert graph_retrieval_service.GraphRetrievalCandidate is not None
    assert callable(graph_retrieval_service.find_graph_candidates)


def test_find_graph_candidates_returns_no_matches_for_empty_question_before_repository(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = FakeGraphRepository()
    monkeypatch.setattr(graph_retrieval_service, "get_settings", lambda: _settings())

    candidates = graph_retrieval_service.find_graph_candidates("   ", repository=repository)

    assert candidates == []
    assert repository.entity_calls == []
    assert repository.relationship_calls == []


def test_find_graph_candidates_uses_default_top_k_and_mockable_graph_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document_id = UUID("11111111-1111-1111-1111-111111111111")
    entity_id = UUID("22222222-2222-2222-2222-222222222222")
    repository = FakeGraphRepository(
        entity_rows=[
            {
                "id": str(entity_id),
                "document_id": str(document_id),
                "chunk_id": "33333333-3333-3333-3333-333333333333",
                "entity_name": "Probation",
            }
        ],
        relationship_rows=[
            {
                "id": "44444444-4444-4444-4444-444444444444",
                "document_id": str(document_id),
                "source_type": "chunk",
                "source_id": "33333333-3333-3333-3333-333333333333",
                "target_type": "entity",
                "target_id": str(entity_id),
                "weight": 1.0,
            }
        ],
        chunk_rows=[
            {
                "id": "33333333-3333-3333-3333-333333333333",
                "document_id": str(document_id),
                "chunk_index": 2,
                "content": "The probation period is six months.",
                "page_number": 4,
                "section_title": "Probation",
            }
        ],
    )
    monkeypatch.setattr(graph_retrieval_service, "get_settings", lambda: _settings(12))

    candidates = graph_retrieval_service.find_graph_candidates(
        "What is the probation period?",
        repository=repository,
    )

    assert len(candidates) == 1
    assert candidates[0].chunk_id == UUID("33333333-3333-3333-3333-333333333333")
    assert candidates[0].document_id == document_id
    assert candidates[0].content == "The probation period is six months."
    assert candidates[0].page_number == 4
    assert candidates[0].section_title == "Probation"
    assert candidates[0].chunk_index == 2
    assert candidates[0].graph_relevance == pytest.approx(0.72)
    assert candidates[0].retrieval_reason == (
        "Graph relationship path from matched entity: Probation"
    )
    assert candidates[0].metadata["matched_entity_id"] == str(entity_id)
    assert candidates[0].metadata["matched_entity_name"] == "Probation"
    assert candidates[0].metadata["graph_path_count"] == 2
    assert {
        evidence["path_type"] for evidence in candidates[0].metadata["graph_evidence"]
    } == {"matched_entity_chunk", "relationship_path"}
    assert repository.entity_calls == [None]
    assert repository.relationship_calls == [[document_id]]
    assert repository.chunk_calls == [[UUID("33333333-3333-3333-3333-333333333333")]]


def test_find_graph_candidates_matches_entity_names_case_insensitively_with_punctuation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document_id = UUID("11111111-1111-1111-1111-111111111111")
    repository = FakeGraphRepository(
        entity_rows=[
            {
                "id": "22222222-2222-2222-2222-222222222222",
                "document_id": str(document_id),
                "chunk_id": "33333333-3333-3333-3333-333333333333",
                "entity_name": "Probation Period",
                "entity_type": "policy",
            }
        ],
    )
    monkeypatch.setattr(graph_retrieval_service, "get_settings", lambda: _settings())

    candidates = graph_retrieval_service.find_graph_candidates(
        "WHAT is the probation-period?",
        repository=repository,
    )

    assert len(candidates) == 1
    assert candidates[0].retrieval_reason == "Matched entity: Probation Period"
    assert candidates[0].metadata["matched_entity_id"] == (
        "22222222-2222-2222-2222-222222222222"
    )
    assert candidates[0].metadata["matched_entity_name"] == "Probation Period"
    assert candidates[0].metadata["graph_path_count"] == 1
    assert candidates[0].metadata["graph_evidence"][0]["path_type"] == (
        "matched_entity_chunk"
    )
    assert 0.0 < candidates[0].graph_relevance <= 1.0


def test_find_graph_candidates_returns_no_matches_for_irrelevant_question(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document_id = UUID("11111111-1111-1111-1111-111111111111")
    repository = FakeGraphRepository(
        entity_rows=[
            {
                "id": "22222222-2222-2222-2222-222222222222",
                "document_id": str(document_id),
                "chunk_id": "33333333-3333-3333-3333-333333333333",
                "entity_name": "Probation Period",
            }
        ],
    )
    monkeypatch.setattr(graph_retrieval_service, "get_settings", lambda: _settings())

    candidates = graph_retrieval_service.find_graph_candidates(
        "How many holidays are listed?",
        repository=repository,
    )

    assert candidates == []


def test_find_graph_candidates_filters_loaded_entities_to_selected_documents(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    selected_document_id = UUID("44444444-4444-4444-4444-444444444444")
    other_document_id = UUID("55555555-5555-5555-5555-555555555555")
    repository = FakeGraphRepository(
        entity_rows=[
            {
                "id": "66666666-6666-6666-6666-666666666666",
                "document_id": str(other_document_id),
                "chunk_id": "77777777-7777-7777-7777-777777777777",
                "entity_name": "Probation Period",
            },
            {
                "id": "88888888-8888-8888-8888-888888888888",
                "document_id": str(selected_document_id),
                "chunk_id": "99999999-9999-9999-9999-999999999999",
                "entity_name": "Probation Period",
            },
        ],
    )
    monkeypatch.setattr(graph_retrieval_service, "get_settings", lambda: _settings())

    candidates = graph_retrieval_service.find_graph_candidates(
        "probation period",
        document_ids=[selected_document_id],
        repository=repository,
    )

    assert [candidate.document_id for candidate in candidates] == [selected_document_id]
    assert [candidate.chunk_id for candidate in candidates] == [
        UUID("99999999-9999-9999-9999-999999999999")
    ]


def test_find_graph_candidates_expands_entity_to_related_chunk(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document_id = UUID("11111111-1111-1111-1111-111111111111")
    entity_id = UUID("22222222-2222-2222-2222-222222222222")
    related_chunk_id = UUID("33333333-3333-3333-3333-333333333333")
    repository = FakeGraphRepository(
        entity_rows=[
            {
                "id": str(entity_id),
                "document_id": str(document_id),
                "chunk_id": "44444444-4444-4444-4444-444444444444",
                "entity_name": "Probation",
            }
        ],
        relationship_rows=[
            {
                "id": "55555555-5555-5555-5555-555555555555",
                "document_id": str(document_id),
                "source_type": "entity",
                "source_id": str(entity_id),
                "target_type": "chunk",
                "target_id": str(related_chunk_id),
                "relationship_type": "chunk_mentions_entity",
                "weight": 0.9,
            }
        ],
        chunk_rows=[
            {
                "id": str(related_chunk_id),
                "document_id": str(document_id),
                "chunk_index": 3,
                "content": "Related graph-only chunk.",
            }
        ],
    )
    monkeypatch.setattr(graph_retrieval_service, "get_settings", lambda: _settings())

    candidates = graph_retrieval_service.find_graph_candidates(
        "probation",
        repository=repository,
    )

    related_candidate = next(
        candidate for candidate in candidates if candidate.chunk_id == related_chunk_id
    )
    assert related_candidate.content == "Related graph-only chunk."
    assert related_candidate.metadata["graph_evidence"][0]["relationship_ids"] == [
        "55555555-5555-5555-5555-555555555555"
    ]
    assert related_candidate.metadata["graph_evidence"][0]["relationship_weight"] == 0.9
    assert related_candidate.graph_relevance == pytest.approx(0.72)


def test_find_graph_candidates_expands_entity_to_entity_to_chunk(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document_id = UUID("11111111-1111-1111-1111-111111111111")
    source_entity_id = UUID("22222222-2222-2222-2222-222222222222")
    related_entity_id = UUID("33333333-3333-3333-3333-333333333333")
    related_chunk_id = UUID("44444444-4444-4444-4444-444444444444")
    repository = FakeGraphRepository(
        entity_rows=[
            {
                "id": str(source_entity_id),
                "document_id": str(document_id),
                "chunk_id": "55555555-5555-5555-5555-555555555555",
                "entity_name": "Probation",
            }
        ],
        relationship_rows=[
            {
                "id": "66666666-6666-6666-6666-666666666666",
                "document_id": str(document_id),
                "source_type": "entity",
                "source_id": str(source_entity_id),
                "target_type": "entity",
                "target_id": str(related_entity_id),
                "relationship_type": "entity_related_to_entity",
                "weight": 0.8,
            },
            {
                "id": "77777777-7777-7777-7777-777777777777",
                "document_id": str(document_id),
                "source_type": "chunk",
                "source_id": str(related_chunk_id),
                "target_type": "entity",
                "target_id": str(related_entity_id),
                "relationship_type": "chunk_mentions_entity",
                "weight": 1.0,
            },
        ],
        chunk_rows=[
            {
                "id": str(related_chunk_id),
                "document_id": str(document_id),
                "chunk_index": 4,
                "content": "Two-hop graph-only chunk.",
            }
        ],
    )
    monkeypatch.setattr(graph_retrieval_service, "get_settings", lambda: _settings())

    candidates = graph_retrieval_service.find_graph_candidates(
        "probation",
        repository=repository,
    )

    related_candidate = next(
        candidate for candidate in candidates if candidate.chunk_id == related_chunk_id
    )
    relationship_evidence = next(
        evidence
        for evidence in related_candidate.metadata["graph_evidence"]
        if evidence["path_type"] == "relationship_path"
    )
    assert relationship_evidence["path_depth"] == 2
    assert relationship_evidence["relationship_types"] == [
        "entity_related_to_entity",
        "chunk_mentions_entity",
    ]
    assert relationship_evidence["relationship_weight"] == 0.9
    assert candidates[0].graph_relevance == pytest.approx(0.7)


def test_find_graph_candidates_deduplicates_duplicate_graph_paths(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document_id = UUID("11111111-1111-1111-1111-111111111111")
    entity_id = UUID("22222222-2222-2222-2222-222222222222")
    chunk_id = UUID("33333333-3333-3333-3333-333333333333")
    duplicate_relationship = {
        "id": "44444444-4444-4444-4444-444444444444",
        "document_id": str(document_id),
        "source_type": "entity",
        "source_id": str(entity_id),
        "target_type": "chunk",
        "target_id": str(chunk_id),
        "relationship_type": "chunk_mentions_entity",
        "weight": 1.0,
    }
    repository = FakeGraphRepository(
        entity_rows=[
            {
                "id": str(entity_id),
                "document_id": str(document_id),
                "chunk_id": str(chunk_id),
                "entity_name": "Probation",
            }
        ],
        relationship_rows=[duplicate_relationship, dict(duplicate_relationship)],
        chunk_rows=[
            {
                "id": str(chunk_id),
                "document_id": str(document_id),
                "content": "Duplicate path target.",
            }
        ],
    )
    monkeypatch.setattr(graph_retrieval_service, "get_settings", lambda: _settings())

    candidates = graph_retrieval_service.find_graph_candidates(
        "probation",
        repository=repository,
    )

    assert len(candidates) == 1
    assert candidates[0].metadata["graph_path_count"] == 2
    assert [
        evidence["path_type"] for evidence in candidates[0].metadata["graph_evidence"]
    ] == ["matched_entity_chunk", "relationship_path"]
    assert candidates[0].graph_relevance == pytest.approx(0.72)


def test_find_graph_candidates_clamps_missing_and_out_of_bounds_weights(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document_id = UUID("11111111-1111-1111-1111-111111111111")
    entity_id = UUID("22222222-2222-2222-2222-222222222222")
    weak_chunk_id = UUID("33333333-3333-3333-3333-333333333333")
    strong_chunk_id = UUID("44444444-4444-4444-4444-444444444444")
    missing_chunk_id = UUID("55555555-5555-5555-5555-555555555555")
    repository = FakeGraphRepository(
        entity_rows=[
            {
                "id": str(entity_id),
                "document_id": str(document_id),
                "chunk_id": "66666666-6666-6666-6666-666666666666",
                "entity_name": "Probation",
            }
        ],
        relationship_rows=[
            {
                "id": "77777777-7777-7777-7777-777777777777",
                "document_id": str(document_id),
                "source_type": "entity",
                "source_id": str(entity_id),
                "target_type": "chunk",
                "target_id": str(weak_chunk_id),
                "relationship_type": "chunk_mentions_entity",
                "weight": 0.1,
            },
            {
                "id": "88888888-8888-8888-8888-888888888888",
                "document_id": str(document_id),
                "source_type": "entity",
                "source_id": str(entity_id),
                "target_type": "chunk",
                "target_id": str(strong_chunk_id),
                "relationship_type": "chunk_mentions_entity",
                "weight": 1.4,
            },
            {
                "id": "99999999-9999-9999-9999-999999999999",
                "document_id": str(document_id),
                "source_type": "entity",
                "source_id": str(entity_id),
                "target_type": "chunk",
                "target_id": str(missing_chunk_id),
                "relationship_type": "chunk_mentions_entity",
            },
        ],
        chunk_rows=[
            {
                "id": str(weak_chunk_id),
                "document_id": str(document_id),
                "chunk_index": 5,
                "content": "Weakly related chunk.",
            },
            {
                "id": str(strong_chunk_id),
                "document_id": str(document_id),
                "chunk_index": 6,
                "content": "Strongly related chunk.",
            },
            {
                "id": str(missing_chunk_id),
                "document_id": str(document_id),
                "chunk_index": 7,
                "content": "Missing weight chunk.",
            },
        ],
    )
    monkeypatch.setattr(graph_retrieval_service, "get_settings", lambda: _settings())

    candidates = graph_retrieval_service.find_graph_candidates(
        "probation",
        repository=repository,
    )

    by_chunk_id = {candidate.chunk_id: candidate for candidate in candidates}
    assert by_chunk_id[strong_chunk_id].graph_relevance == pytest.approx(0.74)
    assert by_chunk_id[weak_chunk_id].graph_relevance == pytest.approx(0.56)
    assert by_chunk_id[missing_chunk_id].graph_relevance == pytest.approx(0.54)
    assert by_chunk_id[strong_chunk_id].graph_relevance > by_chunk_id[weak_chunk_id].graph_relevance
    assert by_chunk_id[weak_chunk_id].graph_relevance > by_chunk_id[missing_chunk_id].graph_relevance
    assert all(0.0 <= candidate.graph_relevance <= 1.0 for candidate in candidates)


def test_find_graph_candidates_excludes_relationship_chunks_outside_selected_documents(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    selected_document_id = UUID("11111111-1111-1111-1111-111111111111")
    other_document_id = UUID("22222222-2222-2222-2222-222222222222")
    entity_id = UUID("33333333-3333-3333-3333-333333333333")
    other_chunk_id = UUID("44444444-4444-4444-4444-444444444444")
    repository = FakeGraphRepository(
        entity_rows=[
            {
                "id": str(entity_id),
                "document_id": str(selected_document_id),
                "chunk_id": "55555555-5555-5555-5555-555555555555",
                "entity_name": "Probation",
            }
        ],
        relationship_rows=[
            {
                "id": "66666666-6666-6666-6666-666666666666",
                "document_id": str(other_document_id),
                "source_type": "entity",
                "source_id": str(entity_id),
                "target_type": "chunk",
                "target_id": str(other_chunk_id),
                "relationship_type": "chunk_mentions_entity",
                "weight": 1.0,
            }
        ],
        chunk_rows=[
            {
                "id": str(other_chunk_id),
                "document_id": str(other_document_id),
                "content": "Must be filtered.",
            }
        ],
    )
    monkeypatch.setattr(graph_retrieval_service, "get_settings", lambda: _settings())

    candidates = graph_retrieval_service.find_graph_candidates(
        "probation",
        document_ids=[selected_document_id],
        repository=repository,
    )

    assert other_chunk_id not in {candidate.chunk_id for candidate in candidates}
    assert {candidate.document_id for candidate in candidates} == {selected_document_id}


def test_find_graph_candidates_preserves_selected_document_filter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    selected_document_id = UUID("44444444-4444-4444-4444-444444444444")
    repository = FakeGraphRepository()
    monkeypatch.setattr(graph_retrieval_service, "get_settings", lambda: _settings())

    graph_retrieval_service.find_graph_candidates(
        "Find policy terms",
        document_ids=[selected_document_id],
        top_k=3,
        repository=repository,
    )

    assert repository.entity_calls == [[selected_document_id]]
    assert repository.relationship_calls == [[selected_document_id]]


@pytest.mark.parametrize("top_k", [0, 51])
def test_find_graph_candidates_rejects_invalid_top_k_before_repository(
    monkeypatch: pytest.MonkeyPatch,
    top_k: int,
) -> None:
    repository = FakeGraphRepository()
    monkeypatch.setattr(graph_retrieval_service, "get_settings", lambda: _settings())

    with pytest.raises(graph_retrieval_service.GraphRetrievalValidationError) as exc_info:
        graph_retrieval_service.find_graph_candidates(
            "valid graph question",
            top_k=top_k,
            repository=repository,
        )

    assert str(exc_info.value) == "top_k must be between 1 and 50."
    assert repository.entity_calls == []
    assert repository.relationship_calls == []
