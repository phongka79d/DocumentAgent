from fastapi import APIRouter, HTTPException, status

from app.schemas.retrieval import SearchRequest, SearchResponse
from app.services import retrieval_service
from app.services.qdrant_service import QdrantSearchError
from app.services.retrieval_service import (
    RetrievalDependencyError,
    RetrievalValidationError,
)

router = APIRouter()


@router.post(
    "/search",
    response_model=SearchResponse,
    status_code=status.HTTP_200_OK,
)
def search_retrieval(request: SearchRequest) -> SearchResponse:
    try:
        return retrieval_service.semantic_search(
            question=request.question,
            document_ids=request.document_ids,
            top_k=request.top_k,
        )
    except RetrievalValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except RetrievalDependencyError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=exc.public_message,
        ) from exc
    except QdrantSearchError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Semantic retrieval is temporarily unavailable.",
        ) from exc
