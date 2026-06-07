import re
import unicodedata
from uuid import UUID

from app.schemas.graph import GraphBuildError, GraphBuildResult, RelationshipDraft
from app.services import supabase_service


class GraphBuildException(RuntimeError):
    """Raised when graph build preflight cannot proceed safely."""

    def __init__(self, message: str, result: GraphBuildResult) -> None:
        super().__init__(message)
        self.result = result


def _empty_result(document_id: str, error: GraphBuildError | None = None) -> GraphBuildResult:
    errors = [error] if error is not None else []
    return GraphBuildResult(
        document_id=UUID(document_id),
        entity_count=0,
        relationship_count=0,
        errors=errors,
    )


def _build_error(
    operation: str,
    message: str,
    *,
    graph_rows_cleared: bool = False,
    partial_state_risk: bool = False,
) -> GraphBuildError:
    return GraphBuildError(
        operation=operation,
        message=message,
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
            _empty_result(
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
    inserted_relationships = _insert_structural_relationships(document_id, chunks)

    return GraphBuildResult(
        document_id=UUID(document_id),
        entity_count=0,
        relationship_count=len(inserted_relationships),
        errors=[],
    )
