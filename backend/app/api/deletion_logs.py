from fastapi import APIRouter, HTTPException, Query, status

from app.schemas.deletion_logs import DeletionLogListResponse, DeletionLogStatus
from app.services import deletion_log_service


router = APIRouter()


@router.get(
    "",
    response_model=DeletionLogListResponse,
    status_code=status.HTTP_200_OK,
)
def get_deletion_logs(
    status_filter: DeletionLogStatus | None = Query(
        default=None,
        alias="status",
    ),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> DeletionLogListResponse:
    try:
        return deletion_log_service.list_deletion_logs(
            status=status_filter,
            limit=limit,
            offset=offset,
        )
    except deletion_log_service.DeletionLogServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=exc.public_message,
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=deletion_log_service.SAFE_DELETION_LOG_MESSAGE,
        ) from exc


__all__ = ["get_deletion_logs", "router"]
