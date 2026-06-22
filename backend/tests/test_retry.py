from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.core.config import Settings
from app.core.retry import (
    RetryExhaustedError,
    capped_exponential_delay,
    classify_exception,
    retry_sync,
)


class StatusError(RuntimeError):
    def __init__(self, status_code: int) -> None:
        super().__init__(f"http {status_code}")
        self.response = SimpleNamespace(status_code=status_code)


def _settings() -> Settings:
    return Settings(
        _env_file=None,
        WORKFLOW_MAX_ATTEMPTS=3,
        WORKFLOW_RETRY_BASE_DELAY_SECONDS=0.25,
        WORKFLOW_RETRY_MAX_DELAY_SECONDS=0.5,
    )


def test_capped_exponential_delay_uses_configured_maximum():
    assert capped_exponential_delay(
        1,
        base_delay_seconds=0.25,
        max_delay_seconds=0.5,
    ) == 0.25
    assert capped_exponential_delay(
        2,
        base_delay_seconds=0.25,
        max_delay_seconds=0.5,
    ) == 0.5
    assert capped_exponential_delay(
        3,
        base_delay_seconds=0.25,
        max_delay_seconds=0.5,
    ) == 0.5


@pytest.mark.parametrize(
    "exc",
    [
        TimeoutError("timed out"),
        ConnectionError("connection failed"),
        StatusError(429),
        StatusError(500),
        StatusError(503),
    ],
)
def test_retry_classification_accepts_only_documented_transient_failures(exc):
    assert classify_exception(exc).retryable is True


@pytest.mark.parametrize(
    "exc",
    [
        ValueError("bad contract"),
        StatusError(400),
        StatusError(401),
        StatusError(403),
        StatusError(404),
    ],
)
def test_retry_classification_rejects_contract_and_documented_4xx_failures(exc):
    assert classify_exception(exc).retryable is False


def test_retry_sync_recovers_with_no_real_sleep():
    calls = 0
    sleeps: list[float] = []
    attempts = []

    def _operation():
        nonlocal calls
        calls += 1
        if calls < 3:
            raise TimeoutError("temporary")
        return "ok"

    result = retry_sync(
        "temporary_operation",
        _operation,
        settings=_settings(),
        sleep=sleeps.append,
        monotonic=lambda: 100.0,
        on_attempt=attempts.append,
    )

    assert result == "ok"
    assert calls == 3
    assert sleeps == [0.25, 0.5]
    assert [attempt.attempt for attempt in attempts] == [1, 2, 3]


def test_retry_sync_runs_non_retryable_failure_once():
    calls = 0
    sleeps: list[float] = []

    def _operation():
        nonlocal calls
        calls += 1
        raise ValueError("invalid model json")

    with pytest.raises(ValueError):
        retry_sync(
            "contract_operation",
            _operation,
            settings=_settings(),
            sleep=sleeps.append,
        )

    assert calls == 1
    assert sleeps == []


def test_retry_sync_raises_stable_exhaustion_error_after_max_attempts():
    sleeps: list[float] = []

    with pytest.raises(RetryExhaustedError) as exc_info:
        retry_sync(
            "provider_operation",
            lambda: (_ for _ in ()).throw(StatusError(503)),
            settings=_settings(),
            sleep=sleeps.append,
        )

    assert exc_info.value.operation == "provider_operation"
    assert exc_info.value.attempts == 3
    assert exc_info.value.error_code == "http_5xx"
    assert sleeps == [0.25, 0.5]
