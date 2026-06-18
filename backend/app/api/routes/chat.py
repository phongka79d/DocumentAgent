from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from fastapi import APIRouter, status
from pydantic import ValidationError

from app.core.config import Settings, get_settings
from app.core.errors import safe_http_exception
from app.graphs.query_graph import build_query_graph
from app.models.schemas import ChatRequest, ChatResponse

router = APIRouter(
    prefix="/chat",
    tags=["chat"],
)

DEFAULT_CHAT_ERROR = "Query failed"


def _resolve_settings() -> Settings:
    return get_settings()


def _response_payload(result: Mapping[str, Any]) -> dict[str, Any]:
    error_message = result.get("error_message")
    if error_message:
        raise safe_http_exception(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            str(error_message),
        )

    return {
        "answer": result.get("answer"),
        "sources": result.get("sources") or [],
    }


@router.post("", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    settings = _resolve_settings()
    try:
        graph = build_query_graph(settings=settings)
        result = graph.invoke(request.model_dump(mode="json"))
    except Exception as exc:  # pragma: no cover - defensive API boundary
        raise safe_http_exception(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            str(exc) or DEFAULT_CHAT_ERROR,
        ) from exc

    if not isinstance(result, Mapping):
        raise safe_http_exception(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            DEFAULT_CHAT_ERROR,
        )

    try:
        return ChatResponse.model_validate(_response_payload(result))
    except ValidationError as exc:
        raise safe_http_exception(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            DEFAULT_CHAT_ERROR,
        ) from exc
