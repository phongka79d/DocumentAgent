import sys
from pathlib import Path
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.api.retrieval import router as retrieval_router
from app.main import create_app
from app.schemas.retrieval import (
    HybridRetrievalCandidate,
    HybridSearchResponse,
    RetrievalResult,
    SearchResponse,
)
from app.services.hybrid_retrieval_service import (
    HybridRetrievalDependencyError,
    HybridRetrievalValidationError,
)
from app.services.qdrant_service import QdrantSearchError
from app.services.retrieval_service import (
    RetrievalDependencyError,
    RetrievalValidationError,
)


DOCUMENT_ID = UUID("11111111-1111-1111-1111-111111111111")
CHUNK_ID = UUID("22222222-2222-2222-2222-222222222222")
HYBRID_CHUNK_ID = UUID("33333333-3333-3333-3333-333333333333")


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(retrieval_router, prefix="/api/retrieval")
    return TestClient(app)


def test_search_retrieval_api_returns_search_response(monkeypatch) -> None:
    def fake_semantic_search(question, document_ids=None, top_k=None):
        return SearchResponse(
            question=question,
            results=[
                RetrievalResult(
                    chunk_id=CHUNK_ID,
                    document_id=DOCUMENT_ID,
                    file_name="handbook.pdf",
                    file_type="pdf",
                    content="Employees may work remotely two days per week.",
                    content_preview=None,
                    page_number=3,
                    section_title="Remote work",
                    chunk_index=7,
                    semantic_similarity=0.91,
                )
            ],
        )

    monkeypatch.setattr(
        "app.api.retrieval.retrieval_service.semantic_search",
        fake_semantic_search,
    )

    response = _client().post(
        "/api/retrieval/search",
        json={
            "question": "What is the remote work policy?",
            "document_ids": [str(DOCUMENT_ID)],
            "top_k": 3,
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "question": "What is the remote work policy?",
        "results": [
            {
                "chunk_id": str(CHUNK_ID),
                "document_id": str(DOCUMENT_ID),
                "file_name": "handbook.pdf",
                "file_type": "pdf",
                "content": "Employees may work remotely two days per week.",
                "content_preview": None,
                "page_number": 3,
                "section_title": "Remote work",
                "chunk_index": 7,
                "semantic_similarity": 0.91,
            }
        ],
    }


def test_search_retrieval_api_delegates_request_fields(monkeypatch) -> None:
    observed_call = {}

    def fake_semantic_search(question, document_ids=None, top_k=None):
        observed_call["question"] = question
        observed_call["document_ids"] = document_ids
        observed_call["top_k"] = top_k
        return SearchResponse(question=question, results=[])

    monkeypatch.setattr(
        "app.api.retrieval.retrieval_service.semantic_search",
        fake_semantic_search,
    )

    response = _client().post(
        "/api/retrieval/search",
        json={
            "question": "Which document mentions onboarding?",
            "document_ids": [str(DOCUMENT_ID)],
            "top_k": 5,
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "question": "Which document mentions onboarding?",
        "results": [],
    }
    assert observed_call == {
        "question": "Which document mentions onboarding?",
        "document_ids": [DOCUMENT_ID],
        "top_k": 5,
    }


def test_search_retrieval_api_allows_omitted_optional_fields(monkeypatch) -> None:
    observed_call = {}

    def fake_semantic_search(question, document_ids=None, top_k=None):
        observed_call["question"] = question
        observed_call["document_ids"] = document_ids
        observed_call["top_k"] = top_k
        return SearchResponse(question=question, results=[])

    monkeypatch.setattr(
        "app.api.retrieval.retrieval_service.semantic_search",
        fake_semantic_search,
    )

    response = _client().post(
        "/api/retrieval/search",
        json={"question": "Where is the onboarding policy?"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "question": "Where is the onboarding policy?",
        "results": [],
    }
    assert observed_call == {
        "question": "Where is the onboarding policy?",
        "document_ids": None,
        "top_k": None,
    }


def test_search_retrieval_api_semantic_mode_preserves_semantic_behavior(
    monkeypatch,
) -> None:
    observed_call = {}

    def fake_semantic_search(question, document_ids=None, top_k=None):
        observed_call["question"] = question
        observed_call["document_ids"] = document_ids
        observed_call["top_k"] = top_k
        return SearchResponse(question=question, results=[])

    def fail_hybrid_retrieval(*args, **kwargs):
        raise AssertionError("hybrid retrieval should not run for semantic mode")

    monkeypatch.setattr(
        "app.api.retrieval.retrieval_service.semantic_search",
        fake_semantic_search,
    )
    monkeypatch.setattr(
        "app.api.retrieval.hybrid_retrieval_service.retrieve_hybrid",
        fail_hybrid_retrieval,
    )

    response = _client().post(
        "/api/retrieval/search",
        json={
            "question": "Which document mentions onboarding?",
            "document_ids": [str(DOCUMENT_ID)],
            "top_k": 4,
            "mode": "semantic",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "question": "Which document mentions onboarding?",
        "results": [],
    }
    assert observed_call == {
        "question": "Which document mentions onboarding?",
        "document_ids": [DOCUMENT_ID],
        "top_k": 4,
    }


def test_search_retrieval_api_hybrid_mode_delegates_to_hybrid_service(
    monkeypatch,
) -> None:
    observed_call = {}

    def fail_semantic_search(*args, **kwargs):
        raise AssertionError("semantic search should not run for hybrid mode")

    def fake_retrieve_hybrid(question, document_ids=None, final_top_k=None):
        observed_call["question"] = question
        observed_call["document_ids"] = document_ids
        observed_call["final_top_k"] = final_top_k
        return HybridSearchResponse(
            question=question.strip(),
            candidates=[
                HybridRetrievalCandidate(
                    chunk_id=HYBRID_CHUNK_ID,
                    document_id=DOCUMENT_ID,
                    file_name="handbook.pdf",
                    file_type="pdf",
                    content="The onboarding policy includes probation details.",
                    content_preview=None,
                    page_number=4,
                    section_title="Onboarding",
                    chunk_index=2,
                    semantic_similarity=0.84,
                    metadata={"source": "graph"},
                    graph_relevance=0.72,
                    keyword_overlap=0.5,
                    metadata_match=1.0,
                    recency_or_position_score=0.9,
                    final_score=0.769,
                    retrieval_reason="Matched entity: Onboarding",
                )
            ],
        )

    monkeypatch.setattr(
        "app.api.retrieval.retrieval_service.semantic_search",
        fail_semantic_search,
    )
    monkeypatch.setattr(
        "app.api.retrieval.hybrid_retrieval_service.retrieve_hybrid",
        fake_retrieve_hybrid,
    )

    response = _client().post(
        "/api/retrieval/search",
        json={
            "question": "Which document mentions onboarding?",
            "document_ids": [str(DOCUMENT_ID)],
            "top_k": 2,
            "mode": "hybrid",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "question": "Which document mentions onboarding?",
        "candidates": [
            {
                "chunk_id": str(HYBRID_CHUNK_ID),
                "document_id": str(DOCUMENT_ID),
                "file_name": "handbook.pdf",
                "file_type": "pdf",
                "content": "The onboarding policy includes probation details.",
                "content_preview": None,
                "page_number": 4,
                "section_title": "Onboarding",
                "chunk_index": 2,
                "semantic_similarity": 0.84,
                "metadata": {"source": "graph"},
                "graph_relevance": 0.72,
                "keyword_overlap": 0.5,
                "metadata_match": 1.0,
                "recency_or_position_score": 0.9,
                "final_score": 0.769,
                "retrieval_reason": "Matched entity: Onboarding",
            }
        ],
    }
    assert observed_call == {
        "question": "Which document mentions onboarding?",
        "document_ids": [DOCUMENT_ID],
        "final_top_k": 2,
    }


def test_main_app_registers_retrieval_router(monkeypatch) -> None:
    def fake_semantic_search(question, document_ids=None, top_k=None):
        return SearchResponse(question=question, results=[])

    monkeypatch.setattr(
        "app.api.retrieval.retrieval_service.semantic_search",
        fake_semantic_search,
    )

    response = TestClient(create_app()).post(
        "/api/retrieval/search",
        json={"question": "Where is the onboarding policy?"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "question": "Where is the onboarding policy?",
        "results": [],
    }


def test_search_retrieval_api_returns_400_for_empty_question(monkeypatch) -> None:
    def fake_semantic_search(question, document_ids=None, top_k=None):
        raise RetrievalValidationError("Question must be non-empty.")

    monkeypatch.setattr(
        "app.api.retrieval.retrieval_service.semantic_search",
        fake_semantic_search,
    )

    response = _client().post(
        "/api/retrieval/search",
        json={"question": "   "},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Question must be non-empty."}


@pytest.mark.parametrize("top_k", [0, 1000])
def test_search_retrieval_api_returns_400_for_top_k_out_of_range(
    monkeypatch,
    top_k,
) -> None:
    def fake_semantic_search(question, document_ids=None, top_k=None):
        raise RetrievalValidationError("top_k must be between 1 and 50.")

    monkeypatch.setattr(
        "app.api.retrieval.retrieval_service.semantic_search",
        fake_semantic_search,
    )

    response = _client().post(
        "/api/retrieval/search",
        json={"question": "What is the policy?", "top_k": top_k},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "top_k must be between 1 and 50."}


def test_search_retrieval_api_returns_422_for_invalid_document_uuid(
    monkeypatch,
) -> None:
    def fake_semantic_search(question, document_ids=None, top_k=None):
        raise AssertionError("semantic_search should not run for invalid UUID input")

    monkeypatch.setattr(
        "app.api.retrieval.retrieval_service.semantic_search",
        fake_semantic_search,
    )

    response = _client().post(
        "/api/retrieval/search",
        json={
            "question": "What is the policy?",
            "document_ids": ["not-a-uuid"],
        },
    )

    assert response.status_code == 422


def test_search_retrieval_api_returns_422_for_invalid_mode(monkeypatch) -> None:
    def fail_semantic_search(*args, **kwargs):
        raise AssertionError("semantic_search should not run for invalid mode")

    def fail_hybrid_retrieval(*args, **kwargs):
        raise AssertionError("retrieve_hybrid should not run for invalid mode")

    monkeypatch.setattr(
        "app.api.retrieval.retrieval_service.semantic_search",
        fail_semantic_search,
    )
    monkeypatch.setattr(
        "app.api.retrieval.hybrid_retrieval_service.retrieve_hybrid",
        fail_hybrid_retrieval,
    )

    response = _client().post(
        "/api/retrieval/search",
        json={"question": "What is the policy?", "mode": "keyword"},
    )

    assert response.status_code == 422


def test_search_retrieval_api_returns_500_for_shopaikey_failure(
    monkeypatch,
) -> None:
    def fake_semantic_search(question, document_ids=None, top_k=None):
        raise RetrievalDependencyError("Semantic retrieval is temporarily unavailable.")

    monkeypatch.setattr(
        "app.api.retrieval.retrieval_service.semantic_search",
        fake_semantic_search,
    )

    response = _client().post(
        "/api/retrieval/search",
        json={"question": "What is the policy?"},
    )

    assert response.status_code == 500
    assert response.json() == {
        "detail": "Semantic retrieval is temporarily unavailable."
    }


def test_search_retrieval_api_returns_500_for_qdrant_search_failure(
    monkeypatch,
) -> None:
    def fake_semantic_search(question, document_ids=None, top_k=None):
        raise QdrantSearchError("Qdrant vector search failed.")

    monkeypatch.setattr(
        "app.api.retrieval.retrieval_service.semantic_search",
        fake_semantic_search,
    )

    response = _client().post(
        "/api/retrieval/search",
        json={"question": "What is the policy?"},
    )

    assert response.status_code == 500
    assert response.json() == {
        "detail": "Semantic retrieval is temporarily unavailable."
    }


def test_search_retrieval_api_maps_hybrid_validation_error_to_400(
    monkeypatch,
) -> None:
    def fake_retrieve_hybrid(question, document_ids=None, final_top_k=None):
        raise HybridRetrievalValidationError("final_top_k must be between 1 and 50.")

    monkeypatch.setattr(
        "app.api.retrieval.hybrid_retrieval_service.retrieve_hybrid",
        fake_retrieve_hybrid,
    )

    response = _client().post(
        "/api/retrieval/search",
        json={"question": "What is the policy?", "mode": "hybrid", "top_k": 0},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "final_top_k must be between 1 and 50."}


def test_search_retrieval_api_maps_hybrid_dependency_error_to_safe_500(
    monkeypatch,
) -> None:
    def fake_retrieve_hybrid(question, document_ids=None, final_top_k=None):
        raise HybridRetrievalDependencyError(
            "Semantic retrieval is temporarily unavailable."
        )

    monkeypatch.setattr(
        "app.api.retrieval.hybrid_retrieval_service.retrieve_hybrid",
        fake_retrieve_hybrid,
    )

    response = _client().post(
        "/api/retrieval/search",
        json={"question": "What is the policy?", "mode": "hybrid"},
    )

    assert response.status_code == 500
    assert response.json() == {
        "detail": "Semantic retrieval is temporarily unavailable."
    }


def test_search_retrieval_api_returns_empty_results_for_missing_indexed_chunks(
    monkeypatch,
) -> None:
    def fake_semantic_search(question, document_ids=None, top_k=None):
        return SearchResponse(question=question, results=[])

    monkeypatch.setattr(
        "app.api.retrieval.retrieval_service.semantic_search",
        fake_semantic_search,
    )

    response = _client().post(
        "/api/retrieval/search",
        json={"question": "What is the policy?"},
    )

    assert response.status_code == 200
    assert response.json() == {"question": "What is the policy?", "results": []}
