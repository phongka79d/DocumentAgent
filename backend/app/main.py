import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router as health_router
from app.core.config import get_settings
from app.core.logging import setup_logging


setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_application: FastAPI) -> AsyncIterator[None]:
    try:
        settings = get_settings()
        logger.info(
            "Starting Document QA Agent backend in %s environment",
            settings.app_env,
        )
        yield
    except Exception:
        logger.exception("Backend startup or shutdown failed")
        raise


def create_app() -> FastAPI:
    try:
        settings = get_settings()
        application = FastAPI(title="Document QA Agent", lifespan=lifespan)
        application.add_middleware(
            CORSMiddleware,
            allow_origins=[settings.frontend_origin],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        application.include_router(health_router, prefix="/api")
        return application
    except Exception:
        logger.exception("Failed to create FastAPI application")
        raise


app = create_app()
