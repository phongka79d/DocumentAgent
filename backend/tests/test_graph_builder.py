import sys
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services import graph_builder
from app.schemas.graph import EntityDraft, RelationshipDraft


DOCUMENT_ID = "11111111-1111-1111-1111-111111111111"
CHUNK_ID_1 = "22222222-2222-2222-2222-222222222222"
CHUNK_ID_2 = "33333333-3333-3333-3333-333333333333"
CHUNK_ID_3 = "44444444-4444-4444-4444-444444444444"


@pytest.fixture(autouse=True)
def _stub_entity_extraction(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        graph_builder.entity_extraction_service,
        "extract_entities_for_chunk",
        lambda chunk: SimpleNamespace(entities=[], relationships=[]),
    )


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


def test_build_document_graph_persists_deduplicated_document_entities(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inserted_entity_batches = []

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
        lambda document_id: None,
    )
    monkeypatch.setattr(
        graph_builder.supabase_service,
        "insert_document_relationships",
        lambda document_id, relationships: [
            {"id": str(index)} for index, _relationship in enumerate(relationships)
        ],
    )

    def extract_entities_for_chunk(chunk: dict[str, object]) -> SimpleNamespace:
        chunk_id = UUID(str(chunk["id"]))
        if chunk["id"] == CHUNK_ID_1:
            return SimpleNamespace(
                entities=[
                    EntityDraft(
                        entity_name=" Probation Period ",
                        entity_type="contract term",
                        description="Initial probation clause",
                        chunk_id=chunk_id,
                    ),
                    object(),
                ],
                relationships=[],
            )

        return SimpleNamespace(
            entities=[
                EntityDraft(
                    entity_name="probation period",
                    entity_type="contract term",
                    description="Duplicate mention",
                    chunk_id=chunk_id,
                ),
                EntityDraft(
                    entity_name="June 1, 2026",
                    entity_type="date",
                    chunk_id=chunk_id,
                ),
            ],
            relationships=[],
        )

    def insert_document_entities(
        document_id: str,
        entities: list[EntityDraft],
    ) -> list[dict[str, object]]:
        inserted_entity_batches.append((document_id, entities))
        return [
            {
                "id": f"entity-{index}",
                "document_id": document_id,
                "entity_name": entity.entity_name,
                "entity_type": entity.entity_type,
                "chunk_id": str(entity.chunk_id),
                "user_id": "single_user",
            }
            for index, entity in enumerate(entities)
        ]

    monkeypatch.setattr(
        graph_builder,
        "entity_extraction_service",
        SimpleNamespace(extract_entities_for_chunk=extract_entities_for_chunk),
        raising=False,
    )
    monkeypatch.setattr(
        graph_builder.supabase_service,
        "insert_document_entities",
        insert_document_entities,
    )

    result = graph_builder.build_document_graph(DOCUMENT_ID)

    assert result.entity_count == 2
    assert result.relationship_count == 7
    assert result.errors == []
    assert len(inserted_entity_batches) == 1
    document_id, entities = inserted_entity_batches[0]
    assert document_id == DOCUMENT_ID
    assert [(entity.entity_name, entity.entity_type) for entity in entities] == [
        ("Probation Period", "contract term"),
        ("June 1, 2026", "date"),
    ]
    assert entities[0].chunk_id == UUID(CHUNK_ID_1)
    assert entities[1].chunk_id == UUID(CHUNK_ID_2)


def test_build_document_graph_reports_safe_chunk_extraction_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret_value = "provider-secret-token"

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
        lambda document_id: None,
    )

    def extract_entities_for_chunk(chunk: dict[str, object]) -> SimpleNamespace:
        if chunk["id"] == CHUNK_ID_2:
            raise RuntimeError(f"provider failed with token {secret_value}")

        return SimpleNamespace(
            entities=[
                EntityDraft(
                    entity_name="Probation Period",
                    entity_type="contract term",
                    chunk_id=UUID(str(chunk["id"])),
                )
            ],
            relationships=[],
        )

    def insert_document_entities(
        document_id: str,
        entities: list[EntityDraft],
    ) -> list[dict[str, object]]:
        return [
            {
                "id": f"entity-{index}",
                "document_id": document_id,
                "entity_name": entity.entity_name,
                "entity_type": entity.entity_type,
                "chunk_id": str(entity.chunk_id),
                "user_id": "single_user",
            }
            for index, entity in enumerate(entities)
        ]

    monkeypatch.setattr(
        graph_builder,
        "entity_extraction_service",
        SimpleNamespace(extract_entities_for_chunk=extract_entities_for_chunk),
        raising=False,
    )
    monkeypatch.setattr(
        graph_builder.supabase_service,
        "insert_document_entities",
        insert_document_entities,
    )
    monkeypatch.setattr(
        graph_builder.supabase_service,
        "insert_document_relationships",
        lambda document_id, relationships: [
            {"id": str(index)} for index, _relationship in enumerate(relationships)
        ],
    )

    result = graph_builder.build_document_graph(DOCUMENT_ID)

    assert result.entity_count == 1
    assert result.relationship_count == 5
    assert result.graph_rows_cleared is True
    assert result.partial_state_risk is True
    assert len(result.errors) == 1
    error = result.errors[0]
    assert error.operation == "extract_entities_for_chunk"
    assert error.chunk_id == UUID(CHUNK_ID_2)
    assert "skipped" in error.message
    assert secret_value not in error.message
    assert secret_value not in str(error.details)
    assert error.details == {
        "graph_rows_cleared": True,
        "partial_state_risk": True,
    }


def test_build_document_graph_persists_chunk_mentions_and_valid_entity_relations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    relationship_batches = []

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
        lambda document_id: None,
    )

    def extract_entities_for_chunk(chunk: dict[str, object]) -> SimpleNamespace:
        chunk_id = UUID(str(chunk["id"]))
        if chunk["id"] == CHUNK_ID_1:
            return SimpleNamespace(
                entities=[
                    EntityDraft(
                        entity_name="Probation Period",
                        entity_type="contract term",
                        chunk_id=chunk_id,
                    ),
                    EntityDraft(
                        entity_name="June 1, 2026",
                        entity_type="date",
                        chunk_id=chunk_id,
                    ),
                ],
                relationships=[
                    RelationshipDraft(
                        source_type="entity",
                        source_id="Probation Period",
                        target_type="entity",
                        target_id="June 1, 2026",
                        relationship_type="requires",
                        weight=0.7,
                        description="Probation requires a start date",
                    ),
                    RelationshipDraft(
                        source_type="entity",
                        source_id="Missing Endpoint",
                        target_type="entity",
                        target_id="June 1, 2026",
                        relationship_type="related_to",
                        weight=0.5,
                    ),
                ],
            )

        return SimpleNamespace(
            entities=[
                EntityDraft(
                    entity_name="probation period",
                    entity_type="contract term",
                    chunk_id=chunk_id,
                ),
            ],
            relationships=[],
        )

    def insert_document_entities(
        document_id: str,
        entities: list[EntityDraft],
    ) -> list[dict[str, object]]:
        return [
            {
                "id": f"entity-{index}",
                "document_id": document_id,
                "entity_name": entity.entity_name,
                "entity_type": entity.entity_type,
                "chunk_id": str(entity.chunk_id),
                "user_id": "single_user",
            }
            for index, entity in enumerate(entities)
        ]

    def insert_document_relationships(
        document_id: str,
        relationships: list[RelationshipDraft],
    ) -> list[dict[str, object]]:
        relationship_batches.append(relationships)
        return [{"id": str(index)} for index, _relationship in enumerate(relationships)]

    monkeypatch.setattr(
        graph_builder,
        "entity_extraction_service",
        SimpleNamespace(extract_entities_for_chunk=extract_entities_for_chunk),
        raising=False,
    )
    monkeypatch.setattr(
        graph_builder.supabase_service,
        "insert_document_entities",
        insert_document_entities,
    )
    monkeypatch.setattr(
        graph_builder.supabase_service,
        "insert_document_relationships",
        insert_document_relationships,
    )

    result = graph_builder.build_document_graph(DOCUMENT_ID)

    assert result.entity_count == 2
    assert result.relationship_count == 8
    assert result.errors == []
    assert len(relationship_batches) == 2

    entity_relationships = relationship_batches[1]
    assert [
        relationship.relationship_type for relationship in entity_relationships
    ] == [
        "chunk_mentions_entity",
        "chunk_mentions_entity",
        "chunk_mentions_entity",
        "entity_related_to_entity",
    ]
    assert [
        (relationship.source_type, relationship.source_id)
        for relationship in entity_relationships[:3]
    ] == [
        ("chunk", CHUNK_ID_1),
        ("chunk", CHUNK_ID_1),
        ("chunk", CHUNK_ID_2),
    ]
    assert [relationship.target_id for relationship in entity_relationships[:3]] == [
        "entity-0",
        "entity-1",
        "entity-0",
    ]
    assert entity_relationships[3].source_type == "entity"
    assert entity_relationships[3].source_id == "entity-0"
    assert entity_relationships[3].target_type == "entity"
    assert entity_relationships[3].target_id == "entity-1"
    assert entity_relationships[3].weight == 0.7
    assert (
        entity_relationships[3].description
        == "requires: Probation requires a start date"
    )


def test_build_document_graph_reports_failed_entity_relationship_insert(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    insert_relationship_calls = 0

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
        lambda document_id: None,
    )

    def extract_entities_for_chunk(chunk: dict[str, object]) -> SimpleNamespace:
        return SimpleNamespace(
            entities=[
                EntityDraft(
                    entity_name="Probation Period",
                    entity_type="contract term",
                    chunk_id=UUID(str(chunk["id"])),
                ),
            ],
            relationships=[],
        )

    def insert_document_entities(
        document_id: str,
        entities: list[EntityDraft],
    ) -> list[dict[str, object]]:
        return [
            {
                "id": "entity-0",
                "document_id": document_id,
                "entity_name": entities[0].entity_name,
                "entity_type": entities[0].entity_type,
                "chunk_id": str(entities[0].chunk_id),
                "user_id": "single_user",
            }
        ]

    def insert_document_relationships(
        document_id: str,
        relationships: list[RelationshipDraft],
    ) -> list[dict[str, object]]:
        nonlocal insert_relationship_calls
        insert_relationship_calls += 1
        if insert_relationship_calls == 2:
            raise RuntimeError("relationship insert failed")
        return [{"id": str(index)} for index, _relationship in enumerate(relationships)]

    monkeypatch.setattr(
        graph_builder,
        "entity_extraction_service",
        SimpleNamespace(extract_entities_for_chunk=extract_entities_for_chunk),
        raising=False,
    )
    monkeypatch.setattr(
        graph_builder.supabase_service,
        "insert_document_entities",
        insert_document_entities,
    )
    monkeypatch.setattr(
        graph_builder.supabase_service,
        "insert_document_relationships",
        insert_document_relationships,
    )

    with pytest.raises(graph_builder.GraphBuildException) as exc_info:
        graph_builder.build_document_graph(DOCUMENT_ID)

    assert (
        str(exc_info.value)
        == f"Graph build could not insert entity relationships: {DOCUMENT_ID}."
    )
    result = exc_info.value.result
    assert result.document_id == UUID(DOCUMENT_ID)
    assert result.entity_count == 1
    assert result.relationship_count == 4
    assert result.graph_rows_cleared is True
    assert result.partial_state_risk is True
    assert result.errors[0].operation == "insert_entity_relationships"
    assert result.errors[0].details == {
        "graph_rows_cleared": True,
        "partial_state_risk": True,
    }


def test_build_document_graph_adds_chunk_relationship_for_strong_entity_overlap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    relationship_batches = []

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
        lambda document_id: None,
    )

    def extract_entities_for_chunk(chunk: dict[str, object]) -> SimpleNamespace:
        chunk_id = UUID(str(chunk["id"]))
        if chunk["id"] == CHUNK_ID_1:
            names = ["Probation Period", "June 1, 2026", "Engineering Team"]
        else:
            names = ["probation period", "June 1, 2026", "Remote Work Policy"]

        def entity_type_for(name: str) -> str:
            if "Period" in name or "period" in name:
                return "contract term"
            return "other"

        return SimpleNamespace(
            entities=[
                EntityDraft(
                    entity_name=name,
                    entity_type=entity_type_for(name),
                    chunk_id=chunk_id,
                )
                for name in names
            ],
            relationships=[],
        )

    def insert_document_entities(
        document_id: str,
        entities: list[EntityDraft],
    ) -> list[dict[str, object]]:
        return [
            {
                "id": f"entity-{index}",
                "document_id": document_id,
                "entity_name": entity.entity_name,
                "entity_type": entity.entity_type,
                "chunk_id": str(entity.chunk_id),
                "user_id": "single_user",
            }
            for index, entity in enumerate(entities)
        ]

    def insert_document_relationships(
        document_id: str,
        relationships: list[RelationshipDraft],
    ) -> list[dict[str, object]]:
        relationship_batches.append(relationships)
        return [{"id": str(index)} for index, _relationship in enumerate(relationships)]

    monkeypatch.setattr(
        graph_builder,
        "entity_extraction_service",
        SimpleNamespace(extract_entities_for_chunk=extract_entities_for_chunk),
        raising=False,
    )
    monkeypatch.setattr(
        graph_builder.supabase_service,
        "insert_document_entities",
        insert_document_entities,
    )
    monkeypatch.setattr(
        graph_builder.supabase_service,
        "insert_document_relationships",
        insert_document_relationships,
    )

    result = graph_builder.build_document_graph(DOCUMENT_ID)

    assert result.entity_count == 4
    assert result.relationship_count == 11
    chunk_relationships = [
        relationship
        for relationship in relationship_batches[1]
        if relationship.relationship_type == "chunk_related_to_chunk"
    ]
    assert len(chunk_relationships) == 1
    assert chunk_relationships[0].source_type == "chunk"
    assert chunk_relationships[0].source_id == CHUNK_ID_1
    assert chunk_relationships[0].target_type == "chunk"
    assert chunk_relationships[0].target_id == CHUNK_ID_2
    assert chunk_relationships[0].weight == 0.5


def test_build_document_graph_skips_weak_chunk_overlap_self_links_and_duplicates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    relationship_batches = []
    chunks = [
        *_chunks(),
        {
            "id": CHUNK_ID_3,
            "document_id": DOCUMENT_ID,
            "user_id": "single_user",
            "chunk_index": 2,
            "content": "Third chunk",
            "page_number": 3,
            "section_title": "Terms",
            "token_count": 2,
        },
    ]

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

    entity_names_by_chunk = {
        CHUNK_ID_1: ["Probation Period", "June 1, 2026", "Remote Work Policy"],
        CHUNK_ID_2: ["Probation Period"],
        CHUNK_ID_3: ["Remote Work Policy", "June 1, 2026", "Probation Period"],
    }

    def extract_entities_for_chunk(chunk: dict[str, object]) -> SimpleNamespace:
        chunk_id = UUID(str(chunk["id"]))
        return SimpleNamespace(
            entities=[
                EntityDraft(
                    entity_name=name,
                    entity_type="contract term",
                    chunk_id=chunk_id,
                )
                for name in entity_names_by_chunk[str(chunk["id"])]
            ],
            relationships=[],
        )

    def insert_document_entities(
        document_id: str,
        entities: list[EntityDraft],
    ) -> list[dict[str, object]]:
        return [
            {
                "id": f"entity-{index}",
                "document_id": document_id,
                "entity_name": entity.entity_name,
                "entity_type": entity.entity_type,
                "chunk_id": str(entity.chunk_id),
                "user_id": "single_user",
            }
            for index, entity in enumerate(entities)
        ]

    def insert_document_relationships(
        document_id: str,
        relationships: list[RelationshipDraft],
    ) -> list[dict[str, object]]:
        relationship_batches.append(relationships)
        return [{"id": str(index)} for index, _relationship in enumerate(relationships)]

    monkeypatch.setattr(
        graph_builder,
        "entity_extraction_service",
        SimpleNamespace(extract_entities_for_chunk=extract_entities_for_chunk),
        raising=False,
    )
    monkeypatch.setattr(
        graph_builder.supabase_service,
        "insert_document_entities",
        insert_document_entities,
    )
    monkeypatch.setattr(
        graph_builder.supabase_service,
        "insert_document_relationships",
        insert_document_relationships,
    )

    graph_builder.build_document_graph(DOCUMENT_ID)

    chunk_relationships = [
        relationship
        for relationship in relationship_batches[1]
        if relationship.relationship_type == "chunk_related_to_chunk"
    ]
    assert [
        (relationship.source_id, relationship.target_id, relationship.weight)
        for relationship in chunk_relationships
    ] == [(CHUNK_ID_1, CHUNK_ID_3, 1.0)]
    assert all(
        relationship.source_id != relationship.target_id
        for relationship in chunk_relationships
    )
