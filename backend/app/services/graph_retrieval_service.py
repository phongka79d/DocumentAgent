import logging
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID

from app.core.config import get_settings
from app.services import supabase_service
from app.utils.scoring import clamp_score


MIN_TOP_K = 1
MAX_TOP_K = 50

logger = logging.getLogger(__name__)

_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


class GraphRetrievalValidationError(ValueError):
    """Raised when graph retrieval input is invalid."""


class GraphRetrievalDependencyError(RuntimeError):
    """Raised when graph retrieval cannot safely complete because of a dependency."""

    def __init__(self, public_message: str) -> None:
        self.public_message = public_message
        super().__init__(public_message)


@dataclass(frozen=True)
class GraphRetrievalCandidate:
    """Graph-side candidate shape consumed later by hybrid merge logic."""

    chunk_id: UUID
    document_id: UUID
    content: str | None = None
    file_name: str | None = None
    file_type: str | None = None
    page_number: int | None = None
    section_title: str | None = None
    chunk_index: int | None = None
    graph_relevance: float = 0.0
    retrieval_reason: str | None = None
    metadata: dict[str, Any] | None = None


@dataclass(frozen=True)
class _GraphPathEvidence:
    chunk_id: UUID
    document_id: UUID
    matched_entity_id: UUID | None
    matched_entity_name: str
    entity_match_strength: float
    path_type: str
    path_depth: int
    relationship_ids: tuple[str, ...] = ()
    relationship_types: tuple[str, ...] = ()
    relationship_weight: float | None = None


class GraphRowsRepository(Protocol):
    """Repository contract for persisted Plan 7 graph rows."""

    def list_document_entities(
        self,
        document_ids: Sequence[UUID] | None,
    ) -> list[Mapping[str, Any]]:
        """Return rows from document_entities filtered to the current user."""

    def list_document_relationships(
        self,
        document_ids: Sequence[UUID],
    ) -> list[Mapping[str, Any]]:
        """Return rows from document_relationships for selected documents."""

    def list_document_chunks_by_ids(
        self,
        chunk_ids: Sequence[UUID],
    ) -> list[Mapping[str, Any]]:
        """Return chunk rows needed to build mergeable graph candidates."""


class SupabaseGraphRowsRepository:
    """Default graph row repository backed by Supabase."""

    def list_document_entities(
        self,
        document_ids: Sequence[UUID] | None,
    ) -> list[Mapping[str, Any]]:
        client = supabase_service.get_supabase_client()
        try:
            query = (
                client.table("document_entities")
                .select("id, document_id, chunk_id, entity_name, entity_type, description")
                .eq("user_id", get_settings().single_user_id)
            )
            if document_ids:
                query = query.in_("document_id", [str(document_id) for document_id in document_ids])
            response = query.execute()
        except Exception as exc:
            raise GraphRetrievalDependencyError(
                "Graph retrieval is temporarily unavailable."
            ) from exc

        return _response_rows(response)

    def list_document_relationships(
        self,
        document_ids: Sequence[UUID],
    ) -> list[Mapping[str, Any]]:
        if not document_ids:
            return []

        client = supabase_service.get_supabase_client()
        try:
            response = (
                client.table("document_relationships")
                .select(
                    "id, document_id, source_type, source_id, target_type, "
                    "target_id, relationship_type, weight, description"
                )
                .in_("document_id", [str(document_id) for document_id in document_ids])
                .execute()
            )
        except Exception as exc:
            raise GraphRetrievalDependencyError(
                "Graph retrieval is temporarily unavailable."
            ) from exc

        return _response_rows(response)

    def list_document_chunks_by_ids(
        self,
        chunk_ids: Sequence[UUID],
    ) -> list[Mapping[str, Any]]:
        if not chunk_ids:
            return []

        client = supabase_service.get_supabase_client()
        try:
            response = (
                client.table("document_chunks")
                .select(
                    "id, document_id, chunk_index, content, page_number, section_title"
                )
                .in_("id", [str(chunk_id) for chunk_id in chunk_ids])
                .eq("user_id", get_settings().single_user_id)
                .execute()
            )
        except Exception as exc:
            raise GraphRetrievalDependencyError(
                "Graph retrieval is temporarily unavailable."
            ) from exc

        return _response_rows(response)


def find_graph_candidates(
    question: str,
    document_ids: list[UUID] | None = None,
    top_k: int | None = None,
    *,
    repository: GraphRowsRepository | None = None,
) -> list[GraphRetrievalCandidate]:
    """Return graph retrieval candidates in a mergeable chunk_id-keyed shape.

    This service uses deterministic entity-name matching and bounded graph
    expansion. Graph relevance is computed from entity match strength,
    relationship weight, and the number of graph paths, then clamped to the
    normalized 0.0 to 1.0 range.
    """

    question_terms = _extract_question_terms(question)
    if not question_terms:
        return []

    resolved_top_k = _resolve_top_k(top_k)
    graph_repository = repository or SupabaseGraphRowsRepository()

    entity_rows = graph_repository.list_document_entities(document_ids)
    relationship_document_ids = _relationship_document_ids(document_ids, entity_rows)
    relationship_rows = graph_repository.list_document_relationships(
        relationship_document_ids
    )

    logger.debug(
        "Loaded graph rows for candidate lookup. entity_rows=%s relationship_rows=%s top_k=%s",
        len(entity_rows),
        len(relationship_rows),
        resolved_top_k,
    )

    matched_entities = _match_entity_rows(
        question_terms=question_terms,
        entity_rows=entity_rows,
        document_ids=document_ids,
    )
    graph_evidence = _expand_matched_entities_to_chunk_evidence(
        matched_entities=matched_entities,
        relationship_rows=relationship_rows,
        document_ids=document_ids,
    )
    chunk_rows = graph_repository.list_document_chunks_by_ids(list(graph_evidence))
    return _chunk_evidence_to_candidates(
        graph_evidence=graph_evidence,
        chunk_rows=chunk_rows,
        document_ids=document_ids,
    )[:resolved_top_k]


def _resolve_top_k(top_k: int | None) -> int:
    resolved_top_k = get_settings().retrieval_graph_top_k if top_k is None else top_k
    if resolved_top_k < MIN_TOP_K or resolved_top_k > MAX_TOP_K:
        raise GraphRetrievalValidationError("top_k must be between 1 and 50.")

    return resolved_top_k


def _relationship_document_ids(
    document_ids: Sequence[UUID] | None,
    entity_rows: Sequence[Mapping[str, Any]],
) -> list[UUID]:
    if document_ids is not None:
        return list(document_ids)

    discovered_ids: list[UUID] = []
    seen: set[UUID] = set()
    for row in entity_rows:
        document_id = _uuid_or_none(row.get("document_id"))
        if document_id is not None and document_id not in seen:
            discovered_ids.append(document_id)
            seen.add(document_id)

    return discovered_ids


@dataclass(frozen=True)
class _MatchedEntity:
    row: Mapping[str, Any]
    document_id: UUID
    chunk_id: UUID
    entity_id: UUID | None
    entity_name: str
    entity_terms: list[str]
    match_score: float


def _extract_question_terms(question: str) -> set[str]:
    return set(_TOKEN_PATTERN.findall(question.lower()))


def _entity_terms(entity_name: str) -> list[str]:
    terms = _TOKEN_PATTERN.findall(entity_name.lower())
    seen: set[str] = set()
    unique_terms: list[str] = []
    for term in terms:
        if term not in seen:
            unique_terms.append(term)
            seen.add(term)
    return unique_terms


def _match_entity_rows(
    *,
    question_terms: set[str],
    entity_rows: Sequence[Mapping[str, Any]],
    document_ids: Sequence[UUID] | None,
) -> list[_MatchedEntity]:
    selected_document_ids = set(document_ids or [])
    matched_entities: list[_MatchedEntity] = []

    for row in entity_rows:
        document_id = _uuid_or_none(row.get("document_id"))
        chunk_id = _uuid_or_none(row.get("chunk_id"))
        entity_name = row.get("entity_name")
        if document_id is None or chunk_id is None or not isinstance(entity_name, str):
            continue
        if selected_document_ids and document_id not in selected_document_ids:
            continue

        terms = _entity_terms(entity_name)
        if not terms:
            continue

        matched_terms = [term for term in terms if term in question_terms]
        if len(matched_terms) != len(terms):
            continue

        matched_entities.append(
            _MatchedEntity(
                row=row,
                document_id=document_id,
                chunk_id=chunk_id,
                entity_id=_uuid_or_none(row.get("id")),
                entity_name=entity_name.strip(),
                entity_terms=terms,
                match_score=len(matched_terms) / len(terms),
            )
        )

    return sorted(
        matched_entities,
        key=lambda match: (-match.match_score, match.entity_name.lower(), str(match.chunk_id)),
    )


def _expand_matched_entities_to_chunk_evidence(
    *,
    matched_entities: Sequence[_MatchedEntity],
    relationship_rows: Sequence[Mapping[str, Any]],
    document_ids: Sequence[UUID] | None,
) -> dict[UUID, list[_GraphPathEvidence]]:
    evidence_by_chunk: dict[UUID, list[_GraphPathEvidence]] = {}
    for match in matched_entities:
        _append_unique_evidence(
            evidence_by_chunk,
            _GraphPathEvidence(
                chunk_id=match.chunk_id,
                document_id=match.document_id,
                matched_entity_id=match.entity_id,
                matched_entity_name=match.entity_name,
                entity_match_strength=match.match_score,
                path_type="matched_entity_chunk",
                path_depth=0,
            )
        )

    relationship_graph = _relationship_graph(relationship_rows, document_ids)
    for match in matched_entities:
        if match.entity_id is None:
            continue

        start_node = ("entity", match.entity_id)
        for path in _relationship_paths_to_chunks(
            start_node=start_node,
            relationship_graph=relationship_graph,
            max_depth=2,
        ):
            chunk_node_type, chunk_id = path[-1]["to_node"]
            if chunk_node_type != "chunk":
                continue

            _append_unique_evidence(
                evidence_by_chunk,
                _GraphPathEvidence(
                    chunk_id=chunk_id,
                    document_id=match.document_id,
                    matched_entity_id=match.entity_id,
                    matched_entity_name=match.entity_name,
                    entity_match_strength=match.match_score,
                    path_type="relationship_path",
                    path_depth=len(path),
                    relationship_ids=tuple(str(edge.get("id")) for edge in path),
                    relationship_types=tuple(
                        str(edge.get("relationship_type")) for edge in path
                    ),
                    relationship_weight=_path_weight(path),
                ),
            )

    return evidence_by_chunk


def _append_unique_evidence(
    evidence_by_chunk: dict[UUID, list[_GraphPathEvidence]],
    evidence: _GraphPathEvidence,
) -> None:
    existing = evidence_by_chunk.setdefault(evidence.chunk_id, [])
    if evidence not in existing:
        existing.append(evidence)


def _relationship_graph(
    relationship_rows: Sequence[Mapping[str, Any]],
    document_ids: Sequence[UUID] | None,
) -> dict[tuple[str, UUID], list[dict[str, Any]]]:
    selected_document_ids = set(document_ids or [])
    graph: dict[tuple[str, UUID], list[dict[str, Any]]] = {}

    for row in relationship_rows:
        document_id = _uuid_or_none(row.get("document_id"))
        if document_id is None:
            continue
        if selected_document_ids and document_id not in selected_document_ids:
            continue

        source_node = _relationship_node(row.get("source_type"), row.get("source_id"))
        target_node = _relationship_node(row.get("target_type"), row.get("target_id"))
        if source_node is None or target_node is None:
            continue

        graph.setdefault(source_node, []).append(
            {
                "id": row.get("id"),
                "document_id": document_id,
                "relationship_type": row.get("relationship_type"),
                "weight": row.get("weight"),
                "from_node": source_node,
                "to_node": target_node,
            }
        )
        graph.setdefault(target_node, []).append(
            {
                "id": row.get("id"),
                "document_id": document_id,
                "relationship_type": row.get("relationship_type"),
                "weight": row.get("weight"),
                "from_node": target_node,
                "to_node": source_node,
            }
        )

    return graph


def _relationship_node(node_type: Any, node_id: Any) -> tuple[str, UUID] | None:
    if not isinstance(node_type, str):
        return None

    normalized_type = node_type.strip().lower()
    if normalized_type not in {"entity", "chunk"}:
        return None

    parsed_id = _uuid_or_none(node_id)
    if parsed_id is None:
        return None

    return normalized_type, parsed_id


def _relationship_paths_to_chunks(
    *,
    start_node: tuple[str, UUID],
    relationship_graph: Mapping[tuple[str, UUID], Sequence[dict[str, Any]]],
    max_depth: int,
) -> list[list[dict[str, Any]]]:
    paths: list[list[dict[str, Any]]] = []
    queue: list[tuple[tuple[str, UUID], list[dict[str, Any]], set[tuple[str, UUID]]]] = [
        (start_node, [], {start_node})
    ]

    while queue:
        node, path, visited = queue.pop(0)
        if len(path) >= max_depth:
            continue

        for edge in relationship_graph.get(node, []):
            next_node = edge["to_node"]
            if next_node in visited:
                continue

            next_path = [*path, edge]
            if next_node[0] == "chunk":
                paths.append(next_path)

            queue.append((next_node, next_path, {*visited, next_node}))

    return paths


def _path_weight(path: Sequence[Mapping[str, Any]]) -> float | None:
    weights: list[float] = []
    for edge in path:
        weight = edge.get("weight")
        if isinstance(weight, (int, float)):
            weights.append(float(weight))

    if not weights:
        return None

    return min(max(sum(weights) / len(weights), 0.0), 1.0)


def _chunk_evidence_to_candidates(
    *,
    graph_evidence: Mapping[UUID, Sequence[_GraphPathEvidence]],
    chunk_rows: Sequence[Mapping[str, Any]],
    document_ids: Sequence[UUID] | None,
) -> list[GraphRetrievalCandidate]:
    selected_document_ids = set(document_ids or [])
    chunks_by_id = {
        chunk_id: row
        for row in chunk_rows
        if (chunk_id := _uuid_or_none(row.get("id"))) is not None
    }
    candidates: list[GraphRetrievalCandidate] = []

    for chunk_id, evidence_items in graph_evidence.items():
        if not evidence_items:
            continue

        chunk_row = chunks_by_id.get(chunk_id, {})
        document_id = _uuid_or_none(chunk_row.get("document_id")) or evidence_items[0].document_id
        if selected_document_ids and document_id not in selected_document_ids:
            continue

        metadata = _candidate_metadata(evidence_items)
        metadata.update(_chunk_metadata(chunk_row))
        graph_relevance = _graph_relevance(evidence_items)
        candidates.append(
            GraphRetrievalCandidate(
                chunk_id=chunk_id,
                document_id=document_id,
                content=_string_or_none(chunk_row.get("content")),
                page_number=_int_or_none(chunk_row.get("page_number")),
                section_title=_string_or_none(chunk_row.get("section_title")),
                chunk_index=_int_or_none(chunk_row.get("chunk_index")),
                graph_relevance=graph_relevance,
                retrieval_reason=_retrieval_reason(evidence_items),
                metadata=metadata,
            )
        )

    return sorted(
        candidates,
        key=lambda candidate: (
            -candidate.graph_relevance,
            -len(candidate.metadata.get("graph_evidence", []) if candidate.metadata else []),
            candidate.chunk_index if candidate.chunk_index is not None else 10**9,
            str(candidate.chunk_id),
        ),
    )


def _graph_relevance(evidence_items: Sequence[_GraphPathEvidence]) -> float:
    if not evidence_items:
        return 0.0

    path_scores = [_graph_path_score(item) for item in evidence_items]
    average_path_score = sum(path_scores) / len(path_scores)
    path_count_bonus = clamp_score(max(len(evidence_items) - 1, 0) / 4.0)
    return clamp_score((0.8 * average_path_score) + (0.2 * path_count_bonus))


def _graph_path_score(evidence: _GraphPathEvidence) -> float:
    entity_match_strength = clamp_score(evidence.entity_match_strength)
    relationship_weight = clamp_score(evidence.relationship_weight)
    path_depth_score = clamp_score(1.0 / (1.0 + max(evidence.path_depth, 0)))
    return clamp_score(
        (0.6 * entity_match_strength)
        + (0.25 * relationship_weight)
        + (0.15 * path_depth_score)
    )


def _candidate_metadata(
    evidence_items: Sequence[_GraphPathEvidence],
) -> dict[str, Any]:
    first = evidence_items[0]
    return {
        "matched_entity_id": str(first.matched_entity_id)
        if first.matched_entity_id is not None
        else None,
        "matched_entity_name": first.matched_entity_name,
        "graph_path_count": len(evidence_items),
        "graph_evidence": [
            {
                "matched_entity_id": str(item.matched_entity_id)
                if item.matched_entity_id is not None
                else None,
                "matched_entity_name": item.matched_entity_name,
                "path_type": item.path_type,
                "path_depth": item.path_depth,
                "relationship_ids": list(item.relationship_ids),
                "relationship_types": list(item.relationship_types),
                "relationship_weight": item.relationship_weight,
            }
            for item in evidence_items
        ],
    }


def _chunk_metadata(chunk_row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "chunk_index": _int_or_none(chunk_row.get("chunk_index")),
        "page_number": _int_or_none(chunk_row.get("page_number")),
        "section_title": _string_or_none(chunk_row.get("section_title")),
    }


def _retrieval_reason(evidence_items: Sequence[_GraphPathEvidence]) -> str:
    first = evidence_items[0]
    if any(item.path_type == "relationship_path" for item in evidence_items):
        return f"Graph relationship path from matched entity: {first.matched_entity_name}"

    return f"Matched entity: {first.matched_entity_name}"


def _string_or_none(value: Any) -> str | None:
    if isinstance(value, str):
        return value

    return None


def _int_or_none(value: Any) -> int | None:
    if isinstance(value, int):
        return value

    return None


def _response_rows(response: object) -> list[Mapping[str, Any]]:
    rows = getattr(response, "data", None) or []
    if not isinstance(rows, list):
        return []

    return [row for row in rows if isinstance(row, Mapping)]


def _uuid_or_none(value: Any) -> UUID | None:
    if value is None:
        return None

    try:
        return UUID(str(value))
    except (TypeError, ValueError):
        return None
