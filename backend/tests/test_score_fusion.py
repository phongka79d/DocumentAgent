from __future__ import annotations

import pytest

from app.core.config import Settings
from app.core.contracts import RetrievalPath
from app.services import retrieval, score_fusion
from app.services.keyword_search import KeywordSearchError


def _settings(**overrides) -> Settings:
    values = {
        "RETRIEVAL_RRF_CONSTANT": 60,
        "RETRIEVAL_FUSION_TOP_K": 3,
        "RETRIEVAL_SEMANTIC_TOP_K": 3,
        "RETRIEVAL_KEYWORD_TOP_K": 3,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def _candidate(chunk_id: str, **overrides):
    candidate = {
        "chunk_id": chunk_id,
        "document_id": "document-a",
        "file_name": "alpha.pdf",
        "chunk_index": 0,
        "content": f"{chunk_id} content",
        "heading": None,
        "section_path": [],
        "page_start": None,
        "page_end": None,
        "chunk_type": "text",
        "token_count": 10,
        "qdrant_score": None,
        "rerank_score": None,
        "semantic_rank": None,
        "semantic_score": None,
        "keyword_rank": None,
        "keyword_score": None,
        "fusion_score": None,
        "retrieval_paths": [],
        "subquery_ids": [],
    }
    candidate.update(overrides)
    return candidate


def test_fuse_candidates_merges_duplicates_and_accumulates_rrf_contributions():
    settings = _settings()

    results = score_fusion.fuse_candidates(
        [
            [
                _candidate(
                    "shared",
                    qdrant_score=0.7,
                    semantic_score=0.7,
                    semantic_rank=2,
                    retrieval_paths=[RetrievalPath.SEMANTIC],
                    subquery_ids=["sq1"],
                ),
                _candidate(
                    "semantic-only",
                    qdrant_score=0.9,
                    semantic_score=0.9,
                    semantic_rank=1,
                    retrieval_paths=[RetrievalPath.SEMANTIC],
                    subquery_ids=["sq1"],
                ),
            ],
            [
                _candidate(
                    "shared",
                    keyword_score=0.8,
                    keyword_rank=1,
                    retrieval_paths=[RetrievalPath.KEYWORD, RetrievalPath.KEYWORD],
                    subquery_ids=["sq2", "sq2"],
                )
            ],
        ],
        settings=settings,
    )

    assert [candidate["chunk_id"] for candidate in results][:2] == [
        "shared",
        "semantic-only",
    ]
    shared = results[0]
    assert shared["semantic_score"] == 0.7
    assert shared["qdrant_score"] == 0.7
    assert shared["semantic_rank"] == 2
    assert shared["keyword_score"] == 0.8
    assert shared["keyword_rank"] == 1
    assert shared["retrieval_paths"] == ["semantic", "keyword"]
    assert shared["subquery_ids"] == ["sq1", "sq2"]
    assert shared["fusion_score"] == pytest.approx((1 / 62) + (1 / 61))


def test_fuse_candidates_orders_by_score_best_rank_chunk_id_and_caps_results():
    candidate_groups = [
        [
            _candidate(
                "chunk-c",
                semantic_rank=1,
                semantic_score=0.9,
                retrieval_paths=[RetrievalPath.SEMANTIC],
            ),
            _candidate(
                "chunk-b",
                semantic_rank=1,
                semantic_score=0.8,
                retrieval_paths=[RetrievalPath.SEMANTIC],
            ),
            _candidate(
                "chunk-a",
                semantic_rank=2,
                semantic_score=0.7,
                retrieval_paths=[RetrievalPath.SEMANTIC],
            ),
        ]
    ]

    results = score_fusion.fuse_candidates(
        candidate_groups,
        settings=_settings(RETRIEVAL_FUSION_TOP_K=2),
    )
    repeated_results = score_fusion.fuse_candidates(
        candidate_groups,
        settings=_settings(RETRIEVAL_FUSION_TOP_K=2),
    )

    assert [candidate["chunk_id"] for candidate in results] == ["chunk-b", "chunk-c"]
    assert [candidate["chunk_id"] for candidate in repeated_results] == [
        "chunk-b",
        "chunk-c",
    ]


def test_retrieve_hybrid_chunks_recovers_with_keyword_when_semantic_path_fails(monkeypatch):
    settings = _settings(ENABLE_KEYWORD_SEARCH=True)
    keyword_candidate = _candidate(
        "keyword-only",
        keyword_rank=1,
        keyword_score=0.7,
        retrieval_paths=[RetrievalPath.KEYWORD],
    )

    monkeypatch.setattr(
        retrieval,
        "embed_question",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            retrieval.RetrievalError("embedding unavailable")
        ),
    )
    monkeypatch.setattr(
        retrieval.keyword_search,
        "search_keyword_chunks",
        lambda *args, **kwargs: [keyword_candidate],
    )

    result = retrieval.retrieve_hybrid_chunks("pricing", settings=settings)

    assert result["retrieved_chunks"] == [keyword_candidate]
    assert result["path_candidates"]["semantic"] == []
    assert result["path_candidates"]["keyword"] == [keyword_candidate]
    assert result["retrieval_metrics"]["fallback_path"] == "keyword"


def test_retrieve_hybrid_chunks_recovers_with_semantic_when_keyword_path_fails(monkeypatch):
    settings = _settings(ENABLE_KEYWORD_SEARCH=True)

    monkeypatch.setattr(retrieval, "embed_question", lambda *args, **kwargs: [0.1])
    monkeypatch.setattr(
        retrieval,
        "search_semantic_chunks",
        lambda *args, **kwargs: [
            {
                "chunk_id": "semantic-only",
                "document_id": "document-a",
                "file_name": "alpha.pdf",
                "chunk_index": 0,
                "content": "semantic content",
                "qdrant_score": 0.9,
            }
        ],
    )
    monkeypatch.setattr(
        retrieval.keyword_search,
        "search_keyword_chunks",
        lambda *args, **kwargs: (_ for _ in ()).throw(KeywordSearchError()),
    )

    result = retrieval.retrieve_hybrid_chunks("pricing", settings=settings)

    assert [candidate["chunk_id"] for candidate in result["retrieved_chunks"]] == [
        "semantic-only"
    ]
    assert result["retrieved_chunks"][0]["retrieval_paths"] == ["semantic"]
    assert result["retrieval_metrics"]["fallback_path"] == "semantic"


def test_retrieve_hybrid_chunks_fails_only_when_both_paths_fail(monkeypatch):
    settings = _settings(ENABLE_KEYWORD_SEARCH=True)
    monkeypatch.setattr(
        retrieval,
        "embed_question",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            retrieval.RetrievalError("embedding unavailable")
        ),
    )
    monkeypatch.setattr(
        retrieval.keyword_search,
        "search_keyword_chunks",
        lambda *args, **kwargs: (_ for _ in ()).throw(KeywordSearchError()),
    )

    with pytest.raises(retrieval.RetrievalError, match="hybrid retrieval failed"):
        retrieval.retrieve_hybrid_chunks("pricing", settings=settings)


def test_retrieve_hybrid_chunks_returns_empty_when_both_paths_have_no_rows(monkeypatch):
    settings = _settings(ENABLE_KEYWORD_SEARCH=True)

    monkeypatch.setattr(retrieval, "embed_question", lambda *args, **kwargs: [0.1])
    monkeypatch.setattr(retrieval, "search_semantic_chunks", lambda *args, **kwargs: [])
    monkeypatch.setattr(retrieval.keyword_search, "search_keyword_chunks", lambda *args, **kwargs: [])

    result = retrieval.retrieve_hybrid_chunks("pricing", settings=settings)

    assert result["retrieved_chunks"] == []
    assert result["fused_candidates"] == []
    assert result["retrieval_metrics"]["fallback_path"] is None


def test_retrieve_hybrid_chunks_uses_semantic_only_when_keyword_disabled(monkeypatch):
    settings = _settings(ENABLE_KEYWORD_SEARCH=False)
    keyword_called = False

    monkeypatch.setattr(retrieval, "embed_question", lambda *args, **kwargs: [0.1])
    monkeypatch.setattr(retrieval, "search_semantic_chunks", lambda *args, **kwargs: [])

    def _keyword_should_not_run(*args, **kwargs):
        nonlocal keyword_called
        keyword_called = True
        return []

    monkeypatch.setattr(retrieval.keyword_search, "search_keyword_chunks", _keyword_should_not_run)

    result = retrieval.retrieve_hybrid_chunks("pricing", settings=settings)

    assert result["retrieved_chunks"] == []
    assert result["path_candidates"]["keyword"] == []
    assert result["retrieval_metrics"]["fallback_path"] == "semantic"
    assert keyword_called is False
