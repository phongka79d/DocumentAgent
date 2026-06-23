from __future__ import annotations

import json
from dataclasses import dataclass, field
from types import SimpleNamespace

import pytest

from app.core.config import Settings
from app.core.contracts import RetrievalStrategy
from app.models.schemas import RetrievalFilters
from app.services import query_planning


DOC_A = "11111111-1111-1111-1111-111111111111"
DOC_B = "22222222-2222-2222-2222-222222222222"


def _settings(
    *,
    enable_keyword_search: bool = True,
    max_subqueries: int = 4,
) -> Settings:
    return Settings(
        _env_file=None,
        SHOPAIKEY_API_KEY="shopai-key",
        SHOPAIKEY_BASE_URL="https://api.shopaikey.com/v1",
        SHOPAIKEY_INPUT_MODEL="gpt-5-mini",
        ENABLE_KEYWORD_SEARCH=enable_keyword_search,
        QUERY_MAX_SUBQUERIES=max_subqueries,
        QUERY_PLANNER_TEMPERATURE=0.0,
        QUERY_PLANNER_MAX_TOKENS=321,
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


@dataclass
class SequenceChatCompletionsEndpoint:
    responses: list[object]
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
        response = self.responses[min(len(self.calls) - 1, len(self.responses) - 1)]
        if isinstance(response, Exception):
            raise response
        return response


@dataclass
class SequenceShopAIKeyClient:
    responses: list[object]

    def __post_init__(self):
        self.chat = SimpleNamespace(
            completions=SequenceChatCompletionsEndpoint(self.responses)
        )


def _chat_response(payload: object) -> object:
    content = payload if isinstance(payload, str) else json.dumps(payload)
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
    )


def test_plan_query_normalizes_complex_plan_and_uses_prompt_based_json():
    settings = _settings()
    client = FakeShopAIKeyClient(
        _chat_response(
            {
                "is_complex": True,
                "strategy": "hybrid",
                "subqueries": [
                    {"id": "first", "text": " Compare pricing "},
                    {"id": "blank", "text": "   "},
                    {"id": "duplicate", "text": "Compare pricing"},
                    {"id": "second", "text": "Compare limits"},
                ],
                "inferred_filters": {
                    "mime_types": [" application/pdf ", ""],
                    "heading": " Inferred heading ",
                    "section_path": ["Plans", ""],
                    "page_start": 1,
                    "page_end": 9,
                },
                "needs_relations": True,
            }
        )
    )

    plan = query_planning.plan_query(
        " Compare pricing and limits ",
        [DOC_A, DOC_B],
        {"heading": " Explicit heading ", "page_start": 3},
        settings=settings,
        shopaikey_client=client,
    )

    assert plan.strategy is RetrievalStrategy.HYBRID
    assert plan.is_complex is True
    assert [(item.id, item.text) for item in plan.subqueries] == [
        ("first", "Compare pricing"),
        ("second", "Compare limits"),
    ]
    assert plan.inferred_filters.model_dump(mode="json") == {
        "mime_types": ["application/pdf"],
        "heading": "Explicit heading",
        "section_path": ["Plans"],
        "page_start": 3,
        "page_end": 9,
    }
    assert plan.needs_relations is True

    chat_call = client.chat.completions.calls[0]
    assert chat_call["model"] == settings.SHOPAIKEY_INPUT_MODEL
    assert chat_call["temperature"] == settings.QUERY_PLANNER_TEMPERATURE
    assert chat_call["max_tokens"] == settings.QUERY_PLANNER_MAX_TOKENS
    assert "response_format" not in chat_call["kwargs"]
    system_prompt = chat_call["messages"][0]["content"]
    assert "For compound questions" in system_prompt
    assert "For exact identifiers or codes" in system_prompt
    user_prompt = chat_call["messages"][1]["content"]
    assert f'"document_ids": ["{DOC_A}", "{DOC_B}"]' in user_prompt
    assert "Compare pricing and limits" in user_prompt


def test_plan_query_caps_subqueries_and_preserves_retained_ids():
    settings = _settings(max_subqueries=2)
    client = FakeShopAIKeyClient(
        _chat_response(
            {
                "is_complex": True,
                "strategy": "semantic",
                "subqueries": [
                    {"id": "stable-a", "text": "Alpha"},
                    {"id": "stable-b", "text": "Beta"},
                    {"id": "stable-c", "text": "Gamma"},
                ],
                "inferred_filters": {},
                "needs_relations": False,
            }
        )
    )

    plan = query_planning.plan_query(
        "Alpha beta gamma",
        [],
        None,
        settings=settings,
        shopaikey_client=client,
    )

    assert [(item.id, item.text) for item in plan.subqueries] == [
        ("stable-a", "Alpha"),
        ("stable-b", "Beta"),
    ]


def test_plan_query_restores_original_question_when_normalized_subqueries_are_empty():
    settings = _settings()
    client = FakeShopAIKeyClient(
        _chat_response(
            {
                "is_complex": False,
                "strategy": "metadata",
                "subqueries": [
                    {"id": "blank-a", "text": ""},
                    {"id": "blank-b", "text": "   "},
                ],
                "inferred_filters": {},
                "needs_relations": False,
            }
        )
    )

    plan = query_planning.plan_query(
        " What is the renewal date? ",
        [],
        None,
        settings=settings,
        shopaikey_client=client,
    )

    assert plan.strategy is RetrievalStrategy.METADATA
    assert [(item.id, item.text) for item in plan.subqueries] == [
        ("q1", "What is the renewal date?")
    ]


def test_plan_query_explicit_filters_override_field_by_field_and_preserve_scope():
    settings = _settings()
    explicit_filters = RetrievalFilters(
        mime_types=["text/plain"],
        section_path=[],
        page_end=4,
    )
    client = FakeShopAIKeyClient(
        _chat_response(
            {
                "is_complex": False,
                "strategy": "keyword",
                "subqueries": [{"id": "q7", "text": "renewal"}],
                "inferred_filters": {
                    "mime_types": ["application/pdf"],
                    "heading": "Renewals",
                    "section_path": ["Pricing"],
                    "page_start": 2,
                    "page_end": 8,
                },
                "needs_relations": False,
            }
        )
    )

    plan = query_planning.plan_query(
        "renewal",
        [DOC_A],
        explicit_filters,
        settings=settings,
        shopaikey_client=client,
    )

    assert plan.inferred_filters.model_dump(mode="json") == {
        "mime_types": ["text/plain"],
        "heading": "Renewals",
        "section_path": [],
        "page_start": 2,
        "page_end": 4,
    }
    user_prompt = client.chat.completions.calls[0]["messages"][1]["content"]
    assert f'"document_ids": ["{DOC_A}"]' in user_prompt
    assert DOC_B not in user_prompt


@pytest.mark.parametrize(
    "response",
    [
        TimeoutError("planner timed out"),
        RuntimeError("provider unavailable"),
        "not json",
        {
            "is_complex": True,
            "strategy": "vector",
            "subqueries": [{"id": "q1", "text": "bad strategy"}],
            "inferred_filters": {},
            "needs_relations": False,
        },
        {
            "is_complex": True,
            "strategy": "hybrid",
            "subqueries": [{"id": "q1", "text": "bad filters"}],
            "inferred_filters": {"page_start": 5, "page_end": 2},
            "needs_relations": False,
        },
    ],
)
def test_plan_query_falls_back_to_one_hybrid_subquery_for_planner_failures(response):
    settings = _settings(enable_keyword_search=True)
    client_response = response if isinstance(response, Exception) else _chat_response(response)
    client = FakeShopAIKeyClient(client_response)

    plan = query_planning.plan_query(
        " What changed in the contract? ",
        [DOC_A],
        None,
        settings=settings,
        shopaikey_client=client,
    )

    assert plan.strategy is RetrievalStrategy.HYBRID
    assert plan.is_complex is False
    assert [(item.id, item.text) for item in plan.subqueries] == [
        ("q1", "What changed in the contract?")
    ]
    assert plan.inferred_filters.model_dump(mode="json") == {
        "mime_types": [],
        "heading": None,
        "section_path": [],
        "page_start": None,
        "page_end": None,
    }
    assert plan.needs_relations is False


def test_plan_query_accepts_model_json_wrapped_in_text():
    settings = _settings(enable_keyword_search=True, max_subqueries=3)
    client = FakeShopAIKeyClient(
        _chat_response(
            '```json\n'
            '{"is_complex":true,"strategy":"hybrid",'
            '"subqueries":[{"id":"model-a","text":"leave carryover"},'
            '{"id":"model-b","text":"pricing cancellation"}],'
            '"inferred_filters":{"mime_types":[],"heading":null,'
            '"section_path":[],"page_start":null,"page_end":null},'
            '"needs_relations":false}'
            "\n```"
        )
    )

    plan = query_planning.plan_query(
        "Compare leave carryover and pricing cancellation.",
        [],
        None,
        settings=settings,
        shopaikey_client=client,
    )

    assert plan.strategy is RetrievalStrategy.HYBRID
    assert plan.is_complex is True
    assert [(item.id, item.text) for item in plan.subqueries] == [
        ("model-a", "leave carryover"),
        ("model-b", "pricing cancellation"),
    ]
    assert plan.needs_relations is False


def test_plan_query_empty_model_response_falls_back_without_local_decomposition():
    settings = _settings(enable_keyword_search=True, max_subqueries=3)
    client = FakeShopAIKeyClient(_chat_response(""))

    plan = query_planning.plan_query(
        "Compare leave carryover and pricing cancellation.",
        [],
        None,
        settings=settings,
        shopaikey_client=client,
    )

    assert plan.strategy is RetrievalStrategy.HYBRID
    assert plan.is_complex is False
    assert [(item.id, item.text) for item in plan.subqueries] == [
        ("q1", "Compare leave carryover and pricing cancellation.")
    ]


def test_plan_query_retries_transient_planner_failures_before_using_response():
    settings = _settings(enable_keyword_search=True).model_copy(
        update={
            "WORKFLOW_MAX_ATTEMPTS": 3,
            "WORKFLOW_RETRY_BASE_DELAY_SECONDS": 0.0,
            "WORKFLOW_RETRY_MAX_DELAY_SECONDS": 0.0,
        }
    )
    client = SequenceShopAIKeyClient(
        [
            TimeoutError("planner timed out"),
            ConnectionError("planner connection failed"),
            _chat_response(
                {
                    "is_complex": False,
                    "strategy": "keyword",
                    "subqueries": [{"id": "q7", "text": "renewal terms"}],
                    "inferred_filters": {},
                    "needs_relations": False,
                }
            ),
        ]
    )

    plan = query_planning.plan_query(
        "renewal",
        [DOC_A],
        None,
        settings=settings,
        shopaikey_client=client,
    )

    assert plan.strategy is RetrievalStrategy.KEYWORD
    assert [(item.id, item.text) for item in plan.subqueries] == [
        ("q7", "renewal terms")
    ]
    assert len(client.chat.completions.calls) == 3


def test_plan_query_non_retryable_contract_failure_runs_once_before_fallback():
    settings = _settings(enable_keyword_search=True).model_copy(
        update={
            "WORKFLOW_MAX_ATTEMPTS": 3,
            "WORKFLOW_RETRY_BASE_DELAY_SECONDS": 0.0,
            "WORKFLOW_RETRY_MAX_DELAY_SECONDS": 0.0,
        }
    )
    client = SequenceShopAIKeyClient([_chat_response("not json")])

    plan = query_planning.plan_query(
        "renewal",
        [DOC_A],
        None,
        settings=settings,
        shopaikey_client=client,
    )

    assert plan.strategy is RetrievalStrategy.HYBRID
    assert [(item.id, item.text) for item in plan.subqueries] == [("q1", "renewal")]
    assert len(client.chat.completions.calls) == 1


def test_plan_query_falls_back_when_planner_attempts_to_return_document_scope():
    settings = _settings(enable_keyword_search=True)
    client = FakeShopAIKeyClient(
        _chat_response(
            {
                "is_complex": False,
                "strategy": "keyword",
                "subqueries": [{"id": "planner-id", "text": "planner widened scope"}],
                "inferred_filters": {},
                "needs_relations": False,
                "document_ids": [DOC_B],
            }
        )
    )

    plan = query_planning.plan_query(
        "renewal",
        [DOC_A],
        None,
        settings=settings,
        shopaikey_client=client,
    )

    assert plan.strategy is RetrievalStrategy.HYBRID
    assert [(item.id, item.text) for item in plan.subqueries] == [
        ("q1", "renewal")
    ]
    user_prompt = client.chat.completions.calls[0]["messages"][1]["content"]
    assert f'"document_ids": ["{DOC_A}"]' in user_prompt
    assert DOC_B not in user_prompt


def test_plan_query_fallback_uses_semantic_when_keyword_search_is_disabled():
    settings = _settings(enable_keyword_search=False)
    client = FakeShopAIKeyClient(_chat_response("not json"))

    plan = query_planning.plan_query(
        "What changed?",
        [],
        None,
        settings=settings,
        shopaikey_client=client,
    )

    assert plan.strategy is RetrievalStrategy.SEMANTIC
    assert [(item.id, item.text) for item in plan.subqueries] == [
        ("q1", "What changed?")
    ]
