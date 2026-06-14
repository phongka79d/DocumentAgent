import logging

from app.core.config import get_settings
from app.schemas.deletion_logs import (
    DeletionLogListResponse,
    DeletionLogResponse,
    DeletionLogStatus,
)
from app.services.supabase_service import (
    list_deletion_logs as fetch_deletion_logs,
)


logger = logging.getLogger(__name__)
SAFE_DELETION_LOG_MESSAGE = "Deletion logs are temporarily unavailable."


class DeletionLogServiceError(RuntimeError):
    def __init__(self) -> None:
        self.public_message = SAFE_DELETION_LOG_MESSAGE
        super().__init__(self.public_message)


def list_deletion_logs(
    *,
    status: DeletionLogStatus | None,
    limit: int,
    offset: int,
) -> DeletionLogListResponse:
    try:
        user_id = get_settings().single_user_id
        rows = fetch_deletion_logs(user_id, status, limit + 1, offset)
        logs = [DeletionLogResponse.model_validate(row) for row in rows[:limit]]
        return DeletionLogListResponse(
            logs=logs,
            limit=limit,
            offset=offset,
            has_more=len(rows) > limit,
        )
    except Exception as exc:
        logger.warning(
            "Deletion log listing failed: %s",
            type(exc).__name__,
        )
        raise DeletionLogServiceError() from exc


__all__ = [
    "DeletionLogServiceError",
    "SAFE_DELETION_LOG_MESSAGE",
    "list_deletion_logs",
]
