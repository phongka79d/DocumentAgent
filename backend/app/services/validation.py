from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.core.config import get_settings

SUPPORTED_UPLOAD_EXTENSIONS = {
    ".pdf",
    ".docx",
    ".txt",
    ".md",
    ".markdown",
}

PDF_MIME_TYPE = "application/pdf"
DOCX_MIME_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
OCTET_STREAM_MIME_TYPE = "application/octet-stream"
MARKDOWN_MIME_TYPES = {
    "application/markdown",
    "text/markdown",
    "text/x-markdown",
}


class UploadValidationError(ValueError):
    """Raised when an upload fails deterministic validation."""


@dataclass(frozen=True, slots=True)
class UploadValidationResult:
    file_name: str
    extension: str
    file_size: int
    content_type: str | None


def _normalize_content_type(content_type: str | None) -> str | None:
    if content_type is None:
        return None

    normalized = content_type.split(";", 1)[0].strip().lower()
    return normalized or None


def _resolve_max_upload_bytes(max_upload_bytes: int | None) -> int:
    if max_upload_bytes is not None:
        return max_upload_bytes

    return get_settings().MAX_UPLOAD_BYTES


def _is_mime_type_compatible(extension: str, content_type: str | None) -> bool:
    if content_type is None or content_type == OCTET_STREAM_MIME_TYPE:
        return True

    if extension == ".pdf":
        return content_type == PDF_MIME_TYPE

    if extension == ".docx":
        return content_type == DOCX_MIME_TYPE

    if extension == ".txt":
        return content_type.startswith("text/")

    if extension in {".md", ".markdown"}:
        return content_type.startswith("text/") or content_type in MARKDOWN_MIME_TYPES

    return False


def validate_upload_file(
    *,
    file_name: str,
    file_bytes: bytes,
    content_type: str | None = None,
    max_upload_bytes: int | None = None,
) -> UploadValidationResult:
    normalized_name = Path(file_name).name.strip()
    normalized_extension = Path(normalized_name).suffix.lower()
    normalized_content_type = _normalize_content_type(content_type)
    file_size = len(file_bytes)
    max_bytes = _resolve_max_upload_bytes(max_upload_bytes)

    if file_size == 0:
        raise UploadValidationError("Uploaded file is empty")

    if file_size > max_bytes:
        raise UploadValidationError(
            f"Uploaded file exceeds maximum size of {max_bytes} bytes"
        )

    if normalized_extension not in SUPPORTED_UPLOAD_EXTENSIONS:
        raise UploadValidationError(
            f"Unsupported file extension: {normalized_extension or '<missing>'}"
        )

    if not _is_mime_type_compatible(normalized_extension, normalized_content_type):
        raise UploadValidationError(
            "File extension "
            f"{normalized_extension} is incompatible with MIME type "
            f"{normalized_content_type}"
        )

    return UploadValidationResult(
        file_name=normalized_name,
        extension=normalized_extension,
        file_size=file_size,
        content_type=normalized_content_type,
    )
