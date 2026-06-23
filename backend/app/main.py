from contextlib import asynccontextmanager
from importlib import import_module, util
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import Settings, get_settings
from app.api.routes.health import router as health_router

DEFAULT_FRONTEND_ORIGIN = "http://localhost:5173"
OPTIONAL_API_ROUTE_MODULES = (
    "app.api.routes.documents",
    "app.api.routes.chat",
    "app.api.routes.messages",
    "app.api.routes.observability",
)


def _get_frontend_origin(settings: Settings) -> str:
    origin = settings.FRONTEND_ORIGIN.strip()
    return origin or DEFAULT_FRONTEND_ORIGIN


def _include_optional_router(app: FastAPI, module_name: str) -> None:
    if util.find_spec(module_name) is None:
        return

    module = import_module(module_name)
    router = getattr(module, "router", None)
    if router is not None:
        app.include_router(router, prefix="/api")


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """FastAPI lifespan that provisions Qdrant payload indexes on startup."""
    settings: Settings = getattr(app.state, "settings", get_settings())
    if settings.ENSURE_QDRANT_PAYLOAD_INDEXES_ON_STARTUP:
        try:
            from app.services.qdrant_client import (
                create_qdrant_client,
                ensure_qdrant_payload_indexes,
            )

            client = create_qdrant_client(settings)
            ensure_qdrant_payload_indexes(
                client,
                collection_name=settings.QDRANT_COLLECTION,
            )
        except Exception as exc:
            import logging

            logging.getLogger(__name__).warning(
                "Non-blocking Qdrant payload index provisioning failed: %s", exc
            )
    yield


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = get_settings() if settings is None else settings

    app = FastAPI(title="RagDocument API", lifespan=_lifespan)
    app.state.settings = settings
    app.dependency_overrides[get_settings] = lambda: settings
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[_get_frontend_origin(settings)],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health_router, prefix="/api")
    for module_name in OPTIONAL_API_ROUTE_MODULES:
        _include_optional_router(app, module_name)
    return app


app = create_app()
