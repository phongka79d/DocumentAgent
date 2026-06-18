from fastapi import HTTPException, status

DEFAULT_SAFE_ERROR_DETAIL = "An unexpected error occurred"
INVALID_ADMIN_TOKEN_DETAIL = "Invalid or missing X-Admin-API-Token"


def safe_detail(detail: str | None, fallback: str = DEFAULT_SAFE_ERROR_DETAIL) -> str:
    cleaned = (detail or "").strip()
    return cleaned if cleaned else fallback


def safe_http_exception(status_code: int, detail: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail=safe_detail(detail))


def invalid_admin_token_exception() -> HTTPException:
    return safe_http_exception(status.HTTP_401_UNAUTHORIZED, INVALID_ADMIN_TOKEN_DETAIL)

