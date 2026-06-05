import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services import shopaikey_service


def _settings(
    *,
    api_key: str = "private-shopaikey-key",
    base_url: str = "https://api.shopaikey.test/v1/",
    embedding_model: str = "configured-embedding-model",
) -> SimpleNamespace:
    return SimpleNamespace(
        require_shopaikey_settings=lambda: {
            "api_key": api_key,
            "base_url": base_url,
            "embedding_model": embedding_model,
        }
    )


def test_create_embedding_posts_openai_style_request_with_configured_values(
    monkeypatch: pytest.MonkeyPatch,
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

    monkeypatch.setattr(shopaikey_service, "get_settings", lambda: _settings())
    monkeypatch.setattr(shopaikey_service.httpx, "post", post)

    vector = shopaikey_service.create_embedding("chunk text")

    assert vector == [0.1, 2.0, -0.3]
    post.assert_called_once_with(
        "https://api.shopaikey.test/v1/embeddings",
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
