from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.schemas.parsing import ParsedSection
from app.services.chunking_service import chunk_sections
from app.services.document_parser import parse_document
from app.services.supabase_service import (
    download_original_document_file,
    get_processing_document,
    insert_document_chunks,
    update_document_chunk_count,
    update_document_status,
)


class DocumentProcessingError(RuntimeError):
    """Raised when document processing cannot continue."""


class DocumentProcessingResult(BaseModel):
    document_id: UUID
    status: Literal["ready"] = "ready"
    chunk_count: int = Field(ge=0)


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


def process_document(document_id: UUID) -> DocumentProcessingResult:
    """Parse, chunk, persist, and mark one uploaded document ready."""
    settings = get_settings()
    document = get_processing_document(str(document_id))
    if document is None:
        raise DocumentProcessingError("Document not found.")

    file_name = _require_document_field(document, "file_name")
    file_type = _require_document_field(document, "file_type")
    storage_path = _require_document_field(document, "storage_path")

    update_document_status(str(document_id), "processing", error_message=None)

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

    inserted_chunks = insert_document_chunks(str(document_id), chunks)
    chunk_count = len(inserted_chunks)
    update_document_chunk_count(str(document_id), chunk_count)
    update_document_status(str(document_id), "ready", error_message=None)

    return DocumentProcessingResult(
        document_id=document_id,
        chunk_count=chunk_count,
    )


__all__ = [
    "DocumentProcessingError",
    "DocumentProcessingResult",
    "process_document",
]
