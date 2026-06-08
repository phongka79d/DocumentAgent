import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services import shopaikey_service


def _settings(
    *,
    api_key: str = "private-shopaikey-key",
    base_url: str = "https://api.shopaikey.test/v1/",
    embedding_model: str = "configured-embedding-model",
    chat_model: str = "configured-chat-model",
    rerank_model: str | None = "configured-rerank-model",
    enable_rerank: bool = False,
) -> SimpleNamespace:
    return SimpleNamespace(
        enable_rerank=enable_rerank,
        require_shopaikey_settings=lambda: {
            "api_key": api_key,
            "base_url": base_url,
            "embedding_model": embedding_model,
        },
        require_shopaikey_chat_settings=lambda: {
            "api_key": api_key,
            "base_url": base_url,
            "chat_model": chat_model,
        },
        require_shopaikey_rerank_settings=lambda: {
            "api_key": api_key,
            "base_url": base_url,
            "rerank_model": rerank_model,
        }
        if rerank_model
        else (_ for _ in ()).throw(
            RuntimeError(
                "Missing SHOPAIKEY_RERANK_MODEL. Configure ShopAIKey rerank settings in the backend environment before enabling rerank."
            )
        ),
    )


def test_rerank_candidates_returns_same_candidates_and_skips_provider_when_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidates = [object(), object()]
    post = Mock()

    monkeypatch.setattr(
        shopaikey_service,
        "get_settings",
        lambda: _settings(enable_rerank=False),
    )
    monkeypatch.setattr(shopaikey_service.httpx, "post", post)

    result = shopaikey_service.rerank_candidates(
        "What is the policy?",
        candidates,
        top_n=2,
    )

    assert result is candidates
    assert result == candidates
    post.assert_not_called()


def test_rerank_candidates_enabled_without_required_config_fails_safely(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret_key = "private-shopaikey-key"

    monkeypatch.setattr(
        shopaikey_service,
        "get_settings",
        lambda: _settings(
            api_key=secret_key,
            enable_rerank=True,
            rerank_model=None,
        ),
    )
    monkeypatch.setattr(shopaikey_service.httpx, "post", Mock())

    with pytest.raises(shopaikey_service.ShopAIKeyServiceError) as exc_info:
        shopaikey_service.rerank_candidates(
            "What is the policy?",
            [object()],
            top_n=1,
        )

    message = str(exc_info.value)
    assert "SHOPAIKEY_RERANK_MODEL" in message
    assert secret_key not in message
    shopaikey_service.httpx.post.assert_not_called()


@pytest.mark.parametrize(
    ("base_url", "expected_url"),
    [
        ("https://api.shopaikey.test/v1", "https://api.shopaikey.test/v1/embeddings"),
        ("https://api.shopaikey.test/v1/", "https://api.shopaikey.test/v1/embeddings"),
    ],
)
def test_create_embedding_posts_openai_style_request_with_configured_values(
    monkeypatch: pytest.MonkeyPatch,
    base_url: str,
    expected_url: str,
) -> None:
    response = Mock()
    response.json.return_value = {
        "data": [
            {
                "embedding": [0.1, 2, -0.3],
            }
        ]
    }
    response.raise_for_status = Mock()
    post = Mock(return_value=response)

    monkeypatch.setattr(
        shopaikey_service, "get_settings", lambda: _settings(base_url=base_url)
    )
    monkeypatch.setattr(shopaikey_service.httpx, "post", post)

    vector = shopaikey_service.create_embedding("chunk text")

    assert vector == [0.1, 2.0, -0.3]
    post.assert_called_once_with(
        expected_url,
        headers={
            "Authorization": "Bearer private-shopaikey-key",
        },
        json={
            "model": "configured-embedding-model",
            "input": "chunk text",
        },
        timeout=shopaikey_service.EMBEDDING_REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status.assert_called_once_with()


def test_create_embedding_uses_configured_model_without_hardcoded_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = Mock()
    response.json.return_value = {"data": [{"embedding": [1.0]}]}
    response.raise_for_status = Mock()
    post = Mock(return_value=response)

    monkeypatch.setattr(
        shopaikey_service,
        "get_settings",
        lambda: _settings(embedding_model="different-provider-model"),
    )
    monkeypatch.setattr(shopaikey_service.httpx, "post", post)

    shopaikey_service.create_embedding("text")

    assert post.call_args.kwargs["json"]["model"] == "different-provider-model"


def test_create_embedding_authorization_header_does_not_expose_key_in_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret_key = "private-shopaikey-key"

    monkeypatch.setattr(
        shopaikey_service,
        "get_settings",
        lambda: _settings(api_key=secret_key, base_url="https://api.shopaikey.test/v1"),
    )
    monkeypatch.setattr(
        shopaikey_service.httpx,
        "post",
        Mock(
            return_value=Mock(
                json=Mock(return_value={"data": []}),
                raise_for_status=Mock(),
            )
        ),
    )

    with pytest.raises(shopaikey_service.ShopAIKeyServiceError) as exc_info:
        shopaikey_service.create_embedding("text")

    message = str(exc_info.value)
    assert secret_key not in message
    assert "embedding vector" in message


@pytest.mark.parametrize(
    ("post_error", "expected_message"),
    [
        (httpx.TimeoutException("timed out"), "timed out"),
        (httpx.ConnectError("provider unavailable"), "request failed"),
    ],
)
def test_create_embedding_maps_network_failures_to_safe_errors(
    monkeypatch: pytest.MonkeyPatch,
    post_error: httpx.RequestError,
    expected_message: str,
) -> None:
    secret_key = "private-shopaikey-key"

    monkeypatch.setattr(shopaikey_service, "get_settings", lambda: _settings(api_key=secret_key))
    monkeypatch.setattr(shopaikey_service.httpx, "post", Mock(side_effect=post_error))

    with pytest.raises(shopaikey_service.ShopAIKeyServiceError) as exc_info:
        shopaikey_service.create_embedding("text")

    message = str(exc_info.value)
    assert expected_message in message
    assert secret_key not in message
    assert "provider unavailable" not in message


def test_create_embedding_maps_non_success_status_to_safe_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret_key = "private-shopaikey-key"
    request = httpx.Request("POST", "https://api.shopaikey.test/v1/embeddings")
    response = httpx.Response(
        status_code=500,
        content=b'{"error":"very long provider body with details"}',
        request=request,
    )

    monkeypatch.setattr(shopaikey_service, "get_settings", lambda: _settings(api_key=secret_key))
    monkeypatch.setattr(
        shopaikey_service.httpx,
        "post",
        Mock(return_value=response),
    )

    with pytest.raises(shopaikey_service.ShopAIKeyServiceError) as exc_info:
        shopaikey_service.create_embedding("text")

    message = str(exc_info.value)
    assert "status 500" in message
    assert secret_key not in message
    assert "very long provider body" not in message


def test_create_embedding_maps_malformed_json_to_clear_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = Mock()
    response.raise_for_status = Mock()
    response.json.side_effect = ValueError("raw invalid json")

    monkeypatch.setattr(shopaikey_service, "get_settings", lambda: _settings())
    monkeypatch.setattr(shopaikey_service.httpx, "post", Mock(return_value=response))

    with pytest.raises(shopaikey_service.ShopAIKeyServiceError) as exc_info:
        shopaikey_service.create_embedding("text")

    message = str(exc_info.value)
    assert "malformed JSON" in message
    assert "raw invalid json" not in message


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"data": []},
        {"data": [{"embedding": None}]},
        {"data": [{"embedding": ["not-a-number"]}]},
    ],
)
def test_create_embedding_maps_missing_or_invalid_vector_to_clear_error(
    monkeypatch: pytest.MonkeyPatch,
    payload: dict[str, Any],
) -> None:
    response = Mock()
    response.raise_for_status = Mock()
    response.json.return_value = payload

    monkeypatch.setattr(shopaikey_service, "get_settings", lambda: _settings())
    monkeypatch.setattr(shopaikey_service.httpx, "post", Mock(return_value=response))

    with pytest.raises(shopaikey_service.ShopAIKeyServiceError) as exc_info:
        shopaikey_service.create_embedding("text")

    assert "embedding vector" in str(exc_info.value)


def test_create_embedding_maps_missing_config_to_clear_backend_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        shopaikey_service,
        "get_settings",
        lambda: SimpleNamespace(
            require_shopaikey_settings=Mock(
                side_effect=RuntimeError(
                    "Missing SHOPAIKEY_API_KEY. Configure ShopAIKey settings in the backend environment before using embedding services."
                )
            )
        ),
    )

    with pytest.raises(shopaikey_service.ShopAIKeyServiceError) as exc_info:
        shopaikey_service.create_embedding("text")

    message = str(exc_info.value)
    assert "Missing SHOPAIKEY_API_KEY" in message
    assert "backend environment" in message


@pytest.mark.parametrize(
    ("base_url", "expected_url"),
    [
        (
            "https://api.shopaikey.test/v1",
            "https://api.shopaikey.test/v1/chat/completions",
        ),
        (
            "https://api.shopaikey.test/v1/",
            "https://api.shopaikey.test/v1/chat/completions",
        ),
    ],
)
def test_chat_completion_posts_openai_style_request_with_configured_values(
    monkeypatch: pytest.MonkeyPatch,
    base_url: str,
    expected_url: str,
) -> None:
    response = Mock()
    response.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": '{"entities":[],"relationships":[]}',
                },
            }
        ]
    }
    response.raise_for_status = Mock()
    post = Mock(return_value=response)
    messages = [{"role": "user", "content": "Extract graph entities."}]
    response_format = {"type": "json_object"}

    monkeypatch.setattr(
        shopaikey_service, "get_settings", lambda: _settings(base_url=base_url)
    )
    monkeypatch.setattr(shopaikey_service.httpx, "post", post)

    content = shopaikey_service.chat_completion(
        messages,
        response_format=response_format,
    )

    assert content == '{"entities":[],"relationships":[]}'
    post.assert_called_once_with(
        expected_url,
        headers={
            "Authorization": "Bearer private-shopaikey-key",
            "Content-Type": "application/json",
        },
        json={
            "model": "configured-chat-model",
            "messages": messages,
            "response_format": response_format,
        },
        timeout=shopaikey_service.CHAT_COMPLETION_REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status.assert_called_once_with()


def test_chat_completion_omits_response_format_when_not_provided(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = Mock()
    response.json.return_value = {"choices": [{"message": {"content": "{}"}}]}
    response.raise_for_status = Mock()
    post = Mock(return_value=response)

    monkeypatch.setattr(shopaikey_service, "get_settings", lambda: _settings())
    monkeypatch.setattr(shopaikey_service.httpx, "post", post)

    shopaikey_service.chat_completion([{"role": "user", "content": "Extract."}])

    assert "response_format" not in post.call_args.kwargs["json"]


def test_chat_completion_uses_configured_chat_model_without_hardcoded_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = Mock()
    response.json.return_value = {"choices": [{"message": {"content": "{}"}}]}
    response.raise_for_status = Mock()
    post = Mock(return_value=response)

    monkeypatch.setattr(
        shopaikey_service,
        "get_settings",
        lambda: _settings(chat_model="different-chat-model"),
    )
    monkeypatch.setattr(shopaikey_service.httpx, "post", post)

    shopaikey_service.chat_completion([{"role": "user", "content": "Extract."}])

    assert post.call_args.kwargs["json"]["model"] == "different-chat-model"


@pytest.mark.parametrize(
    ("post_error", "expected_message"),
    [
        (httpx.TimeoutException("timed out"), "timed out"),
        (httpx.ConnectError("provider unavailable"), "request failed"),
    ],
)
def test_chat_completion_maps_network_failures_to_safe_errors(
    monkeypatch: pytest.MonkeyPatch,
    post_error: httpx.RequestError,
    expected_message: str,
) -> None:
    secret_key = "private-shopaikey-key"

    monkeypatch.setattr(shopaikey_service, "get_settings", lambda: _settings(api_key=secret_key))
    monkeypatch.setattr(shopaikey_service.httpx, "post", Mock(side_effect=post_error))

    with pytest.raises(shopaikey_service.ShopAIKeyServiceError) as exc_info:
        shopaikey_service.chat_completion([{"role": "user", "content": "Extract."}])

    message = str(exc_info.value)
    assert expected_message in message
    assert secret_key not in message
    assert "provider unavailable" not in message


def test_chat_completion_maps_non_success_status_to_safe_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret_key = "private-shopaikey-key"
    request = httpx.Request("POST", "https://api.shopaikey.test/v1/chat/completions")
    response = httpx.Response(
        status_code=502,
        content=b'{"error":"provider secret details"}',
        request=request,
    )

    monkeypatch.setattr(shopaikey_service, "get_settings", lambda: _settings(api_key=secret_key))
    monkeypatch.setattr(shopaikey_service.httpx, "post", Mock(return_value=response))

    with pytest.raises(shopaikey_service.ShopAIKeyServiceError) as exc_info:
        shopaikey_service.chat_completion([{"role": "user", "content": "Extract."}])

    message = str(exc_info.value)
    assert "status 502" in message
    assert secret_key not in message
    assert "provider secret details" not in message


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"choices": []},
        {"choices": [{"message": {}}]},
        {"choices": [{"message": {"content": None}}]},
    ],
)
def test_chat_completion_maps_missing_or_invalid_content_to_clear_error(
    monkeypatch: pytest.MonkeyPatch,
    payload: dict[str, Any],
) -> None:
    response = Mock()
    response.raise_for_status = Mock()
    response.json.return_value = payload

    monkeypatch.setattr(shopaikey_service, "get_settings", lambda: _settings())
    monkeypatch.setattr(shopaikey_service.httpx, "post", Mock(return_value=response))

    with pytest.raises(shopaikey_service.ShopAIKeyServiceError) as exc_info:
        shopaikey_service.chat_completion([{"role": "user", "content": "Extract."}])

    assert "chat completion content" in str(exc_info.value)


def test_chat_completion_maps_malformed_json_to_clear_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = Mock()
    response.raise_for_status = Mock()
    response.json.side_effect = ValueError("raw invalid json")

    monkeypatch.setattr(shopaikey_service, "get_settings", lambda: _settings())
    monkeypatch.setattr(shopaikey_service.httpx, "post", Mock(return_value=response))

    with pytest.raises(shopaikey_service.ShopAIKeyServiceError) as exc_info:
        shopaikey_service.chat_completion([{"role": "user", "content": "Extract."}])

    message = str(exc_info.value)
    assert "malformed JSON" in message
    assert "raw invalid json" not in message


def test_chat_completion_maps_missing_config_to_clear_backend_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        shopaikey_service,
        "get_settings",
        lambda: SimpleNamespace(
            require_shopaikey_chat_settings=Mock(
                side_effect=RuntimeError(
                    "Missing SHOPAIKEY_CHAT_MODEL. Configure ShopAIKey settings in the backend environment before using chat completion services."
                )
            )
        ),
    )

    with pytest.raises(shopaikey_service.ShopAIKeyServiceError) as exc_info:
        shopaikey_service.chat_completion([{"role": "user", "content": "Extract."}])

    message = str(exc_info.value)
    assert "Missing SHOPAIKEY_CHAT_MODEL" in message
    assert "backend environment" in message
