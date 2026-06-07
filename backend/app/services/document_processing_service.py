from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.schemas.parsing import ParsedSection
from app.services.chunking_service import chunk_sections
from app.services.document_parser import (
    DocumentDecodingError,
    DocumentParserError,
    EmptyDocumentError,
    UnsupportedDocumentTypeError,
    parse_document,
)
from app.services.supabase_service import (
    SupabaseConnectionError,
    download_original_document_file,
    get_processing_document,
    insert_document_chunks,
    update_document_chunk_count,
    update_document_status,
)
from app.services import graph_builder


class DocumentProcessingError(RuntimeError):
    """Raised when document processing cannot continue."""


class EmptyChunksError(DocumentProcessingError):
    """Raised when parsing or chunking produces no chunks to persist."""


class DocumentProcessingResult(BaseModel):
    document_id: UUID
    status: Literal["ready"] = "ready"
    chunk_count: int = Field(ge=0)
    graph_entity_count: int = Field(default=0, ge=0)
    graph_relationship_count: int = Field(default=0, ge=0)
    graph_error_count: int = Field(default=0, ge=0)


def _require_document_field(document: dict, field_name: str) -> str:
    value = document.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise DocumentProcessingError(
            f"Document row is missing required field '{field_name}'."
        )

    return value


def _attach_processing_metadata(
    *,
    sections: list[ParsedSection],
    document_id: UUID,
    user_id: str,
    file_name: str,
) -> list[ParsedSection]:
    enriched_sections: list[ParsedSection] = []
    for section in sections:
        metadata = dict(section.metadata)
        metadata.update(
            {
                "document_id": str(document_id),
                "user_id": user_id,
                "file_name": section.file_name or file_name,
            }
        )

        enriched_sections.append(
            section.model_copy(
                update={
                    "file_name": section.file_name or file_name,
                    "metadata": metadata,
                }
            )
        )

    return enriched_sections


def _fail_document_processing(document_id: str, error_message: str) -> None:
    update_document_status(document_id, "failed", error_message=error_message)


def _safe_parser_error_message(exc: DocumentParserError) -> str:
    if isinstance(exc, EmptyDocumentError):
        return "Parsed document is empty."
    if isinstance(exc, UnsupportedDocumentTypeError):
        return "Unsupported document type."
    if isinstance(exc, DocumentDecodingError):
        return str(exc)[:200]

    return "Document parser failed."


def _safe_processing_error_message(exc: Exception) -> str:
    if isinstance(exc, DocumentParserError):
        return _safe_parser_error_message(exc)
    if isinstance(exc, EmptyChunksError):
        return str(exc)
    if isinstance(exc, graph_builder.GraphBuildException):
        return "Document graph build failed."
    if isinstance(exc, SupabaseConnectionError):
        return "Document storage or persistence operation failed."
    if isinstance(exc, DocumentProcessingError):
        return str(exc)[:200]

    return "Document processing failed."


def process_document(document_id: UUID) -> DocumentProcessingResult:
    """Parse, chunk, persist, and mark one uploaded document ready."""
    settings = get_settings()
    document_id_text = str(document_id)
    document = get_processing_document(document_id_text)
    if document is None:
        raise DocumentProcessingError("Document not found.")

    update_document_status(document_id_text, "processing", error_message=None)

    try:
        file_name = _require_document_field(document, "file_name")
        file_type = _require_document_field(document, "file_type")
        storage_path = _require_document_field(document, "storage_path")

        file_bytes = download_original_document_file(storage_path)
        parsed_sections = parse_document(file_bytes, file_type, file_name)
        parsed_sections = _attach_processing_metadata(
            sections=parsed_sections,
            document_id=document_id,
            user_id=settings.single_user_id,
            file_name=file_name,
        )
        chunks = chunk_sections(
            parsed_sections,
            settings.chunk_size_tokens,
            settings.chunk_overlap_tokens,
        )
        if not chunks:
            raise EmptyChunksError("Parsed document produced no chunks.")

        inserted_chunks = insert_document_chunks(document_id_text, chunks)
        chunk_count = len(inserted_chunks)
        if chunk_count == 0:
            raise EmptyChunksError("Chunk persistence returned no chunks.")

        update_document_chunk_count(document_id_text, chunk_count)
        graph_result = graph_builder.build_document_graph(document_id_text)
        update_document_status(document_id_text, "ready", error_message=None)
    except Exception as exc:
        error_message = _safe_processing_error_message(exc)
        try:
            _fail_document_processing(document_id_text, error_message)
        except Exception as status_exc:
            raise DocumentProcessingError(
                "Document processing failed and failed status could not be saved."
            ) from status_exc

        raise DocumentProcessingError(error_message) from exc

    return DocumentProcessingResult(
        document_id=document_id,
        chunk_count=chunk_count,
        graph_entity_count=graph_result.entity_count,
        graph_relationship_count=graph_result.relationship_count,
        graph_error_count=len(graph_result.errors),
    )


__all__ = [
    "DocumentProcessingError",
    "DocumentProcessingResult",
    "EmptyChunksError",
    "process_document",
]
