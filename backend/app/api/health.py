from pydantic import BaseModel
from fastapi import APIRouter

from app.core.config import get_settings


router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    service: str
    app_env: str


@router.get("/health", response_model=HealthResponse)
def get_health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        status="ok",
        service="document-qa-agent",
        app_env=settings.app_env,
    )
