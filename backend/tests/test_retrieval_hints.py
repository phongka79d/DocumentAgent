from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace

import pytest

from app.core.config import Settings
from app.core.contracts import RetrievalBoundary
from app.services import retrieval, retrieval_hints


def _test_settings() -> Settings:
    return Settings(
        _env_file=None,
        SHOPAIKEY_API_KEY="shopai-key",
        SHOPAIKEY_BASE_URL="https://api.shopaikey.com/v1",
        SHOPAIKEY_CHAT_MODEL="gpt-5-mini",
        SHOPAIKEY_INPUT_MODEL="gpt-5-mini",
        RETRIEVAL_HINT_TEMPERATURE=0.3,
        RETRIEVAL_HINT_MAX_TOKENS=77,
    )


@dataclass
class FakeChatCompletionsEndpoint:
    response: object
    calls: list[dict[str, object]] = field(default_factory=list)

    def create(
        self,
        *,
        model: str,
        messages: list[dict[str, object]],
        temperature: float | None = None,
        max_tokens: int | None = None,
        **kwargs,
    ):
        self.calls.append(
            {
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "kwargs": kwargs,
            }
        )
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


@dataclass
class FakeShopAIKeyClient:
    chat_response: object

    def __post_init__(self):
        self.chat = SimpleNamespace(
            completions=FakeChatCompletionsEndpoint(self.chat_response)
        )


def test_extract_retrieval_hints_uses_settings_temperature_and_max_tokens():
    settings = _test_settings()
    client = FakeShopAIKeyClient(
        SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content='{"boundary_positions":["beginning"]}'
                    )
                )
            ]
        )
    )

    hints = retrieval_hints.extract_retrieval_hints(
        "What happens at the beginning?",
        settings=settings,
        shopaikey_client=client,
    )

    assert hints == {"boundary_positions": [RetrievalBoundary.BEGINNING]}
    chat_call = client.chat.completions.calls[0]
    assert chat_call["model"] == settings.SHOPAIKEY_INPUT_MODEL
    assert chat_call["temperature"] == settings.RETRIEVAL_HINT_TEMPERATURE
    assert chat_call["max_tokens"] == settings.RETRIEVAL_HINT_MAX_TOKENS
    system_prompt = chat_call["messages"][0]["content"]
    assert f'"{RetrievalBoundary.BEGINNING}"' in system_prompt
    assert f'"{RetrievalBoundary.END}"' in system_prompt

def test_retrieval_compatibility_raises_retrieval_error_for_blank_question():
    with pytest.raises(retrieval.RetrievalError, match="question is required"):
        retrieval.extract_retrieval_hints("   ", settings=_test_settings())


def test_normalize_retrieval_hints_filters_unknown_boundary_values():
    hints = retrieval_hints.normalize_retrieval_hints(
        {
            "boundary_positions": [
                "unknown",
                RetrievalBoundary.BEGINNING,
                "END",
                RetrievalBoundary.END,
                "",
                None,
            ]
        }
    )

    assert hints == {
        "boundary_positions": [
            RetrievalBoundary.BEGINNING,
            RetrievalBoundary.END,
        ]
    }


def test_extract_retrieval_hints_returns_empty_hints_for_empty_response():
    settings = _test_settings()
    client = FakeShopAIKeyClient(
        SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=""))])
    )

    assert retrieval_hints.extract_retrieval_hints(
        "What is this about?",
        settings=settings,
        shopaikey_client=client,
    ) == {"boundary_positions": []}


def test_extract_retrieval_hints_empty_fallback_returns_fresh_lists():
    settings = _test_settings()
    client = FakeShopAIKeyClient(SimpleNamespace(choices=[]))

    first_hints = retrieval_hints.extract_retrieval_hints(
        "What is this about?",
        settings=settings,
        shopaikey_client=client,
    )
    first_hints["boundary_positions"].append("polluted")

    second_hints = retrieval_hints.extract_retrieval_hints(
        "What is this about?",
        settings=settings,
        shopaikey_client=client,
    )

    assert second_hints == {"boundary_positions": []}

def test_extract_retrieval_hints_returns_empty_hints_for_invalid_response():
    settings = _test_settings()
    client = FakeShopAIKeyClient(
        SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="{}"))])
    )

    assert retrieval_hints.extract_retrieval_hints(
        "What is this about?",
        settings=settings,
        shopaikey_client=client,
    ) == {"boundary_positions": []}

    client = FakeShopAIKeyClient(
        SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="not json"))]
        )
    )

    assert retrieval_hints.extract_retrieval_hints(
        "What is this about?",
        settings=settings,
        shopaikey_client=client,
    ) == {"boundary_positions": []}
