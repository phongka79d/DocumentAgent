from pathlib import Path

import pytest

from app.services.validation import UploadValidationError, validate_upload_file


@pytest.mark.parametrize(
    ("file_name", "content_type", "expected_content_type"),
    [
        (
            "report.pdf",
            "application/pdf",
            "application/pdf",
        ),
        (
            "spec.docx",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ),
        (
            "notes.txt",
            "text/plain; charset=utf-8",
            "text/plain",
        ),
        (
            "summary.md",
            "text/markdown",
            "text/markdown",
        ),
        (
            "guide.markdown",
            None,
            None,
        ),
        (
            "page.html",
            "text/html",
            "text/html",
        ),
        (
            "snippet.htm",
            "text/html; charset=utf-8",
            "text/html",
        ),
    ],
)
def test_validate_upload_file_accepts_supported_files(
    file_name: str,
    content_type: str | None,
    expected_content_type: str | None,
):
    result = validate_upload_file(
        file_name=file_name,
        file_bytes=b"hello world",
        content_type=content_type,
        max_upload_bytes=1024,
    )

    assert result.file_name == file_name
    assert result.extension == Path(file_name).suffix.lower()
    assert result.file_size == 11
    assert result.content_type == expected_content_type


def test_validate_upload_file_rejects_empty_upload():
    with pytest.raises(UploadValidationError, match="Uploaded file is empty"):
        validate_upload_file(
            file_name="empty.pdf",
            file_bytes=b"",
            content_type="application/pdf",
            max_upload_bytes=1024,
        )


def test_validate_upload_file_rejects_oversized_upload():
    with pytest.raises(
        UploadValidationError,
        match="Uploaded file exceeds maximum size of 5 bytes",
    ):
        validate_upload_file(
            file_name="too-big.txt",
            file_bytes=b"123456",
            content_type="text/plain",
            max_upload_bytes=5,
        )


def test_validate_upload_file_rejects_unsupported_extension():
    with pytest.raises(
        UploadValidationError,
        match="Unsupported file extension: .zip",
    ):
        validate_upload_file(
            file_name="archive.zip",
            file_bytes=b"data",
            content_type="application/zip",
            max_upload_bytes=1024,
        )


def test_validate_upload_file_rejects_obvious_mime_conflict():
    with pytest.raises(
        UploadValidationError,
        match="File extension .txt is incompatible with MIME type application/pdf",
    ):
        validate_upload_file(
            file_name="invoice.txt",
            file_bytes=b"data",
            content_type="application/pdf",
            max_upload_bytes=1024,
        )


def test_validate_upload_file_rejects_html_mime_conflict():
    with pytest.raises(
        UploadValidationError,
        match="File extension .html is incompatible with MIME type text/plain",
    ):
        validate_upload_file(
            file_name="page.html",
            file_bytes=b"<html></html>",
            content_type="text/plain",
            max_upload_bytes=1024,
        )
