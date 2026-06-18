from dataclasses import dataclass
from typing import Any

import httpx

from app.core import config as config_module
from app.core.config import Settings

DEFAULT_JINA_RERANK_BASE_URL = "https://api.jina.ai/v1"


def _resolve_settings(settings: Settings | None = None) -> Settings:
    return settings if settings is not None else config_module.get_settings()


@dataclass(slots=True)
class JinaRerankClient:
    http_client: httpx.Client
    model: str

    def __enter__(self) -> "JinaRerankClient":
        self.http_client.__enter__()
        return self

    def __exit__(self, exc_type, exc, tb) -> Any:
        return self.http_client.__exit__(exc_type, exc, tb)

    def __getattr__(self, name: str) -> Any:
        return getattr(self.http_client, name)


def create_jina_client(settings: Settings | None = None) -> JinaRerankClient:
    resolved_settings = _resolve_settings(settings)
    http_client = httpx.Client(
        base_url=DEFAULT_JINA_RERANK_BASE_URL,
        headers={
            "Authorization": f"Bearer {resolved_settings.JINA_API_KEY}",
            "Accept": "application/json",
        },
    )
    return JinaRerankClient(
        http_client=http_client,
        model=resolved_settings.JINA_RERANK_MODEL,
    )

