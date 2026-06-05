import sys
from pathlib import Path
from uuid import UUID

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import app
from app.schemas.embeddings import ChunkIndexingError, DocumentIndexingResult
from app.services import embedding_service


client = TestClient(app)


DOCUMENT_ID = UUID("11111111-1111-1111-1111-111111111111")
CHUNK_ID = UUID("22222222-2222-2222-2222-222222222222")


def test_internal_index_document_api_returns_indexing_result(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.api.documents.embedding_service.index_document_chunks",
        lambda document_id: DocumentIndexingResult(
            document_id=document_id,
            indexed_count=2,
            failed_count=0,
            errors=[],
        ),
    )

    response = client.post(f"/api/documents/{DOCUMENT_ID}/index")

    assert response.status_code == 200
    assert response.json() == {
        "document_id": str(DOCUMENT_ID),
        "indexed_count": 2,
        "failed_count": 0,
        "errors": [],
    }


def test_internal_index_document_api_maps_document_not_found_to_404(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "app.api.documents.embedding_service.index_document_chunks",
        lambda document_id: (_ for _ in ()).throw(
            embedding_service.DocumentIndexingError("Document not found.")
        ),
    )

    response = client.post(f"/api/documents/{DOCUMENT_ID}/index")

    assert response.status_code == 404
    assert response.json()["detail"] == "Document not found."


def test_internal_index_document_api_maps_no_work_to_no_chunks_error(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "app.api.documents.embedding_service.index_document_chunks",
        lambda document_id: DocumentIndexingResult(
            document_id=document_id,
            indexed_count=0,
            failed_count=0,
            errors=[],
        ),
    )

    response = client.post(f"/api/documents/{DOCUMENT_ID}/index")

    assert response.status_code == 400
    assert response.json()["detail"] == "Document has no chunks to index."


def test_internal_index_document_api_maps_total_shopaikey_failure_to_500(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "app.api.documents.embedding_service.index_document_chunks",
        lambda document_id: DocumentIndexingResult(
            document_id=document_id,
            indexed_count=0,
            failed_count=1,
            errors=[
                ChunkIndexingError(
                    chunk_id=CHUNK_ID,
                    chunk_index=0,
                    message="ShopAIKey embedding request timed out.",
                )
            ],
        ),
    )

    response = client.post(f"/api/documents/{DOCUMENT_ID}/index")

    assert response.status_code == 500
    assert response.json()["detail"] == {
        "message": "Indexing failed for all chunks.",
        "errors": [
            {
                "chunk_id": str(CHUNK_ID),
                "chunk_index": 0,
                "message": "ShopAIKey embedding request timed out.",
            }
        ],
    }


def test_internal_index_document_api_maps_total_qdrant_failure_to_500(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "app.api.documents.embedding_service.index_document_chunks",
        lambda document_id: DocumentIndexingResult(
            document_id=document_id,
            indexed_count=0,
            failed_count=1,
            errors=[
                ChunkIndexingError(
                    chunk_id=CHUNK_ID,
                    chunk_index=0,
                    message="Qdrant chunk vector upsert failed.",
                )
            ],
        ),
    )

    response = client.post(f"/api/documents/{DOCUMENT_ID}/index")

    assert response.status_code == 500
    assert response.json()["detail"]["message"] == "Indexing failed for all chunks."
    assert response.json()["detail"]["errors"][0]["message"] == (
        "Qdrant chunk vector upsert failed."
    )


def test_internal_index_document_api_returns_partial_failure_result(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "app.api.documents.embedding_service.index_document_chunks",
        lambda document_id: DocumentIndexingResult(
            document_id=document_id,
            indexed_count=1,
            failed_count=1,
            errors=[
                ChunkIndexingError(
                    chunk_id=CHUNK_ID,
                    chunk_index=0,
                    message="Qdrant chunk vector upsert failed.",
                )
            ],
        ),
    )

    response = client.post(f"/api/documents/{DOCUMENT_ID}/index")

    assert response.status_code == 200
    assert response.json()["indexed_count"] == 1
    assert response.json()["failed_count"] == 1
    assert response.json()["errors"][0]["message"] == (
        "Qdrant chunk vector upsert failed."
    )
