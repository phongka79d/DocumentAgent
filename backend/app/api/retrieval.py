from typing import Union

from fastapi import APIRouter, HTTPException, status

from app.schemas.retrieval import HybridSearchResponse, SearchRequest, SearchResponse
from app.services import hybrid_retrieval_service, retrieval_service
from app.services.qdrant_service import QdrantSearchError
from app.services.hybrid_retrieval_service import (
    HybridRetrievalDependencyError,
    HybridRetrievalValidationError,
)
from app.services.retrieval_service import (
    RetrievalDependencyError,
    RetrievalValidationError,
)

router = APIRouter()


@router.post(
    "/search",
    response_model=Union[SearchResponse, HybridSearchResponse],
    status_code=status.HTTP_200_OK,
)
def search_retrieval(request: SearchRequest) -> SearchResponse | HybridSearchResponse:
    try:
        if request.mode == "hybrid":
            return hybrid_retrieval_service.retrieve_hybrid(
                question=request.question,
                document_ids=request.document_ids,
                final_top_k=request.top_k,
            )

        return retrieval_service.semantic_search(
            question=request.question,
            document_ids=request.document_ids,
            top_k=request.top_k,
        )
    except (RetrievalValidationError, HybridRetrievalValidationError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except (RetrievalDependencyError, HybridRetrievalDependencyError) as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=exc.public_message,
        ) from exc
    except QdrantSearchError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Semantic retrieval is temporarily unavailable.",
        ) from exc
