from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


AllowedEntityType = Literal[
    "person",
    "date",
    "organization",
    "policy",
    "contract term",
    "job position",
    "probation period",
    "salary",
    "deadline",
    "condition",
    "other",
]

AllowedRelationshipType = Literal[
    "document_contains_section",
    "section_contains_chunk",
    "chunk_mentions_entity",
    "entity_related_to_entity",
    "chunk_related_to_chunk",
    "mentions",
    "contains",
    "requires",
    "starts_at",
    "ends_at",
    "depends_on",
    "related_to",
]

ALLOWED_ENTITY_TYPES: tuple[str, ...] = (
    "person",
    "date",
    "organization",
    "policy",
    "contract term",
    "job position",
    "probation period",
    "salary",
    "deadline",
    "condition",
    "other",
)

ALLOWED_RELATIONSHIP_TYPES: tuple[str, ...] = (
    "document_contains_section",
    "section_contains_chunk",
    "chunk_mentions_entity",
    "entity_related_to_entity",
    "chunk_related_to_chunk",
    "mentions",
    "contains",
    "requires",
    "starts_at",
    "ends_at",
    "depends_on",
    "related_to",
)


class EntityDraft(BaseModel):
    entity_name: str = Field(min_length=1)
    entity_type: AllowedEntityType
    description: str | None = None
    chunk_id: UUID

    @field_validator("entity_name")
    @classmethod
    def normalize_entity_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("entity_name must not be empty")
        return normalized

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class RelationshipDraft(BaseModel):
    source_type: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
    target_type: str = Field(min_length=1)
    target_id: str = Field(min_length=1)
    relationship_type: AllowedRelationshipType
    weight: float = Field(ge=0, le=1, strict=True)
    description: str | None = None

    @field_validator("source_type", "source_id", "target_type", "target_id")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("relationship identifiers and types must not be empty")
        return normalized

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class LLMEntityOutput(BaseModel):
    name: str = Field(min_length=1)
    type: AllowedEntityType
    description: str | None = None

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("name must not be empty")
        return normalized

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class LLMRelationshipOutput(BaseModel):
    source_entity: str = Field(min_length=1)
    target_entity: str = Field(min_length=1)
    relationship_type: AllowedRelationshipType
    weight: float = Field(ge=0, le=1, strict=True)
    description: str | None = None

    @field_validator("source_entity", "target_entity")
    @classmethod
    def normalize_endpoint(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("relationship endpoints must not be empty")
        return normalized

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class LLMGraphExtractionOutput(BaseModel):
    entities: list[LLMEntityOutput] = Field(default_factory=list)
    relationships: list[LLMRelationshipOutput] = Field(default_factory=list)


class GraphBuildError(BaseModel):
    operation: str = Field(min_length=1)
    message: str = Field(min_length=1)
    chunk_id: UUID | None = None
    details: dict[str, Any] = Field(default_factory=dict)

    @field_validator("operation", "message")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("graph build errors require operation and message")
        return normalized


class GraphBuildResult(BaseModel):
    document_id: UUID
    entity_count: int = Field(ge=0)
    relationship_count: int = Field(ge=0)
    errors: list[GraphBuildError] = Field(default_factory=list)
    graph_rows_cleared: bool = False
    partial_state_risk: bool = False
