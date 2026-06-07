import json
import sys
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services import entity_extraction_service, supabase_service


CHUNK_ID = "11111111-1111-1111-1111-111111111111"


def _chunk(content: str = "The probation period starts on January 1, 2026.") -> dict[str, str]:
    return {
        "id": CHUNK_ID,
        "content": content,
        "section_title": "Employment Terms",
    }


def _set_graph_extraction_enabled(
    monkeypatch: pytest.MonkeyPatch,
    enabled: bool,
) -> None:
    monkeypatch.setattr(
        entity_extraction_service,
        "get_settings",
        lambda: SimpleNamespace(graph_extraction_enabled=enabled),
    )


def test_extract_entities_for_chunk_returns_validated_drafts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_graph_extraction_enabled(monkeypatch, True)
    payload = {
        "entities": [
            {
                "name": "Probation Period",
                "type": "contract term",
                "description": "Duration before official employment consideration",
            },
            {
                "name": "January 1, 2026",
                "type": "date",
            },
        ],
        "relationships": [
            {
                "source_entity": "Probation Period",
                "target_entity": "January 1, 2026",
                "relationship_type": "starts_at",
                "weight": 0.8,
                "description": "Probation period starts on this date",
            }
        ],
    }

    monkeypatch.setattr(
        entity_extraction_service.shopaikey_service,
        "chat_completion",
        lambda messages, response_format=None: json.dumps(payload),
    )

    result = entity_extraction_service.extract_entities_for_chunk(_chunk())

    assert [entity.entity_name for entity in result.entities] == [
        "Probation Period",
        "January 1, 2026",
    ]
    assert all(entity.chunk_id == UUID(CHUNK_ID) for entity in result.entities)
    assert result.relationships[0].source_id == "Probation Period"
    assert result.relationships[0].target_id == "January 1, 2026"
    assert result.relationships[0].relationship_type == "starts_at"
    assert result.relationships[0].weight == 0.8


def test_extract_entities_for_chunk_uses_strict_json_extraction_prompt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_graph_extraction_enabled(monkeypatch, True)
    captured_messages = []
    captured_response_format = None

    def fake_chat_completion(messages, response_format=None):
        nonlocal captured_messages, captured_response_format
        captured_messages = messages
        captured_response_format = response_format
        return '{"entities":[],"relationships":[]}'

    monkeypatch.setattr(
        entity_extraction_service.shopaikey_service,
        "chat_completion",
        fake_chat_completion,
    )

    entity_extraction_service.extract_entities_for_chunk(_chunk("Salary starts after probation."))

    prompt_text = "\n".join(message["content"] for message in captured_messages)
    assert captured_response_format == {"type": "json_object"}
    assert "strict JSON" in prompt_text
    assert '"entities"' in prompt_text
    assert '"relationships"' in prompt_text
    assert "Salary starts after probation." in prompt_text
    assert "answer the user's question" not in prompt_text.lower()
    assert "answer user questions" not in prompt_text.lower()


@pytest.mark.parametrize(
    "payload",
    [
        "{not-json",
        json.dumps({"entities": [{"name": "Mystery", "type": "unsupported"}], "relationships": []}),
        json.dumps(
            {
                "entities": [{"name": "Probation Period", "type": "contract term"}],
                "relationships": [
                    {
                        "source_entity": "Probation Period",
                        "target_entity": "Salary",
                        "relationship_type": "starts_at",
                        "weight": 2.0,
                    }
                ],
            }
        ),
        json.dumps(
            {
                "entities": [{"name": "Probation Period", "type": "contract term"}],
                "relationships": [
                    {
                        "source_entity": "Probation Period",
                        "target_entity": "Salary",
                        "relationship_type": "unsupported",
                        "weight": 0.5,
                    }
                ],
            }
        ),
        json.dumps(
            {
                "entities": [{"name": "Probation Period", "type": "contract term"}],
                "relationships": [
                    {
                        "source_entity": "Probation Period",
                        "relationship_type": "starts_at",
                        "weight": 0.5,
                    }
                ],
            }
        ),
        json.dumps({"entities": [{"type": "date"}], "relationships": []}),
    ],
)
def test_extract_entities_for_chunk_rejects_invalid_llm_output(
    monkeypatch: pytest.MonkeyPatch,
    payload: str,
) -> None:
    _set_graph_extraction_enabled(monkeypatch, True)
    monkeypatch.setattr(
        entity_extraction_service.shopaikey_service,
        "chat_completion",
        lambda messages, response_format=None: payload,
    )

    with pytest.raises(entity_extraction_service.EntityExtractionError):
        entity_extraction_service.extract_entities_for_chunk(_chunk())


def test_malformed_llm_output_does_not_insert_graph_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_graph_extraction_enabled(monkeypatch, True)
    monkeypatch.setattr(
        entity_extraction_service.shopaikey_service,
        "chat_completion",
        lambda messages, response_format=None: json.dumps(
            {
                "entities": [{"name": "Mystery", "type": "unsupported"}],
                "relationships": [
                    {
                        "source_entity": "Mystery",
                        "target_entity": "Salary",
                        "relationship_type": "unsupported",
                        "weight": 1.5,
                    }
                ],
            }
        ),
    )
    monkeypatch.setattr(
        supabase_service,
        "insert_document_entities",
        lambda *args, **kwargs: pytest.fail("malformed entities must not be inserted"),
    )
    monkeypatch.setattr(
        supabase_service,
        "insert_document_relationships",
        lambda *args, **kwargs: pytest.fail("malformed relationships must not be inserted"),
    )

    with pytest.raises(entity_extraction_service.EntityExtractionError):
        entity_extraction_service.extract_entities_for_chunk(_chunk())


def test_extract_entities_for_chunk_returns_deterministic_fallback_when_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_graph_extraction_enabled(monkeypatch, False)
    monkeypatch.setattr(
        entity_extraction_service.shopaikey_service,
        "chat_completion",
        lambda messages, response_format=None: pytest.fail("fallback must not call ShopAIKey"),
    )

    result = entity_extraction_service.extract_entities_for_chunk(
        _chunk(
            "Acme Policy starts on January 1, 2026. "
            "Acme Policy applies until February 15, 2026. "
            "Salary Plan references Acme Policy."
        )
    )

    assert [(entity.entity_name, entity.entity_type) for entity in result.entities] == [
        ("January 1, 2026", "date"),
        ("February 15, 2026", "date"),
        ("Acme Policy", "other"),
    ]
    assert all(entity.chunk_id == UUID(CHUNK_ID) for entity in result.entities)
    assert result.relationships == []


def test_invalid_llm_json_raises_chunk_scoped_controlled_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_graph_extraction_enabled(monkeypatch, True)
    monkeypatch.setattr(
        entity_extraction_service.shopaikey_service,
        "chat_completion",
        lambda messages, response_format=None: "{not-json",
    )

    with pytest.raises(entity_extraction_service.EntityExtractionError) as exc_info:
        entity_extraction_service.extract_entities_for_chunk(_chunk())

    assert "malformed JSON" in str(exc_info.value)
    assert exc_info.value.chunk_id == UUID(CHUNK_ID)


def test_shopaikey_failure_raises_chunk_scoped_safe_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_graph_extraction_enabled(monkeypatch, True)

    def raise_provider_error(messages, response_format=None):
        raise entity_extraction_service.shopaikey_service.ShopAIKeyServiceError(
            "raw provider timeout"
        )

    monkeypatch.setattr(
        entity_extraction_service.shopaikey_service,
        "chat_completion",
        raise_provider_error,
    )

    with pytest.raises(entity_extraction_service.EntityExtractionError) as exc_info:
        entity_extraction_service.extract_entities_for_chunk(_chunk())

    assert str(exc_info.value) == (
        f"ShopAIKey entity extraction failed for chunk {CHUNK_ID}."
    )
    assert exc_info.value.chunk_id == UUID(CHUNK_ID)
