import sys
from pathlib import Path
from uuid import UUID

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services import graph_builder
from app.schemas.graph import RelationshipDraft


DOCUMENT_ID = "11111111-1111-1111-1111-111111111111"
CHUNK_ID_1 = "22222222-2222-2222-2222-222222222222"
CHUNK_ID_2 = "33333333-3333-3333-3333-333333333333"


def _document() -> dict[str, str]:
    return {
        "id": DOCUMENT_ID,
        "user_id": "single_user",
        "file_name": "handbook.pdf",
    }


def _chunks() -> list[dict[str, object]]:
    return [
        {
            "id": CHUNK_ID_1,
            "document_id": DOCUMENT_ID,
            "user_id": "single_user",
            "chunk_index": 0,
            "content": "First chunk",
            "page_number": 1,
            "section_title": "Intro",
            "token_count": 2,
        },
        {
            "id": CHUNK_ID_2,
            "document_id": DOCUMENT_ID,
            "user_id": "single_user",
            "chunk_index": 1,
            "content": "Second chunk",
            "page_number": 2,
            "section_title": "Terms",
            "token_count": 2,
        },
    ]


def _chunks_without_section_titles() -> list[dict[str, object]]:
    return [
        {
            "id": CHUNK_ID_1,
            "document_id": DOCUMENT_ID,
            "user_id": "single_user",
            "chunk_index": 0,
            "content": "First chunk",
            "page_number": 7,
            "section_title": " ",
            "token_count": 2,
        },
        {
            "id": CHUNK_ID_2,
            "document_id": DOCUMENT_ID,
            "user_id": "single_user",
            "chunk_index": 1,
            "content": "Second chunk",
            "page_number": None,
            "section_title": None,
            "token_count": 2,
        },
    ]


def test_build_document_graph_returns_clear_not_found_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        graph_builder.supabase_service,
        "get_graph_document",
        lambda document_id: None,
    )
    monkeypatch.setattr(
        graph_builder.supabase_service,
        "list_document_chunks",
        lambda document_id: pytest.fail(
            "chunks must not be loaded for a missing document"
        ),
    )
    monkeypatch.setattr(
        graph_builder.supabase_service,
        "clear_document_graph_rows",
        lambda document_id: pytest.fail(
            "graph rows must not be cleared for a missing document"
        ),
    )

    with pytest.raises(graph_builder.GraphBuildException) as exc_info:
        graph_builder.build_document_graph(DOCUMENT_ID)

    assert str(exc_info.value) == f"Graph build document not found: {DOCUMENT_ID}."
    result = exc_info.value.result
    assert result.document_id == UUID(DOCUMENT_ID)
    assert result.entity_count == 0
    assert result.relationship_count == 0
    assert result.errors[0].operation == "load_document"
    assert result.errors[0].message == f"Document not found for graph build: {DOCUMENT_ID}."


def test_build_document_graph_returns_clear_no_chunks_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        graph_builder.supabase_service,
        "get_graph_document",
        lambda document_id: _document(),
    )
    monkeypatch.setattr(
        graph_builder.supabase_service,
        "list_document_chunks",
        lambda document_id: [],
    )
    monkeypatch.setattr(
        graph_builder.supabase_service,
        "clear_document_graph_rows",
        lambda document_id: pytest.fail(
            "graph rows must not be cleared before chunk preflight passes"
        ),
    )

    with pytest.raises(graph_builder.GraphBuildException) as exc_info:
        graph_builder.build_document_graph(DOCUMENT_ID)

    assert str(exc_info.value) == f"Graph build has no chunks: {DOCUMENT_ID}."
    result = exc_info.value.result
    assert result.document_id == UUID(DOCUMENT_ID)
    assert result.errors[0].operation == "load_chunks"
    assert result.errors[0].message == f"Document has no chunks for graph build: {DOCUMENT_ID}."


def test_build_document_graph_loads_document_and_chunks_before_later_stages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = []
    chunks = _chunks()

    def get_graph_document(document_id: str) -> dict[str, str]:
        calls.append(("get_document", document_id))
        return _document()

    def list_document_chunks(document_id: str) -> list[dict[str, object]]:
        calls.append(("list_chunks", document_id))
        return chunks

    def clear_document_graph_rows(document_id: str) -> None:
        calls.append(("clear_graph_rows", document_id))

    def insert_document_relationships(
        document_id: str,
        relationships: list[RelationshipDraft],
    ) -> list[dict[str, object]]:
        calls.append(("insert_relationships", document_id, len(relationships)))
        return [{"id": str(index)} for index, _relationship in enumerate(relationships)]

    monkeypatch.setattr(
        graph_builder.supabase_service,
        "get_graph_document",
        get_graph_document,
    )
    monkeypatch.setattr(
        graph_builder.supabase_service,
        "list_document_chunks",
        list_document_chunks,
    )
    monkeypatch.setattr(
        graph_builder.supabase_service,
        "clear_document_graph_rows",
        clear_document_graph_rows,
    )
    monkeypatch.setattr(
        graph_builder.supabase_service,
        "insert_document_relationships",
        insert_document_relationships,
    )

    result = graph_builder.build_document_graph(DOCUMENT_ID)

    assert result.document_id == UUID(DOCUMENT_ID)
    assert result.entity_count == 0
    assert result.relationship_count == 4
    assert result.errors == []
    assert calls == [
        ("get_document", DOCUMENT_ID),
        ("list_chunks", DOCUMENT_ID),
        ("clear_graph_rows", DOCUMENT_ID),
        ("insert_relationships", DOCUMENT_ID, 4),
    ]


def test_build_document_graph_clears_existing_rows_on_each_rebuild(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clear_calls = []

    monkeypatch.setattr(
        graph_builder.supabase_service,
        "get_graph_document",
        lambda document_id: _document(),
    )
    monkeypatch.setattr(
        graph_builder.supabase_service,
        "list_document_chunks",
        lambda document_id: _chunks(),
    )
    monkeypatch.setattr(
        graph_builder.supabase_service,
        "clear_document_graph_rows",
        lambda document_id: clear_calls.append(document_id),
    )
    monkeypatch.setattr(
        graph_builder.supabase_service,
        "insert_document_relationships",
        lambda document_id, relationships: [
            {"id": str(index)} for index, _relationship in enumerate(relationships)
        ],
    )

    first_result = graph_builder.build_document_graph(DOCUMENT_ID)
    second_result = graph_builder.build_document_graph(DOCUMENT_ID)

    assert first_result.errors == []
    assert second_result.errors == []
    assert clear_calls == [DOCUMENT_ID, DOCUMENT_ID]


def test_build_document_graph_reports_partial_state_risk_when_clear_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        graph_builder.supabase_service,
        "get_graph_document",
        lambda document_id: _document(),
    )
    monkeypatch.setattr(
        graph_builder.supabase_service,
        "list_document_chunks",
        lambda document_id: _chunks(),
    )

    def clear_document_graph_rows(document_id: str) -> None:
        raise RuntimeError("delete failed")

    monkeypatch.setattr(
        graph_builder.supabase_service,
        "clear_document_graph_rows",
        clear_document_graph_rows,
    )

    with pytest.raises(graph_builder.GraphBuildException) as exc_info:
        graph_builder.build_document_graph(DOCUMENT_ID)

    assert (
        str(exc_info.value)
        == f"Graph build could not clear existing graph rows: {DOCUMENT_ID}."
    )
    result = exc_info.value.result
    assert result.document_id == UUID(DOCUMENT_ID)
    assert result.entity_count == 0
    assert result.relationship_count == 0
    assert result.errors[0].operation == "clear_graph_rows"
    assert result.errors[0].details == {
        "graph_rows_cleared": True,
        "partial_state_risk": True,
    }


def test_build_document_graph_persists_section_structural_relationships(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inserted_relationships = []
    chunks = _chunks()
    chunks.append(
        {
            "id": "44444444-4444-4444-4444-444444444444",
            "document_id": DOCUMENT_ID,
            "user_id": "single_user",
            "chunk_index": 2,
            "content": "Another intro chunk",
            "page_number": 3,
            "section_title": " Intro ",
            "token_count": 3,
        }
    )

    monkeypatch.setattr(
        graph_builder.supabase_service,
        "get_graph_document",
        lambda document_id: _document(),
    )
    monkeypatch.setattr(
        graph_builder.supabase_service,
        "list_document_chunks",
        lambda document_id: chunks,
    )
    monkeypatch.setattr(
        graph_builder.supabase_service,
        "clear_document_graph_rows",
        lambda document_id: None,
    )

    def insert_document_relationships(
        document_id: str,
        relationships: list[RelationshipDraft],
    ) -> list[dict[str, object]]:
        inserted_relationships.extend(relationships)
        return [{"id": str(index)} for index, _relationship in enumerate(relationships)]

    monkeypatch.setattr(
        graph_builder.supabase_service,
        "insert_document_relationships",
        insert_document_relationships,
    )

    result = graph_builder.build_document_graph(DOCUMENT_ID)

    assert result.relationship_count == 5
    assert [relationship.relationship_type for relationship in inserted_relationships] == [
        "document_contains_section",
        "document_contains_section",
        "section_contains_chunk",
        "section_contains_chunk",
        "section_contains_chunk",
    ]
    section_ids = [
        relationship.target_id
        for relationship in inserted_relationships
        if relationship.relationship_type == "document_contains_section"
    ]
    assert section_ids == [
        f"{DOCUMENT_ID}:section:intro",
        f"{DOCUMENT_ID}:section:terms",
    ]
    assert inserted_relationships[0].source_type == "document"
    assert inserted_relationships[0].source_id == DOCUMENT_ID
    assert inserted_relationships[0].target_type == "section"
    assert inserted_relationships[0].weight == 1.0
    assert inserted_relationships[0].description == "Document contains section Intro."
    assert inserted_relationships[2].source_type == "section"
    assert inserted_relationships[2].source_id == f"{DOCUMENT_ID}:section:intro"
    assert inserted_relationships[2].target_type == "chunk"
    assert inserted_relationships[2].target_id == CHUNK_ID_1
    assert inserted_relationships[2].weight == 1.0
    assert inserted_relationships[2].description == "Section Intro contains chunk 0."
    assert inserted_relationships[4].source_id == f"{DOCUMENT_ID}:section:intro"


def test_build_document_graph_uses_page_and_chunk_fallback_section_keys(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inserted_relationships = []

    monkeypatch.setattr(
        graph_builder.supabase_service,
        "get_graph_document",
        lambda document_id: _document(),
    )
    monkeypatch.setattr(
        graph_builder.supabase_service,
        "list_document_chunks",
        lambda document_id: _chunks_without_section_titles(),
    )
    monkeypatch.setattr(
        graph_builder.supabase_service,
        "clear_document_graph_rows",
        lambda document_id: None,
    )

    def insert_document_relationships(
        document_id: str,
        relationships: list[RelationshipDraft],
    ) -> list[dict[str, object]]:
        inserted_relationships.extend(relationships)
        return [{"id": str(index)} for index, _relationship in enumerate(relationships)]

    monkeypatch.setattr(
        graph_builder.supabase_service,
        "insert_document_relationships",
        insert_document_relationships,
    )

    result = graph_builder.build_document_graph(DOCUMENT_ID)

    assert result.relationship_count == 4
    assert [relationship.target_id for relationship in inserted_relationships[:2]] == [
        f"{DOCUMENT_ID}:section:page-7",
        f"{DOCUMENT_ID}:section:chunk-group-1",
    ]
    assert [relationship.description for relationship in inserted_relationships[:2]] == [
        "Document contains section Page 7.",
        "Document contains section Chunk group 1.",
    ]
