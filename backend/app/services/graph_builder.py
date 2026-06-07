import re
import unicodedata
from dataclasses import dataclass
from uuid import UUID

from app.schemas.graph import (
    EntityDraft,
    GraphBuildError,
    GraphBuildResult,
    RelationshipDraft,
)
from app.services import entity_extraction_service, supabase_service


_CHUNK_OVERLAP_MIN_SHARED_ENTITIES = 2
_CHUNK_OVERLAP_MIN_WEIGHT = 0.5


class GraphBuildException(RuntimeError):
    """Raised when graph build preflight cannot proceed safely."""

    def __init__(self, message: str, result: GraphBuildResult) -> None:
        super().__init__(message)
        self.result = result


@dataclass(frozen=True)
class _ChunkGraphDrafts:
    chunk: dict
    entities: list[EntityDraft]
    relationships: list[RelationshipDraft]


def _build_result(
    document_id: str,
    *,
    entity_count: int = 0,
    relationship_count: int = 0,
    errors: list[GraphBuildError] | None = None,
    graph_rows_cleared: bool = False,
    partial_state_risk: bool = False,
) -> GraphBuildResult:
    return GraphBuildResult(
        document_id=UUID(document_id),
        entity_count=entity_count,
        relationship_count=relationship_count,
        errors=errors or [],
        graph_rows_cleared=graph_rows_cleared,
        partial_state_risk=partial_state_risk,
    )


def _empty_result(
    document_id: str,
    error: GraphBuildError | None = None,
    *,
    graph_rows_cleared: bool = False,
    partial_state_risk: bool = False,
) -> GraphBuildResult:
    errors = [error] if error is not None else []
    return _build_result(
        document_id,
        errors=errors,
        graph_rows_cleared=graph_rows_cleared,
        partial_state_risk=partial_state_risk,
    )


def _failure_result(
    document_id: str,
    error: GraphBuildError,
    *,
    entity_count: int = 0,
    relationship_count: int = 0,
    graph_rows_cleared: bool = False,
    partial_state_risk: bool = False,
) -> GraphBuildResult:
    return _build_result(
        document_id,
        entity_count=entity_count,
        relationship_count=relationship_count,
        errors=[error],
        graph_rows_cleared=graph_rows_cleared,
        partial_state_risk=partial_state_risk,
    )


def _build_error(
    operation: str,
    message: str,
    *,
    chunk_id: UUID | None = None,
    graph_rows_cleared: bool = False,
    partial_state_risk: bool = False,
) -> GraphBuildError:
    return GraphBuildError(
        operation=operation,
        message=message,
        chunk_id=chunk_id,
        details={
            "graph_rows_cleared": graph_rows_cleared,
            "partial_state_risk": partial_state_risk,
        },
    )


def _raise_not_found(document_id: str) -> None:
    raise GraphBuildException(
        f"Graph build document not found: {document_id}.",
        _empty_result(
            document_id,
            _build_error(
                operation="load_document",
                message=f"Document not found for graph build: {document_id}.",
            ),
        ),
    )


def _raise_no_chunks(document_id: str) -> None:
    raise GraphBuildException(
        f"Graph build has no chunks: {document_id}.",
        _empty_result(
            document_id,
            _build_error(
                operation="load_chunks",
                message=f"Document has no chunks for graph build: {document_id}.",
            ),
        ),
    )


def _clear_existing_graph_rows(document_id: str) -> None:
    try:
        supabase_service.clear_document_graph_rows(document_id)
    except Exception as exc:
        raise GraphBuildException(
            f"Graph build could not clear existing graph rows: {document_id}.",
            _empty_result(
                document_id,
                _build_error(
                    operation="clear_graph_rows",
                    message=(
                        "Failed to clear existing graph rows before rebuild; "
                        "document graph may be partially cleared."
                    ),
                    graph_rows_cleared=True,
                    partial_state_risk=True,
                ),
                graph_rows_cleared=True,
                partial_state_risk=True,
            ),
        ) from exc


def _slugify(value: str) -> str:
    ascii_value = (
        unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    )
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_value.strip().lower()).strip("-")
    return slug or "untitled"


def _chunk_index(chunk: dict) -> int:
    chunk_index = chunk.get("chunk_index")
    if isinstance(chunk_index, int):
        return chunk_index
    return 0


def _section_key_parts(chunk: dict) -> tuple[str, str]:
    section_title = chunk.get("section_title")
    if isinstance(section_title, str) and section_title.strip():
        normalized_title = re.sub(r"\s+", " ", section_title.strip())
        return _slugify(normalized_title), normalized_title

    page_number = chunk.get("page_number")
    if isinstance(page_number, int):
        return f"page-{page_number}", f"Page {page_number}"

    chunk_index = _chunk_index(chunk)
    return f"chunk-group-{chunk_index}", f"Chunk group {chunk_index}"


def _section_id(document_id: str, section_key: str) -> str:
    return f"{document_id}:section:{section_key}"


def _normalize_entity_name(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip()).casefold()


def _entity_dedupe_key(document_id: str, entity: EntityDraft) -> tuple[str, str, str]:
    return (document_id, _normalize_entity_name(entity.entity_name), entity.entity_type)


def _chunk_id_for_error(chunk: dict, exc: Exception) -> UUID | None:
    error_chunk_id = getattr(exc, "chunk_id", None)
    if isinstance(error_chunk_id, UUID):
        return error_chunk_id

    chunk_id = chunk.get("id")
    if chunk_id is None:
        return None

    try:
        return UUID(str(chunk_id))
    except ValueError:
        return None


def _safe_extraction_error(chunk: dict, exc: Exception) -> GraphBuildError:
    return _build_error(
        operation="extract_entities_for_chunk",
        message=(
            "Entity extraction failed for a document chunk; extracted graph data "
            "for that chunk was skipped."
        ),
        chunk_id=_chunk_id_for_error(chunk, exc),
        graph_rows_cleared=True,
        partial_state_risk=True,
    )


def _extract_chunk_graph_drafts(
    chunks: list[dict],
) -> tuple[list[_ChunkGraphDrafts], list[GraphBuildError]]:
    chunk_graph_drafts: list[_ChunkGraphDrafts] = []
    extraction_errors: list[GraphBuildError] = []

    for chunk in chunks:
        try:
            extraction_result = entity_extraction_service.extract_entities_for_chunk(
                chunk
            )
        except Exception as exc:
            extraction_errors.append(_safe_extraction_error(chunk, exc))
            continue

        entities = [
            entity
            for entity in getattr(extraction_result, "entities", [])
            if isinstance(entity, EntityDraft)
        ]
        relationships = [
            relationship
            for relationship in getattr(extraction_result, "relationships", [])
            if isinstance(relationship, RelationshipDraft)
        ]
        chunk_graph_drafts.append(
            _ChunkGraphDrafts(
                chunk=chunk,
                entities=entities,
                relationships=relationships,
            )
        )

    return chunk_graph_drafts, extraction_errors


def _extract_deduplicated_entities(
    document_id: str,
    chunk_graph_drafts: list[_ChunkGraphDrafts],
) -> list[EntityDraft]:
    deduped_entities: list[EntityDraft] = []
    seen_entities: set[tuple[str, str, str]] = set()

    for chunk_graph_draft in chunk_graph_drafts:
        for entity in chunk_graph_draft.entities:
            dedupe_key = _entity_dedupe_key(document_id, entity)
            if dedupe_key in seen_entities:
                continue

            seen_entities.add(dedupe_key)
            deduped_entities.append(entity)

    return deduped_entities


def _insert_document_entities(
    document_id: str,
    chunk_graph_drafts: list[_ChunkGraphDrafts],
    *,
    relationship_count: int = 0,
) -> list[dict]:
    entities = _extract_deduplicated_entities(document_id, chunk_graph_drafts)
    try:
        return supabase_service.insert_document_entities(document_id, entities)
    except Exception as exc:
        raise GraphBuildException(
            f"Graph build could not insert document entities: {document_id}.",
            _failure_result(
                document_id,
                _build_error(
                    operation="insert_document_entities",
                    message=(
                        "Failed to insert extracted document entities after graph "
                        "rows were cleared."
                    ),
                    graph_rows_cleared=True,
                    partial_state_risk=True,
                ),
                relationship_count=relationship_count,
                graph_rows_cleared=True,
                partial_state_risk=True,
            ),
        ) from exc


def _entity_id_by_dedupe_key(
    document_id: str,
    inserted_entities: list[dict],
) -> dict[tuple[str, str, str], str]:
    entity_ids: dict[tuple[str, str, str], str] = {}

    for entity in inserted_entities:
        entity_id = entity.get("id")
        entity_name = entity.get("entity_name")
        entity_type = entity.get("entity_type")
        if entity_id is None or not isinstance(entity_name, str):
            continue
        if not isinstance(entity_type, str):
            continue

        entity_ids[
            (document_id, _normalize_entity_name(entity_name), entity_type)
        ] = str(entity_id)

    return entity_ids


def _entity_ids_by_normalized_name(inserted_entities: list[dict]) -> dict[str, set[str]]:
    entity_ids: dict[str, set[str]] = {}

    for entity in inserted_entities:
        entity_id = entity.get("id")
        entity_name = entity.get("entity_name")
        if entity_id is None or not isinstance(entity_name, str):
            continue

        normalized_name = _normalize_entity_name(entity_name)
        entity_ids.setdefault(normalized_name, set()).add(str(entity_id))

    return entity_ids


def _resolve_entity_id(
    endpoint_name: str,
    entity_ids_by_name: dict[str, set[str]],
) -> str | None:
    entity_ids = entity_ids_by_name.get(_normalize_entity_name(endpoint_name), set())
    if len(entity_ids) != 1:
        return None

    return next(iter(entity_ids))


def _build_chunk_entity_relationships(
    document_id: str,
    chunk_graph_drafts: list[_ChunkGraphDrafts],
    entity_ids_by_key: dict[tuple[str, str, str], str],
) -> list[RelationshipDraft]:
    relationships: list[RelationshipDraft] = []

    for chunk_graph_draft in chunk_graph_drafts:
        for entity in chunk_graph_draft.entities:
            entity_id = entity_ids_by_key.get(_entity_dedupe_key(document_id, entity))
            if entity_id is None:
                continue

            relationships.append(
                RelationshipDraft(
                    source_type="chunk",
                    source_id=str(entity.chunk_id),
                    target_type="entity",
                    target_id=entity_id,
                    relationship_type="chunk_mentions_entity",
                    weight=1.0,
                    description=f"Chunk mentions entity {entity.entity_name}.",
                )
            )

    return relationships


def _entity_relation_description(relationship: RelationshipDraft) -> str | None:
    if relationship.relationship_type == "entity_related_to_entity":
        return relationship.description

    if relationship.description:
        return f"{relationship.relationship_type}: {relationship.description}"

    return f"Extracted {relationship.relationship_type} relation."


def _build_entity_entity_relationships(
    chunk_graph_drafts: list[_ChunkGraphDrafts],
    entity_ids_by_name: dict[str, set[str]],
) -> list[RelationshipDraft]:
    relationships: list[RelationshipDraft] = []

    for chunk_graph_draft in chunk_graph_drafts:
        for extracted_relationship in chunk_graph_draft.relationships:
            if (
                extracted_relationship.source_type != "entity"
                or extracted_relationship.target_type != "entity"
            ):
                continue

            source_id = _resolve_entity_id(
                extracted_relationship.source_id,
                entity_ids_by_name,
            )
            target_id = _resolve_entity_id(
                extracted_relationship.target_id,
                entity_ids_by_name,
            )
            if source_id is None or target_id is None or source_id == target_id:
                continue

            relationships.append(
                RelationshipDraft(
                    source_type="entity",
                    source_id=source_id,
                    target_type="entity",
                    target_id=target_id,
                    relationship_type="entity_related_to_entity",
                    weight=extracted_relationship.weight,
                    description=_entity_relation_description(extracted_relationship),
                )
            )

    return relationships


def _chunk_entity_keys(
    document_id: str,
    chunk_graph_draft: _ChunkGraphDrafts,
) -> set[tuple[str, str, str]]:
    return {
        _entity_dedupe_key(document_id, entity)
        for entity in chunk_graph_draft.entities
    }


def _chunk_overlap_weight(
    source_entity_keys: set[tuple[str, str, str]],
    target_entity_keys: set[tuple[str, str, str]],
) -> float | None:
    shared_entity_count = len(source_entity_keys.intersection(target_entity_keys))
    if shared_entity_count < _CHUNK_OVERLAP_MIN_SHARED_ENTITIES:
        return None

    all_entity_count = len(source_entity_keys.union(target_entity_keys))
    if all_entity_count == 0:
        return None

    weight = shared_entity_count / all_entity_count
    if weight < _CHUNK_OVERLAP_MIN_WEIGHT:
        return None

    return round(weight, 4)


def _build_chunk_chunk_relationships(
    document_id: str,
    chunk_graph_drafts: list[_ChunkGraphDrafts],
) -> list[RelationshipDraft]:
    relationships: list[RelationshipDraft] = []
    chunk_entity_keys = [
        (
            str(chunk_graph_draft.chunk["id"]),
            _chunk_entity_keys(document_id, chunk_graph_draft),
        )
        for chunk_graph_draft in chunk_graph_drafts
    ]
    seen_chunk_pairs: set[tuple[str, str]] = set()

    for source_index, (source_chunk_id, source_entity_keys) in enumerate(
        chunk_entity_keys
    ):
        for target_chunk_id, target_entity_keys in chunk_entity_keys[source_index + 1 :]:
            if source_chunk_id == target_chunk_id:
                continue

            source_id, target_id = sorted((source_chunk_id, target_chunk_id))
            chunk_pair = (source_id, target_id)
            if chunk_pair in seen_chunk_pairs:
                continue

            weight = _chunk_overlap_weight(source_entity_keys, target_entity_keys)
            if weight is None:
                continue

            seen_chunk_pairs.add(chunk_pair)
            relationships.append(
                RelationshipDraft(
                    source_type="chunk",
                    source_id=source_id,
                    target_type="chunk",
                    target_id=target_id,
                    relationship_type="chunk_related_to_chunk",
                    weight=weight,
                    description=(
                        "Chunks share strong de-duplicated entity overlap."
                    ),
                )
            )

    return relationships


def _build_entity_relationships(
    document_id: str,
    chunk_graph_drafts: list[_ChunkGraphDrafts],
    inserted_entities: list[dict],
) -> list[RelationshipDraft]:
    entity_ids_by_key = _entity_id_by_dedupe_key(document_id, inserted_entities)
    entity_ids_by_name = _entity_ids_by_normalized_name(inserted_entities)

    return [
        *_build_chunk_entity_relationships(
            document_id,
            chunk_graph_drafts,
            entity_ids_by_key,
        ),
        *_build_entity_entity_relationships(chunk_graph_drafts, entity_ids_by_name),
        *_build_chunk_chunk_relationships(document_id, chunk_graph_drafts),
    ]


def _insert_entity_relationships(
    document_id: str,
    chunk_graph_drafts: list[_ChunkGraphDrafts],
    inserted_entities: list[dict],
    *,
    relationship_count: int = 0,
) -> list[dict]:
    relationships = _build_entity_relationships(
        document_id,
        chunk_graph_drafts,
        inserted_entities,
    )
    if not relationships:
        return []

    try:
        return supabase_service.insert_document_relationships(document_id, relationships)
    except Exception as exc:
        raise GraphBuildException(
            f"Graph build could not insert entity relationships: {document_id}.",
            _failure_result(
                document_id,
                _build_error(
                    operation="insert_entity_relationships",
                    message=(
                        "Failed to insert chunk-entity or entity-entity "
                        "relationships after graph rows were cleared."
                    ),
                    graph_rows_cleared=True,
                    partial_state_risk=True,
                ),
                entity_count=len(inserted_entities),
                relationship_count=relationship_count,
                graph_rows_cleared=True,
                partial_state_risk=True,
            ),
        ) from exc


def _build_structural_relationships(
    document_id: str,
    chunks: list[dict],
) -> list[RelationshipDraft]:
    sections: dict[str, str] = {}
    chunk_section_pairs: list[tuple[dict, str, str]] = []

    for chunk in chunks:
        section_key, section_label = _section_key_parts(chunk)
        sections.setdefault(section_key, section_label)
        chunk_section_pairs.append((chunk, section_key, section_label))

    relationships = [
        RelationshipDraft(
            source_type="document",
            source_id=document_id,
            target_type="section",
            target_id=_section_id(document_id, section_key),
            relationship_type="document_contains_section",
            weight=1.0,
            description=f"Document contains section {section_label}.",
        )
        for section_key, section_label in sections.items()
    ]

    relationships.extend(
        RelationshipDraft(
            source_type="section",
            source_id=_section_id(document_id, section_key),
            target_type="chunk",
            target_id=str(chunk["id"]),
            relationship_type="section_contains_chunk",
            weight=1.0,
            description=f"Section {section_label} contains chunk {_chunk_index(chunk)}.",
        )
        for chunk, section_key, section_label in chunk_section_pairs
    )

    return relationships


def _insert_structural_relationships(
    document_id: str,
    chunks: list[dict],
) -> list[dict]:
    relationships = _build_structural_relationships(document_id, chunks)
    try:
        return supabase_service.insert_document_relationships(document_id, relationships)
    except Exception as exc:
        raise GraphBuildException(
            f"Graph build could not insert structural relationships: {document_id}.",
            _failure_result(
                document_id,
                _build_error(
                    operation="insert_structural_relationships",
                    message=(
                        "Failed to insert document-section or section-chunk "
                        "relationships after graph rows were cleared."
                    ),
                    graph_rows_cleared=True,
                    partial_state_risk=True,
                ),
                graph_rows_cleared=True,
                partial_state_risk=True,
            ),
        ) from exc


def build_document_graph(document_id: str) -> GraphBuildResult:
    document = supabase_service.get_graph_document(document_id)
    if document is None:
        _raise_not_found(document_id)

    chunks = supabase_service.list_document_chunks(document_id)
    if not chunks:
        _raise_no_chunks(document_id)

    _clear_existing_graph_rows(document_id)
    chunk_graph_drafts, extraction_errors = _extract_chunk_graph_drafts(chunks)
    inserted_relationships = _insert_structural_relationships(document_id, chunks)
    inserted_entities = _insert_document_entities(
        document_id,
        chunk_graph_drafts,
        relationship_count=len(inserted_relationships),
    )
    inserted_entity_relationships = _insert_entity_relationships(
        document_id,
        chunk_graph_drafts,
        inserted_entities,
        relationship_count=len(inserted_relationships),
    )

    return _build_result(
        document_id,
        entity_count=len(inserted_entities),
        relationship_count=(
            len(inserted_relationships) + len(inserted_entity_relationships)
        ),
        errors=extraction_errors,
        graph_rows_cleared=True,
        partial_state_risk=bool(extraction_errors),
    )
