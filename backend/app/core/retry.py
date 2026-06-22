from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import time
from typing import Any, TypeVar

from app.core.config import Settings, get_settings

T = TypeVar("T")


@dataclass(frozen=True)
class RetryClassification:
    retryable: bool
    error_code: str
    status_code: int | None = None


@dataclass(frozen=True)
class RetryAttempt:
    operation: str
    attempt: int
    max_attempts: int
    retryable: bool
    error_code: str
    delay_seconds: float | None = None


class RetryExhaustedError(RuntimeError):
    def __init__(
        self,
        operation: str,
        last_exception: BaseException,
        *,
        attempts: int,
        error_code: str,
    ) -> None:
        super().__init__(f"{operation} failed after {attempts} attempts")
        self.operation = operation
        self.last_exception = last_exception
        self.attempts = attempts
        self.error_code = error_code


def _settings(settings: Settings | None = None) -> Settings:
    return settings if settings is not None else get_settings()


def _status_code_from_exception(exc: BaseException) -> int | None:
    status_code = getattr(exc, "status_code", None)
    if isinstance(status_code, int):
        return status_code

    response = getattr(exc, "response", None)
    status_code = getattr(response, "status_code", None)
    if isinstance(status_code, int):
        return status_code

    return None


def _class_name_contains(exc: BaseException, tokens: tuple[str, ...]) -> bool:
    names = [exc.__class__.__name__.lower()]
    names.extend(cls.__name__.lower() for cls in exc.__class__.__mro__)
    return any(token in name for token in tokens for name in names)


def classify_exception(exc: BaseException) -> RetryClassification:
    status_code = _status_code_from_exception(exc)
    if status_code is not None:
        if status_code == 429:
            return RetryClassification(True, "http_429", status_code)
        if 500 <= status_code <= 599:
            return RetryClassification(True, "http_5xx", status_code)
        return RetryClassification(False, f"http_{status_code}", status_code)

    if isinstance(exc, TimeoutError) or _class_name_contains(exc, ("timeout",)):
        return RetryClassification(True, "timeout")
    if isinstance(exc, ConnectionError) or _class_name_contains(
        exc, ("connect", "connection")
    ):
        return RetryClassification(True, "connection")

    return RetryClassification(False, "contract_error")


def is_retryable_exception(exc: BaseException) -> bool:
    return classify_exception(exc).retryable


def capped_exponential_delay(
    attempt: int,
    *,
    base_delay_seconds: float,
    max_delay_seconds: float,
) -> float:
    if attempt <= 0:
        return 0.0
    delay = base_delay_seconds * (2 ** (attempt - 1))
    return min(delay, max_delay_seconds)


def retry_sync(
    operation: str,
    func: Callable[[], T],
    *,
    settings: Settings | None = None,
    sleep: Callable[[float], None] | None = None,
    monotonic: Callable[[], float] | None = None,
    on_attempt: Callable[[RetryAttempt], None] | None = None,
) -> T:
    resolved_settings = _settings(settings)
    max_attempts = max(1, int(resolved_settings.WORKFLOW_MAX_ATTEMPTS))
    base_delay = float(resolved_settings.WORKFLOW_RETRY_BASE_DELAY_SECONDS)
    max_delay = float(resolved_settings.WORKFLOW_RETRY_MAX_DELAY_SECONDS)
    sleeper = sleep if sleep is not None else time.sleep
    clock = monotonic if monotonic is not None else time.monotonic

    _ = clock()
    for attempt in range(1, max_attempts + 1):
        try:
            result = func()
        except Exception as exc:
            classification = classify_exception(exc)
            should_retry = classification.retryable and attempt < max_attempts
            delay = (
                capped_exponential_delay(
                    attempt,
                    base_delay_seconds=base_delay,
                    max_delay_seconds=max_delay,
                )
                if should_retry
                else None
            )
            if on_attempt is not None:
                on_attempt(
                    RetryAttempt(
                        operation=operation,
                        attempt=attempt,
                        max_attempts=max_attempts,
                        retryable=classification.retryable,
                        error_code=classification.error_code,
                        delay_seconds=delay,
                    )
                )
            if not classification.retryable:
                raise
            if attempt >= max_attempts:
                raise RetryExhaustedError(
                    operation,
                    exc,
                    attempts=attempt,
                    error_code=classification.error_code,
                ) from exc
            sleeper(delay or 0.0)
            continue
        else:
            if on_attempt is not None:
                on_attempt(
                    RetryAttempt(
                        operation=operation,
                        attempt=attempt,
                        max_attempts=max_attempts,
                        retryable=False,
                        error_code="ok",
                    )
                )
            return result

    raise AssertionError("retry loop exited unexpectedly")


__all__ = [
    "RetryAttempt",
    "RetryClassification",
    "RetryExhaustedError",
    "capped_exponential_delay",
    "classify_exception",
    "is_retryable_exception",
    "retry_sync",
]
