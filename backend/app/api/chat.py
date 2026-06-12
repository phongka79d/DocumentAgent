from collections.abc import Callable
from typing import Any, Coroutine

from fastapi import APIRouter, HTTPException, Request, Response, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute

from app.agents.graph import run_qa_workflow
from app.schemas.chat import ChatAskRequest, ChatAskResponse
from app.services import agent_run_service, chat_service


class ChatValidationRoute(APIRoute):
    def get_route_handler(
        self,
    ) -> Callable[[Request], Coroutine[Any, Any, Response]]:
        route_handler = super().get_route_handler()

        async def validation_as_bad_request(request: Request) -> Response:
            try:
                return await route_handler(request)
            except RequestValidationError as exc:
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={"detail": jsonable_encoder(exc.errors())},
                )

        return validation_as_bad_request


router = APIRouter(route_class=ChatValidationRoute)


@router.post(
    "/ask",
    response_model=ChatAskResponse,
    status_code=status.HTTP_200_OK,
)
def ask_question(request: ChatAskRequest) -> ChatAskResponse:
    try:
        context = chat_service.prepare_chat_persistence(
            session_id=request.session_id,
            question=request.question,
            document_ids=request.document_ids,
        )
        session_id = str(context.session["id"])
        workflow_result = run_qa_workflow(
            request.question,
            request.document_ids,
            session_id=session_id,
        )
        chat_service.persist_assistant_message(
            session_id=session_id,
            agent_run_id=workflow_result["agent_run_id"],
            answer=workflow_result["answer"],
            confidence=workflow_result["confidence"],
        )
        return ChatAskResponse.model_validate(workflow_result)
    except chat_service.ChatValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=exc.public_message,
        ) from exc
    except (
        chat_service.ChatSessionNotFoundError,
        chat_service.SelectedDocumentNotFoundError,
        agent_run_service.AgentRunSessionNotFoundError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=exc.public_message,
        ) from exc
    except (
        chat_service.ChatDependencyError,
        agent_run_service.AgentRunServiceError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=exc.public_message,
        ) from exc


__all__ = ["ask_question", "router"]
