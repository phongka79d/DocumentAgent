import sys
from pathlib import Path
from types import SimpleNamespace
import logging
from unittest.mock import Mock
from uuid import UUID

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.schemas.retrieval import RetrievalResult, SearchResponse
from app.services import hybrid_retrieval_service
from app.services.graph_retrieval_service import (
    GraphRetrievalCandidate,
    GraphRetrievalDependencyError,
)
from app.services.retrieval_service import RetrievalDependencyError
from app.utils.scoring import final_score


def _settings(
    semantic_top_k: int = 11,
    graph_top_k: int = 7,
    final_top_k: int = 5,
    enable_rerank: bool = False,
) -> SimpleNamespace:
    return SimpleNamespace(
        retrieval_semantic_top_k=semantic_top_k,
        retrieval_graph_top_k=graph_top_k,
        retrieval_final_top_k=final_top_k,
        enable_rerank=enable_rerank,
    )


def _semantic_candidate(
    chunk_id: str,
    *,
    document_id: str = "22222222-2222-2222-2222-222222222222",
    content: str | None = "semantic content",
    semantic_similarity: float = 0.82,
    file_name: str | None = "semantic.pdf",
    page_number: int | None = 2,
    section_title: str | None = "Semantic Section",
    chunk_index: int | None = 3,
) -> RetrievalResult:
    return RetrievalResult(
        chunk_id=UUID(chunk_id),
        document_id=UUID(document_id),
        file_name=file_name,
        file_type="application/pdf" if file_name else None,
        content=content,
        content_preview=content[:40] if content else None,
        page_number=page_number,
        section_title=section_title,
        chunk_index=chunk_index,
        semantic_similarity=semantic_similarity,
    )


def _graph_candidate(
    chunk_id: str,
    *,
    document_id: str = "22222222-2222-2222-2222-222222222222",
    content: str | None = "graph content",
    graph_relevance: float = 0.67,
    file_name: str | None = None,
    page_number: int | None = 4,
    section_title: str | None = "Graph Section",
    chunk_index: int | None = 5,
    metadata: dict[str, object] | None = None,
) -> GraphRetrievalCandidate:
    return GraphRetrievalCandidate(
        chunk_id=UUID(chunk_id),
        document_id=UUID(document_id),
        content=content,
        file_name=file_name,
        page_number=page_number,
        section_title=section_title,
        chunk_index=chunk_index,
        graph_relevance=graph_relevance,
        retrieval_reason="Matched entity: policy",
        metadata=metadata,
    )


def test_hybrid_retrieval_service_imports_contract() -> None:
    assert callable(hybrid_retrieval_service.retrieve_hybrid)
    assert hybrid_retrieval_service.HybridRetrievalValidationError is not None


def test_retrieve_hybrid_rejects_empty_question_before_dependency_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    semantic_search = Mock()
    graph_retrieval = Mock()
    monkeypatch.setattr(hybrid_retrieval_service, "get_settings", lambda: _settings())

    with pytest.raises(hybrid_retrieval_service.HybridRetrievalValidationError) as exc_info:
        hybrid_retrieval_service.retrieve_hybrid(
            "   ",
            semantic_search=semantic_search,
            graph_retrieval=graph_retrieval,
        )

    assert str(exc_info.value) == "Question must be non-empty."
    semantic_search.assert_not_called()
    graph_retrieval.assert_not_called()


def test_retrieve_hybrid_calls_semantic_and_graph_with_configured_top_k_and_filters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document_ids = [UUID("11111111-1111-1111-1111-111111111111")]
    semantic_search = Mock(
        return_value=SearchResponse(question="What is the policy?", results=[])
    )
    graph_retrieval = Mock(return_value=[])

    monkeypatch.setattr(
        hybrid_retrieval_service,
        "get_settings",
        lambda: _settings(semantic_top_k=13, graph_top_k=9, final_top_k=4),
    )

    response = hybrid_retrieval_service.retrieve_hybrid(
        "  What is the policy?  ",
        document_ids=document_ids,
        semantic_search=semantic_search,
        graph_retrieval=graph_retrieval,
    )

    assert response.question == "What is the policy?"
    assert response.candidates == []
    semantic_search.assert_called_once_with(
        "What is the policy?",
        document_ids=document_ids,
        top_k=13,
    )
    graph_retrieval.assert_called_once_with(
        "What is the policy?",
        document_ids=document_ids,
        top_k=9,
    )


def test_retrieve_hybrid_merges_duplicate_semantic_and_graph_chunks_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chunk_id = "33333333-3333-3333-3333-333333333333"
    semantic_search = Mock(
        return_value=SearchResponse(
            question="What is the policy?",
            results=[
                _semantic_candidate(
                    chunk_id,
                    content="short semantic text",
                    semantic_similarity=0.91,
                    page_number=None,
                )
            ],
        )
    )
    graph_retrieval = Mock(
        return_value=[
            _graph_candidate(
                chunk_id,
                content="longer graph text with more complete candidate content",
                graph_relevance=0.73,
                page_number=8,
                metadata={"matched_entity_name": "policy", "graph_path_count": 2},
            )
        ]
    )
    monkeypatch.setattr(hybrid_retrieval_service, "get_settings", lambda: _settings())

    response = hybrid_retrieval_service.retrieve_hybrid(
        "What is the policy?",
        semantic_search=semantic_search,
        graph_retrieval=graph_retrieval,
    )

    assert [candidate.chunk_id for candidate in response.candidates] == [UUID(chunk_id)]
    candidate = response.candidates[0]
    assert candidate.semantic_similarity == pytest.approx(0.91)
    assert candidate.graph_relevance == pytest.approx(0.73)
    assert candidate.page_number == 8
    assert candidate.content == "longer graph text with more complete candidate content"
    assert candidate.metadata == {
        "matched_entity_name": "policy",
        "graph_path_count": 2,
    }


def test_retrieve_hybrid_keeps_semantic_only_candidate_with_zero_graph_score(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chunk_id = "44444444-4444-4444-4444-444444444444"
    semantic_search = Mock(
        return_value=SearchResponse(
            question="What is the policy?",
            results=[_semantic_candidate(chunk_id, semantic_similarity=0.88)],
        )
    )
    graph_retrieval = Mock(return_value=[])
    monkeypatch.setattr(hybrid_retrieval_service, "get_settings", lambda: _settings())

    response = hybrid_retrieval_service.retrieve_hybrid(
        "What is the policy?",
        semantic_search=semantic_search,
        graph_retrieval=graph_retrieval,
    )

    assert len(response.candidates) == 1
    assert response.candidates[0].semantic_similarity == pytest.approx(0.88)
    assert response.candidates[0].graph_relevance == 0.0


def test_retrieve_hybrid_keeps_graph_only_candidate_with_zero_semantic_score(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chunk_id = "55555555-5555-5555-5555-555555555555"
    semantic_search = Mock(
        return_value=SearchResponse(question="What is the policy?", results=[])
    )
    graph_retrieval = Mock(
        return_value=[_graph_candidate(chunk_id, graph_relevance=0.64)]
    )
    monkeypatch.setattr(hybrid_retrieval_service, "get_settings", lambda: _settings())

    response = hybrid_retrieval_service.retrieve_hybrid(
        "What is the policy?",
        semantic_search=semantic_search,
        graph_retrieval=graph_retrieval,
    )

    assert len(response.candidates) == 1
    assert response.candidates[0].semantic_similarity == 0.0
    assert response.candidates[0].graph_relevance == pytest.approx(0.64)


def test_retrieve_hybrid_generates_semantic_retrieval_reason_without_answer_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chunk_id = "56565656-5656-5656-5656-565656565656"
    semantic_search = Mock(
        return_value=SearchResponse(
            question="What policy appears in policy.pdf summary?",
            results=[
                _semantic_candidate(
                    chunk_id,
                    content="policy summary states approval conditions",
                    semantic_similarity=0.88,
                    file_name="policy.pdf",
                    page_number=1,
                    section_title="Summary",
                    chunk_index=0,
                )
            ],
        )
    )
    graph_retrieval = Mock(return_value=[])
    monkeypatch.setattr(hybrid_retrieval_service, "get_settings", lambda: _settings())

    response = hybrid_retrieval_service.retrieve_hybrid(
        "What policy appears in policy.pdf summary?",
        semantic_search=semantic_search,
        graph_retrieval=graph_retrieval,
    )

    reason = response.candidates[0].retrieval_reason
    assert reason == (
        "Semantic match score: 0.88; keyword overlap: policy, summary; "
        "metadata match score: 0.40; position signal score: 0.85"
    )
    assert "approval conditions" not in reason


def test_retrieve_hybrid_combines_graph_reason_with_deterministic_score_signals(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chunk_id = "57575757-5757-5757-5757-575757575757"
    semantic_search = Mock(
        return_value=SearchResponse(
            question="What policy applies?",
            results=[
                _semantic_candidate(
                    chunk_id,
                    content="policy text",
                    semantic_similarity=0.91,
                )
            ],
        )
    )
    graph_retrieval = Mock(
        return_value=[
            _graph_candidate(
                chunk_id,
                content="policy graph content",
                graph_relevance=0.73,
                metadata={"matched_entity_name": "policy"},
            )
        ]
    )
    monkeypatch.setattr(hybrid_retrieval_service, "get_settings", lambda: _settings())

    response = hybrid_retrieval_service.retrieve_hybrid(
        "What policy applies?",
        semantic_search=semantic_search,
        graph_retrieval=graph_retrieval,
    )

    assert response.candidates[0].retrieval_reason == (
        "Graph match: Matched entity: policy; Semantic match score: 0.91; "
        "keyword overlap: policy"
    )


def test_retrieve_hybrid_preserves_richer_metadata_when_semantic_source_is_sparse(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chunk_id = "66666666-6666-6666-6666-666666666666"
    semantic_search = Mock(
        return_value=SearchResponse(
            question="What is the policy?",
            results=[
                _semantic_candidate(
                    chunk_id,
                    content=None,
                    file_name=None,
                    page_number=None,
                    section_title=None,
                    chunk_index=None,
                    semantic_similarity=0.79,
                )
            ],
        )
    )
    graph_retrieval = Mock(
        return_value=[
            _graph_candidate(
                chunk_id,
                content="graph supplied content",
                file_name="graph.pdf",
                page_number=6,
                section_title="Graph Metadata",
                chunk_index=12,
                metadata={"matched_entity_name": "policy", "page_number": 6},
            )
        ]
    )
    monkeypatch.setattr(hybrid_retrieval_service, "get_settings", lambda: _settings())

    response = hybrid_retrieval_service.retrieve_hybrid(
        "What is the policy?",
        semantic_search=semantic_search,
        graph_retrieval=graph_retrieval,
    )

    candidate = response.candidates[0]
    assert candidate.content == "graph supplied content"
    assert candidate.file_name == "graph.pdf"
    assert candidate.page_number == 6
    assert candidate.section_title == "Graph Metadata"
    assert candidate.chunk_index == 12
    assert candidate.metadata == {"matched_entity_name": "policy", "page_number": 6}


def test_retrieve_hybrid_calculates_score_components_for_every_merged_candidate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document_id = "22222222-2222-2222-2222-222222222222"
    duplicate_chunk_id = "77777777-7777-7777-7777-777777777777"
    graph_only_chunk_id = "88888888-8888-8888-8888-888888888888"
    semantic_search = Mock(
        return_value=SearchResponse(
            question="What policy appears on page 1 in policy.pdf summary?",
            results=[
                _semantic_candidate(
                    duplicate_chunk_id,
                    document_id=document_id,
                    content="policy summary states requirements",
                    semantic_similarity=0.8,
                    file_name="policy.pdf",
                    page_number=1,
                    section_title="Summary",
                    chunk_index=0,
                )
            ],
        )
    )
    graph_retrieval = Mock(
        return_value=[
            _graph_candidate(
                duplicate_chunk_id,
                document_id=document_id,
                graph_relevance=0.6,
                section_title=None,
                metadata={"matched_entity_name": "policy"},
            ),
            _graph_candidate(
                graph_only_chunk_id,
                document_id=document_id,
                content="policy appendix",
                graph_relevance=0.4,
                file_name="appendix.pdf",
                page_number=9,
                section_title="Appendix",
                chunk_index=9,
            ),
        ]
    )
    monkeypatch.setattr(hybrid_retrieval_service, "get_settings", lambda: _settings())

    response = hybrid_retrieval_service.retrieve_hybrid(
        "What policy appears on page 1 in policy.pdf summary?",
        document_ids=[UUID(document_id)],
        semantic_search=semantic_search,
        graph_retrieval=graph_retrieval,
    )

    assert len(response.candidates) == 2
    merged_candidate = response.candidates[0]
    assert merged_candidate.semantic_similarity == pytest.approx(0.8)
    assert merged_candidate.graph_relevance == pytest.approx(0.6)
    assert 0.0 < merged_candidate.keyword_overlap <= 1.0
    assert merged_candidate.metadata_match == pytest.approx(1.0)
    assert merged_candidate.recency_or_position_score == pytest.approx(0.85)
    assert merged_candidate.final_score == pytest.approx(
        final_score(
            {
                "semantic_similarity": merged_candidate.semantic_similarity,
                "graph_relevance": merged_candidate.graph_relevance,
                "keyword_overlap": merged_candidate.keyword_overlap,
                "metadata_match": merged_candidate.metadata_match,
                "recency_or_position_score": merged_candidate.recency_or_position_score,
            }
        )
    )

    graph_only_candidate = response.candidates[1]
    assert graph_only_candidate.semantic_similarity == 0.0
    assert graph_only_candidate.graph_relevance == pytest.approx(0.4)
    assert 0.0 <= graph_only_candidate.keyword_overlap <= 1.0
    assert 0.0 <= graph_only_candidate.metadata_match <= 1.0
    assert 0.0 <= graph_only_candidate.recency_or_position_score <= 1.0
    assert graph_only_candidate.final_score == pytest.approx(
        final_score(
            {
                "semantic_similarity": graph_only_candidate.semantic_similarity,
                "graph_relevance": graph_only_candidate.graph_relevance,
                "keyword_overlap": graph_only_candidate.keyword_overlap,
                "metadata_match": graph_only_candidate.metadata_match,
                "recency_or_position_score": graph_only_candidate.recency_or_position_score,
            }
        )
    )


def test_retrieve_hybrid_clamps_invalid_component_scores_before_final_formula(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chunk_id = "99999999-9999-9999-9999-999999999999"
    semantic_search = Mock(
        return_value=SearchResponse(
            question="What is the policy?",
            results=[_semantic_candidate(chunk_id, semantic_similarity=1.7)],
        )
    )
    graph_retrieval = Mock(
        return_value=[_graph_candidate(chunk_id, graph_relevance=-0.4)]
    )
    monkeypatch.setattr(hybrid_retrieval_service, "get_settings", lambda: _settings())

    response = hybrid_retrieval_service.retrieve_hybrid(
        "What is the policy?",
        semantic_search=semantic_search,
        graph_retrieval=graph_retrieval,
    )

    candidate = response.candidates[0]
    assert candidate.semantic_similarity == 1.0
    assert candidate.graph_relevance == 0.0
    assert candidate.final_score == pytest.approx(
        final_score(
            {
                "semantic_similarity": candidate.semantic_similarity,
                "graph_relevance": candidate.graph_relevance,
                "keyword_overlap": candidate.keyword_overlap,
                "metadata_match": candidate.metadata_match,
                "recency_or_position_score": candidate.recency_or_position_score,
            }
        )
    )
    assert 0.0 <= candidate.final_score <= 1.0


def test_retrieve_hybrid_sorts_by_final_score_desc_and_uses_configured_final_top_k(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    low_chunk_id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    high_chunk_id = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
    middle_chunk_id = "cccccccc-cccc-cccc-cccc-cccccccccccc"
    semantic_search = Mock(
        return_value=SearchResponse(
            question="unmatched query",
            results=[
                _semantic_candidate(
                    low_chunk_id,
                    content="alpha",
                    semantic_similarity=0.2,
                    chunk_index=5,
                    page_number=None,
                    section_title=None,
                ),
                _semantic_candidate(
                    high_chunk_id,
                    content="bravo",
                    semantic_similarity=0.9,
                    chunk_index=5,
                    page_number=None,
                    section_title=None,
                ),
                _semantic_candidate(
                    middle_chunk_id,
                    content="charlie",
                    semantic_similarity=0.5,
                    chunk_index=5,
                    page_number=None,
                    section_title=None,
                ),
            ],
        )
    )
    graph_retrieval = Mock(return_value=[])
    monkeypatch.setattr(
        hybrid_retrieval_service,
        "get_settings",
        lambda: _settings(final_top_k=2),
    )

    response = hybrid_retrieval_service.retrieve_hybrid(
        "unmatched query",
        semantic_search=semantic_search,
        graph_retrieval=graph_retrieval,
    )

    assert [candidate.chunk_id for candidate in response.candidates] == [
        UUID(high_chunk_id),
        UUID(middle_chunk_id),
    ]
    assert [candidate.final_score for candidate in response.candidates] == sorted(
        [candidate.final_score for candidate in response.candidates],
        reverse=True,
    )


def test_retrieve_hybrid_passes_ranked_candidates_through_guarded_rerank(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    low_chunk_id = "abababab-abab-abab-abab-abababababab"
    high_chunk_id = "bcbcbcbc-bcbc-bcbc-bcbc-bcbcbcbcbcbc"
    semantic_search = Mock(
        return_value=SearchResponse(
            question="unmatched query",
            results=[
                _semantic_candidate(
                    low_chunk_id,
                    content="alpha",
                    semantic_similarity=0.2,
                    chunk_index=5,
                    page_number=None,
                    section_title=None,
                ),
                _semantic_candidate(
                    high_chunk_id,
                    content="bravo",
                    semantic_similarity=0.9,
                    chunk_index=5,
                    page_number=None,
                    section_title=None,
                ),
            ],
        )
    )
    graph_retrieval = Mock(return_value=[])
    rerank_candidates = Mock(side_effect=lambda _question, candidates, top_n: candidates)
    monkeypatch.setattr(hybrid_retrieval_service, "get_settings", lambda: _settings())
    monkeypatch.setattr(
        hybrid_retrieval_service.shopaikey_service,
        "rerank_candidates",
        rerank_candidates,
    )

    response = hybrid_retrieval_service.retrieve_hybrid(
        "unmatched query",
        semantic_search=semantic_search,
        graph_retrieval=graph_retrieval,
    )

    rerank_candidates.assert_called_once()
    rerank_question, ranked_candidates = rerank_candidates.call_args.args[:2]
    rerank_top_n = rerank_candidates.call_args.kwargs["top_n"]
    assert rerank_question == "unmatched query"
    assert rerank_top_n == 5
    assert [candidate.chunk_id for candidate in ranked_candidates] == [
        UUID(high_chunk_id),
        UUID(low_chunk_id),
    ]
    assert [candidate.chunk_id for candidate in response.candidates] == [
        UUID(high_chunk_id),
        UUID(low_chunk_id),
    ]
    assert all(candidate.final_score > 0.0 for candidate in response.candidates)


def test_retrieve_hybrid_explicit_final_top_k_overrides_configured_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    semantic_search = Mock(
        return_value=SearchResponse(
            question="unmatched query",
            results=[
                _semantic_candidate(
                    "dddddddd-dddd-dddd-dddd-dddddddddddd",
                    content="delta",
                    semantic_similarity=0.6,
                ),
                _semantic_candidate(
                    "eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee",
                    content="echo",
                    semantic_similarity=0.8,
                ),
                _semantic_candidate(
                    "ffffffff-ffff-ffff-ffff-ffffffffffff",
                    content="foxtrot",
                    semantic_similarity=0.4,
                ),
            ],
        )
    )
    graph_retrieval = Mock(return_value=[])
    monkeypatch.setattr(
        hybrid_retrieval_service,
        "get_settings",
        lambda: _settings(final_top_k=3),
    )

    response = hybrid_retrieval_service.retrieve_hybrid(
        "unmatched query",
        final_top_k=1,
        semantic_search=semantic_search,
        graph_retrieval=graph_retrieval,
    )

    assert len(response.candidates) == 1
    assert response.candidates[0].chunk_id == UUID(
        "eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee"
    )


def test_retrieve_hybrid_preserves_merge_order_for_equal_final_scores(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first_chunk_id = "12121212-1212-1212-1212-121212121212"
    second_chunk_id = "34343434-3434-3434-3434-343434343434"
    semantic_search = Mock(
        return_value=SearchResponse(
            question="unmatched query",
            results=[
                _semantic_candidate(
                    first_chunk_id,
                    content="alpha",
                    semantic_similarity=0.7,
                    chunk_index=5,
                    page_number=None,
                    section_title=None,
                ),
                _semantic_candidate(
                    second_chunk_id,
                    content="bravo",
                    semantic_similarity=0.7,
                    chunk_index=5,
                    page_number=None,
                    section_title=None,
                ),
            ],
        )
    )
    graph_retrieval = Mock(return_value=[])
    monkeypatch.setattr(hybrid_retrieval_service, "get_settings", lambda: _settings())

    response = hybrid_retrieval_service.retrieve_hybrid(
        "unmatched query",
        semantic_search=semantic_search,
        graph_retrieval=graph_retrieval,
    )

    assert response.candidates[0].final_score == pytest.approx(
        response.candidates[1].final_score
    )
    assert [candidate.chunk_id for candidate in response.candidates] == [
        UUID(first_chunk_id),
        UUID(second_chunk_id),
    ]


def test_retrieve_hybrid_returns_empty_list_for_empty_merged_candidates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    semantic_search = Mock(
        return_value=SearchResponse(question="What is the policy?", results=[])
    )
    graph_retrieval = Mock(return_value=[])
    monkeypatch.setattr(hybrid_retrieval_service, "get_settings", lambda: _settings())

    response = hybrid_retrieval_service.retrieve_hybrid(
        "What is the policy?",
        semantic_search=semantic_search,
        graph_retrieval=graph_retrieval,
    )

    assert response.candidates == []


def test_retrieve_hybrid_fails_semantic_dependency_errors_with_safe_message_and_log(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    secret = "sk-live-secret-value"
    semantic_error = RetrievalDependencyError(
        f"Provider rejected Authorization Bearer {secret}"
    )
    semantic_search = Mock(side_effect=semantic_error)
    graph_retrieval = Mock()
    monkeypatch.setattr(hybrid_retrieval_service, "get_settings", lambda: _settings())

    with caplog.at_level(logging.ERROR, logger=hybrid_retrieval_service.logger.name):
        with pytest.raises(
            hybrid_retrieval_service.HybridRetrievalDependencyError
        ) as exc_info:
            hybrid_retrieval_service.retrieve_hybrid(
                "What is the policy?",
                semantic_search=semantic_search,
                graph_retrieval=graph_retrieval,
            )

    assert exc_info.value.public_message == (
        "Semantic retrieval is temporarily unavailable."
    )
    assert str(exc_info.value) == "Semantic retrieval is temporarily unavailable."
    assert exc_info.value.__cause__ is semantic_error
    assert secret not in str(exc_info.value)
    assert secret not in caplog.text
    assert "Semantic retrieval failed during hybrid retrieval" in caplog.text
    assert "RetrievalDependencyError" in caplog.text
    graph_retrieval.assert_not_called()


def test_retrieve_hybrid_logs_graph_dependency_error_and_returns_semantic_only_scores(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    secret = "service-role-secret"
    chunk_id = "13131313-1313-1313-1313-131313131313"
    semantic_search = Mock(
        return_value=SearchResponse(
            question="What is the policy?",
            results=[_semantic_candidate(chunk_id, semantic_similarity=0.82)],
        )
    )
    graph_retrieval = Mock(
        side_effect=GraphRetrievalDependencyError(
            f"SQL failed with service key {secret}"
        )
    )
    monkeypatch.setattr(hybrid_retrieval_service, "get_settings", lambda: _settings())

    with caplog.at_level(logging.WARNING, logger=hybrid_retrieval_service.logger.name):
        response = hybrid_retrieval_service.retrieve_hybrid(
            "What is the policy?",
            semantic_search=semantic_search,
            graph_retrieval=graph_retrieval,
        )

    assert len(response.candidates) == 1
    assert response.candidates[0].chunk_id == UUID(chunk_id)
    assert response.candidates[0].semantic_similarity == pytest.approx(0.82)
    assert response.candidates[0].graph_relevance == 0.0
    assert response.candidates[0].final_score > 0.0
    assert secret not in caplog.text
    assert "Graph retrieval unavailable during hybrid retrieval" in caplog.text
    assert "GraphRetrievalDependencyError" in caplog.text


def test_retrieve_hybrid_logs_unexpected_graph_error_and_returns_semantic_only_scores(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    secret = "raw-sql-select-secret"
    chunk_id = "14141414-1414-1414-1414-141414141414"
    semantic_search = Mock(
        return_value=SearchResponse(
            question="What is the policy?",
            results=[_semantic_candidate(chunk_id, semantic_similarity=0.7)],
        )
    )
    graph_retrieval = Mock(side_effect=RuntimeError(f"internal stack {secret}"))
    monkeypatch.setattr(hybrid_retrieval_service, "get_settings", lambda: _settings())

    with caplog.at_level(logging.WARNING, logger=hybrid_retrieval_service.logger.name):
        response = hybrid_retrieval_service.retrieve_hybrid(
            "What is the policy?",
            semantic_search=semantic_search,
            graph_retrieval=graph_retrieval,
        )

    assert [candidate.chunk_id for candidate in response.candidates] == [UUID(chunk_id)]
    assert response.candidates[0].graph_relevance == 0.0
    assert secret not in caplog.text
    assert "Graph retrieval unavailable during hybrid retrieval" in caplog.text
    assert "RuntimeError" in caplog.text


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"final_top_k": 0}, "final_top_k must be between 1 and 50."),
        ({"final_top_k": 51}, "final_top_k must be between 1 and 50."),
        ({"semantic_top_k": 0}, "semantic_top_k must be between 1 and 50."),
        ({"graph_top_k": 51}, "graph_top_k must be between 1 and 50."),
    ],
)
def test_retrieve_hybrid_rejects_invalid_top_k_before_dependency_calls(
    kwargs: dict[str, int],
    message: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    semantic_search = Mock()
    graph_retrieval = Mock()
    monkeypatch.setattr(hybrid_retrieval_service, "get_settings", lambda: _settings())

    with pytest.raises(hybrid_retrieval_service.HybridRetrievalValidationError) as exc_info:
        hybrid_retrieval_service.retrieve_hybrid(
            "What is the policy?",
            semantic_search=semantic_search,
            graph_retrieval=graph_retrieval,
            **kwargs,
        )

    assert str(exc_info.value) == message
    semantic_search.assert_not_called()
    graph_retrieval.assert_not_called()
