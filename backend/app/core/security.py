from typing import Annotated

from fastapi import Depends, Header

from app.core.config import Settings, get_settings
from app.core.errors import invalid_admin_token_exception

AdminAPIHeader = Annotated[str | None, Header(alias="X-Admin-API-Token")]


def require_admin_token(
    x_admin_api_token: AdminAPIHeader = None,
    settings: Settings = Depends(get_settings),
) -> None:
    expected_token = settings.ADMIN_API_TOKEN
    if not expected_token:
        return None

    if x_admin_api_token != expected_token:
        raise invalid_admin_token_exception()

    return None

