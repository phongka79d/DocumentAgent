from __future__ import annotations

import json
from types import SimpleNamespace
from uuid import UUID

import pytest

from app.core.config import Settings
from app.services import relations


LOW_ID = UUID("11111111-1111-1111-1111-111111111111")
HIGH_ID = UUID("99999999-9999-9999-9999-999999999999")
CHUNK_ID = UUID("22222222-2222-2222-2222-222222222222")
SECOND_CHUNK_ID = UUID("33333333-3333-3333-3333-333333333333")
THIRD_ID = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")


class FakeResponse:
    def __init__(self, data=None):
        self.data = data


class FakeQuery:
    def __init__(self, client, table_name):
        self.client = client
        self.table_name = table_name
        self.operation = "select"
        self.payload = None
        self.filters = []
        self.or_filter = None

    def select(self, *_args):
        self.operation = "select"
        return self

    def insert(self, payload):
        self.operation = "insert"
        self.payload = payload
        return self

    def delete(self):
        self.operation = "delete"
        return self

    def eq(self, field, value):
        self.filters.append((field, value))
        return self

    def or_(self, expression):
        self.or_filter = expression
        return self

    def execute(self):
        self.client.calls.append(self)
        return FakeResponse(self.client.responses.pop(0) if self.client.responses else [])


class FakeClient:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def table(self, table_name):
        return FakeQuery(self, table_name)


class FakeEmbeddingEndpoint:
    def __init__(self):
        self.calls = []

    def create(self, *, model, input):
        self.calls.append((model, list(input)))
        return SimpleNamespace(data=[SimpleNamespace(embedding=[0.1, 0.2, 0.3])])


class FakeChatCompletions:
    def __init__(self, content):
        self.content = content
        self.calls = []

    def create(self, **payload):
        self.calls.append(payload)
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content=self.content),
                )
            ]
        )


class FakeShopAIKeyClient:
    def __init__(self, content):
        self.embeddings = FakeEmbeddingEndpoint()
        self.chat = SimpleNamespace(completions=FakeChatCompletions(content))


class FakeQdrantClient:
    def __init__(self, points):
        self.points = points
        self.calls = []

    def query_points(self, **payload):
        self.calls.append(payload)
        return SimpleNamespace(points=self.points)


def _point(*, document_id, chunk_id, score):
    return SimpleNamespace(
        id=str(chunk_id),
        score=score,
        payload={
            "document_id": str(document_id),
            "chunk_id": str(chunk_id),
            "file_name": f"{document_id}.pdf",
        },
    )


def _settings(max_related=2, enabled=True):
    return Settings(
        _env_file=None,
        ENABLE_RELATION_RETRIEVAL=enabled,
        RELATION_MAX_RELATED_DOCUMENTS=max_related,
        QDRANT_COLLECTION="document_chunks_v1",
        SHOPAIKEY_EMBEDDING_MODEL="embedding-model",
        SHOPAIKEY_CHAT_MODEL="chat-model",
    )


def _relation(**overrides):
    record = {
        "source_document_id": HIGH_ID,
        "target_document_id": LOW_ID,
        "relation_type": "supports",
        "description": "  Evidence agrees.  ",
        "evidence_chunk_ids": [CHUNK_ID],
        "confidence": 0.8,
        "model": "  relation-model  ",
    }
    record.update(overrides)
    return record


def test_create_relation_stores_canonical_pair_and_normalized_values():
    client = FakeClient([])

    result = relations.create_relation(**_relation(), supabase_client=client)

    assert result == {
        "source_document_id": str(LOW_ID),
        "target_document_id": str(HIGH_ID),
        "relation_type": "supports",
        "description": "Evidence agrees.",
        "evidence_chunk_ids": [str(CHUNK_ID)],
        "confidence": 0.8,
        "model": "relation-model",
    }
    assert client.calls[0].payload == result


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"target_document_id": HIGH_ID}, "must be different"),
        ({"confidence": 1.01}, "between 0 and 1"),
        ({"relation_type": "related"}, "related"),
    ],
)
def test_create_relation_rejects_invalid_contract_values(overrides, message):
    with pytest.raises(ValueError, match=message):
        relations.create_relation(
            **_relation(**overrides), supabase_client=FakeClient([])
        )


def test_list_relations_returns_empty_and_orders_rows_deterministically():
    assert relations.list_relations(LOW_ID, supabase_client=FakeClient(None)) == []

    rows = [
        _relation(relation_type="supports"),
        _relation(relation_type="references"),
    ]
    result = relations.list_relations(LOW_ID, supabase_client=FakeClient(rows))
    assert [row["relation_type"] for row in result] == ["references", "supports"]
    assert all(row["source_document_id"] == str(LOW_ID) for row in result)


def test_replace_document_relations_deletes_both_directions_then_inserts():
    client = FakeClient([], [])

    result = relations.replace_document_relations(
        HIGH_ID, [_relation()], supabase_client=client
    )

    assert [call.operation for call in client.calls] == ["delete", "insert"]
    expected_id = str(HIGH_ID)
    assert client.calls[0].or_filter == (
        f"source_document_id.eq.{expected_id},target_document_id.eq.{expected_id}"
    )
    assert result[0]["source_document_id"] == str(LOW_ID)


def test_replace_document_relations_keeps_one_row_per_pair_and_type():
    client = FakeClient([], [])

    result = relations.replace_document_relations(
        HIGH_ID,
        [
            _relation(confidence=0.2, description="lower confidence"),
            _relation(confidence=0.9, description="higher confidence"),
            _relation(relation_type="references", description="different type"),
        ],
        supabase_client=client,
    )

    assert [row["relation_type"] for row in result] == ["references", "supports"]
    inserted = client.calls[1].payload
    assert len(inserted) == 2
    supports = [row for row in inserted if row["relation_type"] == "supports"]
    assert supports == [
        {
            "source_document_id": str(LOW_ID),
            "target_document_id": str(HIGH_ID),
            "relation_type": "supports",
            "description": "higher confidence",
            "evidence_chunk_ids": [str(CHUNK_ID)],
            "confidence": 0.9,
            "model": "relation-model",
        }
    ]


def test_delete_document_relations_targets_both_pair_directions():
    client = FakeClient([])

    relations.delete_document_relations(HIGH_ID, supabase_client=client)

    assert client.calls[0].operation == "delete"
    assert str(HIGH_ID) in client.calls[0].or_filter


def test_update_document_relations_bounds_ready_candidates_and_validates_model_json():
    model_payload = {
        "relations": [
            {
                "target_document_id": str(HIGH_ID),
                "relation_type": "supports",
                "description": "Summaries support the same finding.",
                "evidence_chunk_ids": [str(CHUNK_ID)],
                "confidence": 0.8,
            },
            {
                "target_document_id": str(THIRD_ID),
                "relation_type": "same_topic",
                "description": "Excluded by candidate cap.",
                "evidence_chunk_ids": [str(SECOND_CHUNK_ID)],
                "confidence": 0.7,
            },
            {
                "target_document_id": str(HIGH_ID),
                "relation_type": "unknown",
                "description": "Bad type.",
                "evidence_chunk_ids": [str(CHUNK_ID)],
                "confidence": 0.5,
            },
            {
                "target_document_id": str(HIGH_ID),
                "relation_type": "references",
                "description": "Bad evidence.",
                "evidence_chunk_ids": [str(UUID("44444444-4444-4444-4444-444444444444"))],
                "confidence": 0.5,
            },
        ]
    }
    shopaikey_client = FakeShopAIKeyClient(json.dumps(model_payload))
    qdrant_client = FakeQdrantClient(
        [
            _point(document_id=LOW_ID, chunk_id=UUID("55555555-5555-5555-5555-555555555555"), score=0.99),
            _point(document_id=HIGH_ID, chunk_id=CHUNK_ID, score=0.9),
            _point(document_id=HIGH_ID, chunk_id=SECOND_CHUNK_ID, score=0.8),
            _point(document_id=THIRD_ID, chunk_id=UUID("66666666-6666-6666-6666-666666666666"), score=0.7),
        ]
    )
    supabase_client = FakeClient(
        [{"id": str(HIGH_ID), "status": "ready"}],
        [],
        [],
    )

    result = relations.update_document_relations(
        LOW_ID,
        summary_records=[
            {
                "summary_type": "document",
                "content": "Source document summary",
                "source_chunk_ids": [str(UUID("55555555-5555-5555-5555-555555555555"))],
                "model": "summary-model",
            }
        ],
        settings=_settings(max_related=1),
        shopaikey_client=shopaikey_client,
        qdrant_client=qdrant_client,
        supabase_client=supabase_client,
    )

    assert result["status"] == "updated"
    assert result["candidate_document_count"] == 1
    assert result["accepted_relation_count"] == 1
    assert result["discarded_relation_count"] == 3
    assert qdrant_client.calls[0]["limit"] >= 1
    inserted = supabase_client.calls[-1].payload
    assert inserted == [
        {
            "source_document_id": str(LOW_ID),
            "target_document_id": str(HIGH_ID),
            "relation_type": "supports",
            "description": "Summaries support the same finding.",
            "evidence_chunk_ids": [str(CHUNK_ID)],
            "confidence": 0.8,
            "model": "chat-model",
        }
    ]


def test_update_document_relations_discards_invalid_json_without_failing_indexing():
    result = relations.update_document_relations(
        LOW_ID,
        summary_records=[{"summary_type": "document", "content": "Source summary"}],
        settings=_settings(),
        shopaikey_client=FakeShopAIKeyClient("not json"),
        qdrant_client=FakeQdrantClient(
            [_point(document_id=HIGH_ID, chunk_id=CHUNK_ID, score=0.9)]
        ),
        supabase_client=FakeClient([{"id": str(HIGH_ID), "status": "ready"}], []),
    )

    assert result["status"] == "updated"
    assert result["accepted_relation_count"] == 0
    assert result["discarded_relation_count"] == 1


def test_resolve_related_document_scope_is_one_hop_bounded_and_respects_allow_list():
    client = FakeClient(
        [
            _relation(source_document_id=LOW_ID, target_document_id=HIGH_ID),
            _relation(
                source_document_id=LOW_ID,
                target_document_id=THIRD_ID,
                relation_type="references",
            ),
        ],
        [
            _relation(source_document_id=LOW_ID, target_document_id=HIGH_ID),
            _relation(
                source_document_id=HIGH_ID,
                target_document_id=THIRD_ID,
                relation_type="same_topic",
            ),
        ],
    )

    result = relations.resolve_related_document_scope(
        [LOW_ID, HIGH_ID],
        settings=_settings(max_related=1),
        supabase_client=client,
    )

    assert result == [str(LOW_ID), str(HIGH_ID)]
    assert len(client.calls) == 2
    assert all(str(THIRD_ID) not in document_id for document_id in result)
