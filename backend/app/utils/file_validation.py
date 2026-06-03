from dataclasses import dataclass
from inspect import isawaitable
from pathlib import Path
import re
from typing import Any


SUPPORTED_DOCUMENT_TYPES = {"pdf", "docx", "txt", "csv"}

_SUPPORTED_EXTENSIONS = {f".{file_type}" for file_type in SUPPORTED_DOCUMENT_TYPES}
_CONTENT_TYPES_BY_FILE_TYPE = {
    "pdf": {"application/pdf"},
    "docx": {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    },
    "txt": {"text/plain"},
    "csv": {"text/csv"},
}
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x1f\x7f]")
_UNSAFE_FILENAME_CHARS_RE = re.compile(r"[^A-Za-z0-9._-]+")
_REPEATED_UNDERSCORES_RE = re.compile(r"_+")


class UploadValidationError(ValueError):
    """Raised when an uploaded document fails local validation."""


class UploadTooLargeError(UploadValidationError):
    """Raised when an uploaded document exceeds the configured size limit."""


@dataclass(frozen=True)
class ValidatedUpload:
    file_name: str
    file_type: str
    content: bytes
    content_type: str | None


def _supported_extensions_message() -> str:
    extensions = ", ".join(sorted(_SUPPORTED_EXTENSIONS))
    return f"Supported document extensions are: {extensions}."


def get_file_type(filename: str) -> str:
    suffix = Path(filename or "").suffix.lower()
    if suffix not in _SUPPORTED_EXTENSIONS:
        raise UploadValidationError(
            f"Unsupported file type. {_supported_extensions_message()}"
        )

    return suffix.removeprefix(".")


def sanitize_filename(filename: str) -> str:
    name = (filename or "").replace("\\", "/").split("/")[-1].strip()
    name = _CONTROL_CHARS_RE.sub("", name)
    name = _UNSAFE_FILENAME_CHARS_RE.sub("_", name)
    name = _REPEATED_UNDERSCORES_RE.sub("_", name).strip("._-")

    if not name:
        raise UploadValidationError("Filename is required.")

    get_file_type(name)
    return name


def _normalize_content_type(content_type: str | None) -> str | None:
    if content_type is None:
        return None

    normalized = content_type.split(";", 1)[0].strip().lower()
    return normalized or None


def _validate_content_type(file_type: str, content_type: str | None) -> None:
    if content_type is None:
        return

    allowed_content_types = _CONTENT_TYPES_BY_FILE_TYPE[file_type]
    if content_type not in allowed_content_types:
        expected = ", ".join(sorted(allowed_content_types))
        raise UploadValidationError(
            f"Content type '{content_type}' does not match .{file_type}. Expected: {expected}."
        )


async def _read_upload_bytes(upload_file: Any) -> bytes:
    content = upload_file.read()
    if isawaitable(content):
        content = await content

    if not isinstance(content, bytes):
        raise UploadValidationError("Uploaded file content must be bytes.")

    return content


async def validate_upload_file(upload_file: Any, max_bytes: int | None) -> ValidatedUpload:
    filename = getattr(upload_file, "filename", None)
    if not filename:
        raise UploadValidationError("Filename is required.")

    safe_filename = sanitize_filename(filename)
    file_type = get_file_type(safe_filename)
    content_type = _normalize_content_type(getattr(upload_file, "content_type", None))
    _validate_content_type(file_type, content_type)

    content = await _read_upload_bytes(upload_file)
    if not content:
        raise UploadValidationError("Uploaded file cannot be empty.")

    if max_bytes is not None and max_bytes > 0 and len(content) > max_bytes:
        raise UploadTooLargeError(
            f"Uploaded file exceeds the maximum size of {max_bytes} bytes."
        )

    return ValidatedUpload(
        file_name=safe_filename,
        file_type=file_type,
        content=content,
        content_type=content_type,
    )
