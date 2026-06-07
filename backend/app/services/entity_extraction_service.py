import json
import re
from collections import Counter
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ValidationError

from app.core.config import get_settings
from app.schemas.graph import (
    ALLOWED_ENTITY_TYPES,
    ALLOWED_RELATIONSHIP_TYPES,
    EntityDraft,
    LLMGraphExtractionOutput,
    RelationshipDraft,
)
from app.services import shopaikey_service


class EntityExtractionError(RuntimeError):
    """Raised when chunk entity extraction cannot produce validated graph drafts."""

    def __init__(self, message: str, *, chunk_id: UUID | None = None) -> None:
        super().__init__(message)
        self.chunk_id = chunk_id


class EntityExtractionResult(BaseModel):
    entities: list[EntityDraft]
    relationships: list[RelationshipDraft]


DATE_PATTERN = re.compile(
    r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+"
    r"\d{1,2},\s+\d{4}\b"
)
CAPITALIZED_TERM_PATTERN = re.compile(
    r"\b[A-Z][A-Za-z0-9&'-]*(?:\s+[A-Z][A-Za-z0-9&'-]*)+\b"
)


def _chunk_value(chunk: Any, field_name: str) -> Any:
    if isinstance(chunk, dict):
        return chunk.get(field_name)
    return getattr(chunk, field_name, None)


def _require_chunk_id(chunk: Any) -> UUID:
    chunk_id = _chunk_value(chunk, "id")
    if chunk_id is None:
        raise EntityExtractionError("Document chunk is missing required id.")

    try:
        return UUID(str(chunk_id))
    except ValueError as exc:
        raise EntityExtractionError("Document chunk id must be a valid UUID.") from exc


def _require_chunk_content(chunk: Any) -> str:
    content = _chunk_value(chunk, "content")
    if not isinstance(content, str) or not content.strip():
        raise EntityExtractionError("Document chunk is missing required content.")
    return content.strip()


def _optional_section_title(chunk: Any) -> str | None:
    section_title = _chunk_value(chunk, "section_title")
    if not isinstance(section_title, str):
        return None
    normalized = section_title.strip()
    return normalized or None


def _build_extraction_messages(
    *,
    chunk_id: UUID,
    content: str,
    section_title: str | None,
) -> list[dict[str, str]]:
    entity_types = ", ".join(ALLOWED_ENTITY_TYPES)
    relationship_types = ", ".join(ALLOWED_RELATIONSHIP_TYPES)
    section_context = section_title or "No section title"

    return [
        {
            "role": "system",
            "content": (
                "Extract graph entities and entity relationships from one document "
                "chunk. Return strict JSON only, with no markdown or commentary."
            ),
        },
        {
            "role": "user",
            "content": (
                "Return a JSON object with exactly two top-level arrays named "
                '"entities" and "relationships". Entity objects must use keys '
                '"name", "type", and optional "description". Relationship objects '
                'must use keys "source_entity", "target_entity", '
                '"relationship_type", "weight", and optional "description". '
                f"Allowed entity types: {entity_types}. "
                f"Allowed relationship types: {relationship_types}. "
                "Weights must be numbers between 0.0 and 1.0. "
                f"Chunk id: {chunk_id}. Section title: {section_context}. "
                f"Chunk content:\n{content}"
            ),
        },
    ]


def _parse_llm_json(content: str, *, chunk_id: UUID) -> LLMGraphExtractionOutput:
    try:
        payload = json.loads(content)
    except json.JSONDecodeError as exc:
        raise EntityExtractionError(
            "LLM entity extraction returned malformed JSON.",
            chunk_id=chunk_id,
        ) from exc

    try:
        return LLMGraphExtractionOutput.model_validate(payload)
    except ValidationError as exc:
        raise EntityExtractionError(
            "LLM entity extraction returned invalid graph data.",
            chunk_id=chunk_id,
        ) from exc


def _to_entity_drafts(
    llm_output: LLMGraphExtractionOutput,
    *,
    chunk_id: UUID,
) -> list[EntityDraft]:
    return [
        EntityDraft(
            entity_name=entity.name,
            entity_type=entity.type,
            description=entity.description,
            chunk_id=chunk_id,
        )
        for entity in llm_output.entities
    ]


def _to_relationship_drafts(
    llm_output: LLMGraphExtractionOutput,
) -> list[RelationshipDraft]:
    return [
        RelationshipDraft(
            source_type="entity",
            source_id=relationship.source_entity,
            target_type="entity",
            target_id=relationship.target_entity,
            relationship_type=relationship.relationship_type,
            weight=relationship.weight,
            description=relationship.description,
        )
        for relationship in llm_output.relationships
    ]


def _unique_matches(pattern: re.Pattern[str], content: str) -> list[str]:
    matches = []
    seen = set()
    for match in pattern.finditer(content):
        value = " ".join(match.group(0).split())
        if value not in seen:
            matches.append(value)
            seen.add(value)
    return matches


def _deterministic_fallback(chunk_id: UUID, content: str) -> EntityExtractionResult:
    dates = _unique_matches(DATE_PATTERN, content)
    capitalized_terms = _unique_matches(CAPITALIZED_TERM_PATTERN, content)
    term_counts = Counter(
        " ".join(match.group(0).split())
        for match in CAPITALIZED_TERM_PATTERN.finditer(content)
    )
    date_values = set(dates)

    entities = [
        EntityDraft(entity_name=date, entity_type="date", chunk_id=chunk_id)
        for date in dates
    ]
    entities.extend(
        EntityDraft(entity_name=term, entity_type="other", chunk_id=chunk_id)
        for term in capitalized_terms
        if term_counts[term] > 1 and term not in date_values
    )

    return EntityExtractionResult(entities=entities, relationships=[])


def extract_entities_for_chunk(chunk: Any) -> EntityExtractionResult:
    settings = get_settings()
    chunk_id = _require_chunk_id(chunk)
    content = _require_chunk_content(chunk)

    if not settings.graph_extraction_enabled:
        return _deterministic_fallback(chunk_id, content)

    section_title = _optional_section_title(chunk)
    messages = _build_extraction_messages(
        chunk_id=chunk_id,
        content=content,
        section_title=section_title,
    )

    try:
        llm_content = shopaikey_service.chat_completion(
            messages,
            response_format={"type": "json_object"},
        )
    except shopaikey_service.ShopAIKeyServiceError as exc:
        raise EntityExtractionError(
            f"ShopAIKey entity extraction failed for chunk {chunk_id}.",
            chunk_id=chunk_id,
        ) from exc

    llm_output = _parse_llm_json(llm_content, chunk_id=chunk_id)

    return EntityExtractionResult(
        entities=_to_entity_drafts(llm_output, chunk_id=chunk_id),
        relationships=_to_relationship_drafts(llm_output),
    )
