from __future__ import annotations

from fastapi import APIRouter, status

from app.core.config import Settings, get_settings
from app.core.errors import safe_http_exception
from app.models.schemas import MessageListResponse
from app.services import messages as message_service

router = APIRouter(
    prefix="/messages",
    tags=["messages"],
)

DEFAULT_MESSAGES_ERROR = "Message history unavailable"


def _resolve_settings() -> Settings:
    return get_settings()


@router.get("", response_model=MessageListResponse)
def get_messages(limit: int = 50) -> MessageListResponse:
    settings = _resolve_settings()
    try:
        messages = message_service.list_messages(limit=limit, settings=settings)
        return MessageListResponse(messages=messages)
    except Exception as exc:  # pragma: no cover - defensive API boundary
        raise safe_http_exception(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            DEFAULT_MESSAGES_ERROR,
        ) from exc
