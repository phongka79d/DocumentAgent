from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.schemas.agent_runs import AgentRunEvidenceResponse, AgentRunLogsResponse
from app.services import agent_run_service


router = APIRouter()


@router.get(
    "/{agent_run_id}/evidence",
    response_model=AgentRunEvidenceResponse,
    status_code=status.HTTP_200_OK,
)
def get_agent_run_evidence(agent_run_id: UUID) -> AgentRunEvidenceResponse:
    try:
        return agent_run_service.get_agent_run_evidence(agent_run_id)
    except agent_run_service.AgentRunNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=exc.public_message,
        ) from exc
    except agent_run_service.AgentRunServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=exc.public_message,
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=agent_run_service.SAFE_AGENT_RUN_EVIDENCE_MESSAGE,
        ) from exc


@router.get(
    "/{agent_run_id}/logs",
    response_model=AgentRunLogsResponse,
    status_code=status.HTTP_200_OK,
)
def get_agent_run_logs(agent_run_id: UUID) -> AgentRunLogsResponse:
    try:
        return agent_run_service.get_agent_run_logs(agent_run_id)
    except agent_run_service.AgentRunNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=exc.public_message,
        ) from exc
    except agent_run_service.AgentRunServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=exc.public_message,
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=agent_run_service.SAFE_AGENT_RUN_LOGS_MESSAGE,
        ) from exc


__all__ = ["get_agent_run_evidence", "get_agent_run_logs", "router"]
