from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.core.config import Settings
from app.graphs.query_prompts import build_grounding_messages
from app.services.grounding import (
    GroundingProviderError,
    cited_evidence_from_sources,
    verify_answer_grounding,
)


def _settings() -> Settings:
    return Settings(_env_file=None, SHOPAIKEY_API_KEY="shopai-key")


def _chunk() -> dict[str, object]:
    return {
        "document_id": "doc-a",
        "chunk_id": "chunk-a",
        "file_name": "alpha.pdf",
        "chunk_index": 0,
        "content": "Alpha pricing is based on usage tiers.",
    }


def test_cited_evidence_uses_only_exact_cited_chunk_texts():
    evidence = cited_evidence_from_sources(
        context_chunks=[
            {**_chunk(), "citation_key": "S1"},
            {
                "document_id": "doc-a",
                "chunk_id": "chunk-b",
                "file_name": "alpha.pdf",
                "chunk_index": 1,
                "content": "Uncited renewal terms.",
                "citation_key": "S2",
            },
        ],
        cited_keys=["S1"],
    )

    assert evidence == [
        {
            "citation_key": "S1",
            "chunk_id": "chunk-a",
            "text": "Alpha pricing is based on usage tiers.",
        }
    ]


def test_grounding_prompt_requests_strict_json_contract():
    messages = build_grounding_messages(
        answer="Pricing is usage based [S1].",
        evidence=[{"citation_key": "S1", "chunk_id": "chunk-a", "text": "Pricing is usage based."}],
    )

    joined = "\n".join(str(message["content"]) for message in messages)

    assert "JSON only" in joined
    assert "grounded" in joined
    assert "score" in joined
    assert "unsupported_claims" in joined
    assert "missing_citations" in joined
    assert "Pricing is usage based." in joined


def test_verify_answer_grounding_parses_valid_strict_json():
    fake_client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(
                create=lambda **kwargs: SimpleNamespace(
                    choices=[
                        SimpleNamespace(
                            message=SimpleNamespace(
                                content='{"grounded": true, "score": 0.95, "unsupported_claims": [], "missing_citations": []}'
                            )
                        )
                    ]
                )
            )
        )
    )

    result = verify_answer_grounding(
        "Pricing is usage based [S1].",
        evidence=[{"citation_key": "S1", "chunk_id": "chunk-a", "text": "Pricing is usage based."}],
        settings=_settings(),
        shopaikey_client=fake_client,
    )

    assert result.grounded is True
    assert result.score == 0.95
    assert result.unsupported_claims == []
    assert result.missing_citations == []


def test_verify_answer_grounding_parses_markdown_fenced_json():
    fake_client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(
                create=lambda **kwargs: SimpleNamespace(
                    choices=[
                        SimpleNamespace(
                            message=SimpleNamespace(
                                content='```json\n{"grounded": true, "score": 0.95, "unsupported_claims": [], "missing_citations": []}\n```'
                            )
                        )
                    ]
                )
            )
        )
    )

    result = verify_answer_grounding(
        "Pricing is usage based [S1].",
        evidence=[{"citation_key": "S1", "chunk_id": "chunk-a", "text": "Pricing is usage based."}],
        settings=_settings(),
        shopaikey_client=fake_client,
    )

    assert result.grounded is True
    assert result.score == 0.95
    assert result.unsupported_claims == []
    assert result.missing_citations == []


def test_verify_answer_grounding_requests_json_response_format():
    captured_kwargs: dict[str, object] = {}

    def _create(**kwargs):
        captured_kwargs.update(kwargs)
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content='{"grounded": true, "score": 0.95, "unsupported_claims": [], "missing_citations": []}'
                    )
                )
            ]
        )

    fake_client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=_create))
    )

    verify_answer_grounding(
        "Pricing is usage based [S1].",
        evidence=[{"citation_key": "S1", "chunk_id": "chunk-a", "text": "Pricing is usage based."}],
        settings=_settings(),
        shopaikey_client=fake_client,
    )

    assert captured_kwargs["response_format"] == {"type": "json_object"}


def test_verify_answer_grounding_provider_failure_is_explicit_verification_failure():
    fake_client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(
                create=lambda **kwargs: (_ for _ in ()).throw(RuntimeError("provider down"))
            )
        )
    )

    with pytest.raises(GroundingProviderError):
        verify_answer_grounding(
            "Pricing is usage based [S1].",
            evidence=[
                {
                    "citation_key": "S1",
                    "chunk_id": "chunk-a",
                    "text": "Pricing is usage based.",
                }
            ],
            settings=_settings(),
            shopaikey_client=fake_client,
        )
