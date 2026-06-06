import sys
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.schemas import (
    ALLOWED_ENTITY_TYPES,
    ALLOWED_RELATIONSHIP_TYPES,
    EntityDraft,
    GraphBuildResult,
    LLMGraphExtractionOutput,
    RelationshipDraft,
)


def test_graph_schema_constants_include_plan_allowed_types() -> None:
    assert "contract term" in ALLOWED_ENTITY_TYPES
    assert "probation period" in ALLOWED_ENTITY_TYPES
    assert "document_contains_section" in ALLOWED_RELATIONSHIP_TYPES
    assert "depends_on" in ALLOWED_RELATIONSHIP_TYPES


def test_entity_draft_rejects_invalid_type_and_empty_name() -> None:
    with pytest.raises(ValidationError):
        EntityDraft(
            entity_name="Unknown Term",
            entity_type="invalid",
            chunk_id=uuid4(),
        )

    with pytest.raises(ValidationError):
        EntityDraft(
            entity_name="   ",
            entity_type="other",
            chunk_id=uuid4(),
        )


def test_relationship_draft_rejects_invalid_type_and_malformed_weight() -> None:
    valid_relationship = {
        "source_type": "chunk",
        "source_id": str(uuid4()),
        "target_type": "entity",
        "target_id": "Probation Period",
        "relationship_type": "chunk_mentions_entity",
        "weight": 0.8,
    }

    assert RelationshipDraft(**valid_relationship).weight == 0.8

    with pytest.raises(ValidationError):
        RelationshipDraft(**{**valid_relationship, "relationship_type": "invalid"})

    with pytest.raises(ValidationError):
        RelationshipDraft(**{**valid_relationship, "weight": "0.8"})

    with pytest.raises(ValidationError):
        RelationshipDraft(**{**valid_relationship, "weight": 1.5})


def test_llm_extraction_output_rejects_malformed_structure() -> None:
    valid_extraction = LLMGraphExtractionOutput(
        entities=[
            {
                "name": "Start Date",
                "type": "date",
                "description": "The date employment starts",
            }
        ],
        relationships=[
            {
                "source_entity": "Offer Letter",
                "target_entity": "Start Date",
                "relationship_type": "starts_at",
                "weight": 0.7,
            }
        ],
    )

    assert valid_extraction.entities[0].name == "Start Date"

    with pytest.raises(ValidationError):
        LLMGraphExtractionOutput(
            entities=[{"name": "Start Date", "type": "date"}],
            relationships=[{"source_entity": "Offer Letter", "relationship_type": "starts_at"}],
        )


def test_graph_build_result_validates_counts() -> None:
    result = GraphBuildResult(document_id=uuid4(), entity_count=1, relationship_count=2)

    assert result.entity_count == 1
    assert result.relationship_count == 2

    with pytest.raises(ValidationError):
        GraphBuildResult(document_id=uuid4(), entity_count=-1, relationship_count=0)
