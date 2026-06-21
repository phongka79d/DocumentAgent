from __future__ import annotations

from uuid import UUID

import pytest

from app.services import relations


LOW_ID = UUID("11111111-1111-1111-1111-111111111111")
HIGH_ID = UUID("99999999-9999-9999-9999-999999999999")
CHUNK_ID = UUID("22222222-2222-2222-2222-222222222222")


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


def test_delete_document_relations_targets_both_pair_directions():
    client = FakeClient([])

    relations.delete_document_relations(HIGH_ID, supabase_client=client)

    assert client.calls[0].operation == "delete"
    assert str(HIGH_ID) in client.calls[0].or_filter

