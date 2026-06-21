from __future__ import annotations

from pathlib import Path
from uuid import UUID

from app.core.contracts import SummaryType, TableName
from app.services import summaries


DOCUMENT_ID = UUID("11111111-1111-1111-1111-111111111111")
SUMMARY_ID = UUID("22222222-2222-2222-2222-222222222222")


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

    def execute(self):
        self.client.calls.append(self)
        return FakeResponse(self.client.responses.pop(0) if self.client.responses else [])


class FakeClient:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def table(self, table_name):
        return FakeQuery(self, table_name)


def test_list_summaries_returns_empty_for_empty_response():
    assert summaries.list_summaries(DOCUMENT_ID, supabase_client=FakeClient(None)) == []


def test_phase3_persistence_tables_are_shared_contracts():
    assert TableName.DOCUMENT_SUMMARIES == "document_summaries"
    assert TableName.DOCUMENT_RELATIONS == "document_relations"
    assert TableName.WORKFLOW_RUNS == "workflow_runs"


def test_create_summary_normalizes_uuid_enum_and_json_lists():
    client = FakeClient([])

    result = summaries.create_summary(
        document_id=DOCUMENT_ID,
        summary_type=SummaryType.SECTION,
        heading="  Overview  ",
        section_path=("Overview", "Scope"),
        content="  Compact summary.  ",
        source_chunk_ids=(SUMMARY_ID,),
        model="  summary-model  ",
        supabase_client=client,
    )

    assert result == {
        "document_id": str(DOCUMENT_ID),
        "summary_type": "section",
        "heading": "Overview",
        "section_path": ["Overview", "Scope"],
        "content": "Compact summary.",
        "source_chunk_ids": [str(SUMMARY_ID)],
        "model": "summary-model",
    }
    assert client.calls[0].payload == result


def test_list_summaries_orders_document_summary_before_sections():
    section_z = {
        "id": SUMMARY_ID,
        "document_id": DOCUMENT_ID,
        "summary_type": "section",
        "heading": "Zed",
        "section_path": ["Zed"],
        "content": "z",
        "source_chunk_ids": [],
        "model": "m",
    }
    document = {**section_z, "summary_type": "document", "section_path": []}
    section_a = {**section_z, "heading": "Alpha", "section_path": ["Alpha"]}

    result = summaries.list_summaries(
        DOCUMENT_ID,
        supabase_client=FakeClient([section_z, document, section_a]),
    )

    assert [row["summary_type"] for row in result] == ["document", "section", "section"]
    assert [row["section_path"] for row in result] == [[], ["Alpha"], ["Zed"]]
    assert all(row["document_id"] == str(DOCUMENT_ID) for row in result)


def test_replace_document_summaries_deletes_then_bulk_inserts():
    client = FakeClient([], [])
    records = [
        {
            "summary_type": "document",
            "content": "Whole document",
            "model": "m",
        },
        {
            "summary_type": "section",
            "heading": "A",
            "section_path": ["A"],
            "content": "Section A",
            "source_chunk_ids": [SUMMARY_ID],
            "model": "m",
        },
    ]

    result = summaries.replace_document_summaries(
        DOCUMENT_ID, records, supabase_client=client
    )

    assert [call.operation for call in client.calls] == ["delete", "insert"]
    assert client.calls[0].filters == [("document_id", str(DOCUMENT_ID))]
    assert all(
        row["document_id"] == str(DOCUMENT_ID) for row in client.calls[1].payload
    )
    assert [row["summary_type"] for row in result] == ["document", "section"]


def test_delete_document_summaries_uses_normalized_document_id():
    client = FakeClient([])

    summaries.delete_document_summaries(DOCUMENT_ID, supabase_client=client)

    assert client.calls[0].operation == "delete"
    assert client.calls[0].filters == [("document_id", str(DOCUMENT_ID))]


def test_fresh_schema_and_migration_define_equivalent_phase3_objects():
    root = Path(__file__).resolve().parents[2]
    migration = (root / "docs/database/phase3_migration.sql").read_text().lower()
    fresh = (root / "docs/database/supabase_schema.sql").read_text().lower()
    required_fragments = (
        "error_code text",
        "create table if not exists document_summaries",
        "create table if not exists document_relations",
        "create table if not exists workflow_runs",
        "summary_type in ('section', 'document')",
        "relation_type in ('same_topic', 'supports', 'contradicts', 'references')",
        "confidence >= 0 and confidence <= 1",
        "source_document_id < target_document_id",
        "workflow_type in ('ingestion', 'query')",
        "status in ('running', 'completed', 'failed')",
    )
    for fragment in required_fragments:
        assert fragment in migration
        assert fragment in fresh
    assert "add column if not exists error_code text" in migration
    assert "create index if not exists" in migration
