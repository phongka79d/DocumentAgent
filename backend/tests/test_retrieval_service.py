import sys
from pathlib import Path
from types import SimpleNamespace
import logging
from unittest.mock import Mock
from uuid import UUID

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services import retrieval_service
from app.services import supabase_service
from app.services.shopaikey_service import ShopAIKeyServiceError


def _settings(top_k: int = 8) -> SimpleNamespace:
    return SimpleNamespace(retrieval_semantic_top_k=top_k)


def test_semantic_search_rejects_empty_question_before_embedding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    create_embedding = Mock()
    search_vectors = Mock()

    monkeypatch.setattr(retrieval_service, "create_embedding", create_embedding)
    monkeypatch.setattr(retrieval_service, "search_vectors", search_vectors)

    with pytest.raises(retrieval_service.RetrievalValidationError) as exc_info:
        retrieval_service.semantic_search("   ")

    assert str(exc_info.value) == "Question must be non-empty."
    create_embedding.assert_not_called()
    search_vectors.assert_not_called()


def test_semantic_search_uses_default_top_k_when_omitted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    create_embedding = Mock(return_value=[0.1, 0.2, 0.3])
    search_vectors = Mock(return_value=[])

    monkeypatch.setattr(retrieval_service, "get_settings", lambda: _settings(12))
    monkeypatch.setattr(retrieval_service, "create_embedding", create_embedding)
    monkeypatch.setattr(retrieval_service, "search_vectors", search_vectors)

    response = retrieval_service.semantic_search("What is the probation period?")

    assert response.question == "What is the probation period?"
    assert response.results == []
    search_vectors.assert_called_once_with(
        query_vector=[0.1, 0.2, 0.3],
        top_k=12,
        document_ids=None,
    )


def test_semantic_search_returns_empty_results_for_no_qdrant_matches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    create_embedding = Mock(return_value=[0.1, 0.2, 0.3])
    search_vectors = Mock(return_value=[])
    get_chunk_content_by_ids = Mock()

    monkeypatch.setattr(retrieval_service, "create_embedding", create_embedding)
    monkeypatch.setattr(retrieval_service, "search_vectors", search_vectors)
    monkeypatch.setattr(
        retrieval_service,
        "get_chunk_content_by_ids",
        get_chunk_content_by_ids,
        raising=False,
    )

    response = retrieval_service.semantic_search("No matching chunks?", top_k=2)

    assert response.model_dump(mode="json") == {
        "question": "No matching chunks?",
        "results": [],
    }
    get_chunk_content_by_ids.assert_not_called()


def test_semantic_search_wraps_shopaikey_failure_with_safe_error_and_log(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    secret = "sk-live-secret-value"
    provider_error = ShopAIKeyServiceError(
        f"ShopAIKey upstream rejected Authorization Bearer {secret}"
    )
    create_embedding = Mock(side_effect=provider_error)
    search_vectors = Mock()

    monkeypatch.setattr(retrieval_service, "create_embedding", create_embedding)
    monkeypatch.setattr(retrieval_service, "search_vectors", search_vectors)

    with caplog.at_level(logging.ERROR, logger=retrieval_service.logger.name):
        with pytest.raises(retrieval_service.RetrievalDependencyError) as exc_info:
            retrieval_service.semantic_search("What is indexed?", top_k=2)

    assert exc_info.value.public_message == "Semantic retrieval is temporarily unavailable."
    assert str(exc_info.value) == "Semantic retrieval is temporarily unavailable."
    assert exc_info.value.__cause__ is provider_error
    assert secret not in str(exc_info.value)
    assert secret not in caplog.text
    assert "ShopAIKey embedding failed during semantic retrieval" in caplog.text
    assert "ShopAIKeyServiceError" in caplog.text
    search_vectors.assert_not_called()


@pytest.mark.parametrize("top_k", [0, 51])
def test_semantic_search_rejects_top_k_outside_bounds_before_embedding(
    monkeypatch: pytest.MonkeyPatch,
    top_k: int,
) -> None:
    create_embedding = Mock()
    search_vectors = Mock()

    monkeypatch.setattr(retrieval_service, "create_embedding", create_embedding)
    monkeypatch.setattr(retrieval_service, "search_vectors", search_vectors)

    with pytest.raises(retrieval_service.RetrievalValidationError) as exc_info:
        retrieval_service.semantic_search("valid question", top_k=top_k)

    assert str(exc_info.value) == "top_k must be between 1 and 50."
    create_embedding.assert_not_called()
    search_vectors.assert_not_called()


def test_semantic_search_embeds_trimmed_question(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    create_embedding = Mock(return_value=[0.4, 0.5])
    search_vectors = Mock(return_value=[])

    monkeypatch.setattr(retrieval_service, "create_embedding", create_embedding)
    monkeypatch.setattr(retrieval_service, "search_vectors", search_vectors)

    response = retrieval_service.semantic_search("  What changed?  ", top_k=3)

    assert response.question == "What changed?"
    create_embedding.assert_called_once_with("What changed?")


def test_semantic_search_delegates_vector_and_document_ids_to_qdrant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document_ids = [
        UUID("11111111-1111-1111-1111-111111111111"),
        UUID("22222222-2222-2222-2222-222222222222"),
    ]
    create_embedding = Mock(return_value=[0.6, 0.7, 0.8])
    search_vectors = Mock(return_value=[])

    monkeypatch.setattr(retrieval_service, "create_embedding", create_embedding)
    monkeypatch.setattr(retrieval_service, "search_vectors", search_vectors)

    retrieval_service.semantic_search(
        "Find selected document facts",
        document_ids=document_ids,
        top_k=5,
    )

    search_vectors.assert_called_once_with(
        query_vector=[0.6, 0.7, 0.8],
        top_k=5,
        document_ids=document_ids,
    )


def test_semantic_search_maps_complete_qdrant_payload_to_response_shape(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    create_embedding = Mock(return_value=[0.1])
    search_vectors = Mock(
        return_value=[
            SimpleNamespace(
                payload={
                    "chunk_id": "33333333-3333-3333-3333-333333333333",
                    "document_id": "44444444-4444-4444-4444-444444444444",
                    "file_name": "contract.pdf",
                    "file_type": "pdf",
                    "content": "Full chunk text",
                    "content_preview": "Preview text",
                    "page_number": 3,
                    "section_title": "Probation",
                    "chunk_index": 4,
                },
                semantic_similarity=0.88,
            )
        ]
    )

    monkeypatch.setattr(retrieval_service, "create_embedding", create_embedding)
    monkeypatch.setattr(retrieval_service, "search_vectors", search_vectors)

    response = retrieval_service.semantic_search("probation", top_k=1)

    assert response.results[0].chunk_id == UUID("33333333-3333-3333-3333-333333333333")
    assert response.results[0].document_id == UUID(
        "44444444-4444-4444-4444-444444444444"
    )
    assert response.results[0].file_name == "contract.pdf"
    assert response.results[0].file_type == "pdf"
    assert response.results[0].content == "Full chunk text"
    assert response.results[0].content_preview == "Preview text"
    assert response.results[0].page_number == 3
    assert response.results[0].section_title == "Probation"
    assert response.results[0].chunk_index == 4
    assert response.results[0].semantic_similarity == 0.88


def test_semantic_search_maps_missing_optional_payload_fields_to_null(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    create_embedding = Mock(return_value=[0.1])
    search_vectors = Mock(
        return_value=[
            SimpleNamespace(
                payload={
                    "chunk_id": "33333333-3333-3333-3333-333333333333",
                    "document_id": "44444444-4444-4444-4444-444444444444",
                },
                semantic_similarity=0.77,
            )
        ]
    )

    monkeypatch.setattr(retrieval_service, "create_embedding", create_embedding)
    monkeypatch.setattr(retrieval_service, "search_vectors", search_vectors)

    response = retrieval_service.semantic_search("probation", top_k=1)

    result = response.results[0]
    assert result.file_name is None
    assert result.file_type is None
    assert result.content is None
    assert result.content_preview is None
    assert result.page_number is None
    assert result.section_title is None
    assert result.chunk_index is None
    assert result.semantic_similarity == 0.77


def test_semantic_search_maps_malformed_optional_payload_fields_to_null(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    create_embedding = Mock(return_value=[0.1])
    search_vectors = Mock(
        return_value=[
            SimpleNamespace(
                payload={
                    "chunk_id": "33333333-3333-3333-3333-333333333333",
                    "document_id": "44444444-4444-4444-4444-444444444444",
                    "file_name": {"unexpected": "object"},
                    "file_type": ["pdf"],
                    "content": {"text": "Full chunk text"},
                    "content_preview": ["Preview text"],
                    "page_number": "not-a-number",
                    "section_title": ["Probation"],
                    "chunk_index": {"index": 4},
                },
                semantic_similarity=0.66,
            )
        ]
    )

    monkeypatch.setattr(retrieval_service, "create_embedding", create_embedding)
    monkeypatch.setattr(retrieval_service, "search_vectors", search_vectors)

    with caplog.at_level(logging.WARNING, logger=retrieval_service.logger.name):
        response = retrieval_service.semantic_search("probation", top_k=1)

    result = response.results[0]
    assert result.file_name is None
    assert result.file_type is None
    assert result.content is None
    assert result.content_preview is None
    assert result.page_number is None
    assert result.section_title is None
    assert result.chunk_index is None
    assert result.semantic_similarity == 0.66
    assert "Malformed optional Qdrant payload field" in caplog.text


@pytest.mark.parametrize(
    "payload",
    [
        {"document_id": "44444444-4444-4444-4444-444444444444"},
        {"chunk_id": "33333333-3333-3333-3333-333333333333"},
        {
            "chunk_id": "not-a-uuid",
            "document_id": "44444444-4444-4444-4444-444444444444",
        },
        {
            "chunk_id": "33333333-3333-3333-3333-333333333333",
            "document_id": "not-a-uuid",
        },
    ],
)
def test_semantic_search_skips_malformed_identity_payloads(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    payload: dict[str, str],
) -> None:
    create_embedding = Mock(return_value=[0.1])
    search_vectors = Mock(
        return_value=[
            SimpleNamespace(payload=payload, semantic_similarity=0.55),
        ]
    )

    monkeypatch.setattr(retrieval_service, "create_embedding", create_embedding)
    monkeypatch.setattr(retrieval_service, "search_vectors", search_vectors)

    with caplog.at_level(logging.WARNING, logger=retrieval_service.logger.name):
        response = retrieval_service.semantic_search("probation", top_k=1)

    assert response.results == []
    assert "Skipping malformed Qdrant point" in caplog.text


def test_semantic_search_skips_point_with_non_mapping_payload(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    create_embedding = Mock(return_value=[0.1])
    search_vectors = Mock(
        return_value=[
            SimpleNamespace(payload="not-a-payload", semantic_similarity=0.44),
        ]
    )

    monkeypatch.setattr(retrieval_service, "create_embedding", create_embedding)
    monkeypatch.setattr(retrieval_service, "search_vectors", search_vectors)

    with caplog.at_level(logging.WARNING, logger=retrieval_service.logger.name):
        response = retrieval_service.semantic_search("probation", top_k=1)

    assert response.results == []
    assert "Skipping malformed Qdrant point" in caplog.text


def test_semantic_search_fetches_missing_full_content_from_supabase(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chunk_id = UUID("33333333-3333-3333-3333-333333333333")
    create_embedding = Mock(return_value=[0.1])
    search_vectors = Mock(
        return_value=[
            SimpleNamespace(
                payload={
                    "chunk_id": str(chunk_id),
                    "document_id": "44444444-4444-4444-4444-444444444444",
                    "content_preview": "Preview text",
                },
                semantic_similarity=0.88,
            )
        ]
    )
    get_chunk_content_by_ids = Mock(
        return_value={str(chunk_id): "Full chunk text from Supabase"}
    )

    monkeypatch.setattr(retrieval_service, "create_embedding", create_embedding)
    monkeypatch.setattr(retrieval_service, "search_vectors", search_vectors)
    monkeypatch.setattr(
        retrieval_service,
        "get_chunk_content_by_ids",
        get_chunk_content_by_ids,
        raising=False,
    )

    response = retrieval_service.semantic_search("probation", top_k=1)

    assert response.results[0].content == "Full chunk text from Supabase"
    assert response.results[0].content_preview == "Preview text"
    get_chunk_content_by_ids.assert_called_once_with([str(chunk_id)])


def test_semantic_search_omits_preview_only_points_when_supabase_row_is_absent(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    chunk_id = UUID("33333333-3333-3333-3333-333333333333")
    create_embedding = Mock(return_value=[0.1])
    search_vectors = Mock(
        return_value=[
            SimpleNamespace(
                payload={
                    "chunk_id": str(chunk_id),
                    "document_id": "44444444-4444-4444-4444-444444444444",
                    "content_preview": "Preview text",
                },
                semantic_similarity=0.88,
            )
        ]
    )
    get_chunk_content_by_ids = Mock(return_value={})

    monkeypatch.setattr(retrieval_service, "create_embedding", create_embedding)
    monkeypatch.setattr(retrieval_service, "search_vectors", search_vectors)
    monkeypatch.setattr(
        retrieval_service,
        "get_chunk_content_by_ids",
        get_chunk_content_by_ids,
        raising=False,
    )

    with caplog.at_level(logging.WARNING, logger=retrieval_service.logger.name):
        response = retrieval_service.semantic_search("probation", top_k=1)

    assert response.results == []
    assert "Supabase chunk row was not found" in caplog.text


def test_get_chunk_content_by_ids_filters_single_user(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows = [
        {
            "id": "33333333-3333-3333-3333-333333333333",
            "content": "Full chunk text",
        }
    ]
    query = Mock()
    query.select.return_value = query
    query.in_.return_value = query
    query.eq.return_value = query
    query.execute.return_value = SimpleNamespace(data=rows)
    client = SimpleNamespace(table=Mock(return_value=query))
    settings = SimpleNamespace(single_user_id="single_user")

    monkeypatch.setattr(supabase_service, "get_settings", lambda: settings)
    monkeypatch.setattr(supabase_service, "get_supabase_client", lambda: client)

    result = supabase_service.get_chunk_content_by_ids(
        ["33333333-3333-3333-3333-333333333333"]
    )

    assert result == {
        "33333333-3333-3333-3333-333333333333": "Full chunk text",
    }
    client.table.assert_called_once_with("document_chunks")
    query.select.assert_called_once_with("id, content")
    query.in_.assert_called_once_with(
        "id", ["33333333-3333-3333-3333-333333333333"]
    )
    query.eq.assert_called_once_with("user_id", "single_user")
    query.execute.assert_called_once_with()
