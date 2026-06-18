from io import BytesIO

import pytest

from app.parsing import (
    EmptyExtractedTextError,
    MarkdownParser,
    PARSER_REGISTRY,
    PdfParser,
    TextParser,
    get_parser_for_extension,
    get_parser_for_file,
    get_parser_for_mime_type,
)
from app.parsing.base import UnsupportedDocumentTypeError
from app.services.validation import DOCX_MIME_TYPE


def test_text_parser_uses_utf8_fallback_when_needed():
    parser = TextParser()

    parsed = parser.parse(b"caf\xe9")

    assert parsed == {
        "text": "caf\u00e9",
        "pages": [
            {
                "page_number": 1,
                "text": "caf\u00e9",
            }
        ],
        "metadata": {
            "parser_name": "text",
            "parser_version": "1.0.0",
        },
    }


def test_markdown_parser_normalizes_to_text_and_pages():
    parser = MarkdownParser()
    markdown = "# Title\n\nSome *content*.\n"

    parsed = parser.parse(markdown.encode("utf-8"))

    assert parsed["text"] == markdown
    assert parsed["pages"] == [
        {
            "page_number": 1,
            "text": markdown,
        }
    ]
    assert parsed["metadata"] == {
        "parser_name": "markdown",
        "parser_version": "1.0.0",
    }


@pytest.mark.parametrize(
    ("file_name", "mime_type", "expected_parser_name"),
    [
        ("report.pdf", "application/pdf", "pymupdf"),
        ("brief.docx", DOCX_MIME_TYPE, "python-docx"),
        ("notes.txt", "text/plain; charset=utf-8", "text"),
        ("summary.md", "text/markdown", "markdown"),
        ("guide.markdown", None, "markdown"),
        ("README", "text/plain", "text"),
    ],
)
def test_registry_resolves_supported_file_types(
    file_name: str,
    mime_type: str | None,
    expected_parser_name: str,
):
    parser = get_parser_for_file(file_name, mime_type=mime_type)

    assert parser.parser_name == expected_parser_name


def test_registry_maps_supported_extensions_and_mime_types():
    assert PARSER_REGISTRY.supported_extensions == frozenset(
        {".pdf", ".docx", ".txt", ".md", ".markdown"}
    )
    assert PARSER_REGISTRY.supported_mime_types == frozenset(
        {
            "application/pdf",
            DOCX_MIME_TYPE,
            "text/plain",
            "application/markdown",
            "text/markdown",
            "text/x-markdown",
        }
    )

    assert get_parser_for_extension(".pdf").parser_name == "pymupdf"
    assert get_parser_for_extension(".docx").parser_name == "python-docx"
    assert get_parser_for_extension(".txt").parser_name == "text"
    assert get_parser_for_extension(".md").parser_name == "markdown"
    assert get_parser_for_extension(".markdown").parser_name == "markdown"

    assert get_parser_for_mime_type("application/pdf").parser_name == "pymupdf"
    assert get_parser_for_mime_type(DOCX_MIME_TYPE).parser_name == "python-docx"
    assert get_parser_for_mime_type("text/plain").parser_name == "text"
    assert get_parser_for_mime_type("text/markdown").parser_name == "markdown"
    assert get_parser_for_mime_type("application/markdown").parser_name == "markdown"


def test_empty_extracted_text_raises_parse_error():
    parser = TextParser()

    with pytest.raises(EmptyExtractedTextError, match="Extracted text is empty"):
        parser.parse(b" \t\r\n")


def test_registry_rejects_unsupported_type():
    with pytest.raises(UnsupportedDocumentTypeError, match="Unsupported document type"):
        get_parser_for_file("archive.zip", mime_type="application/zip")


def test_pdf_parser_extracts_page_text_from_in_memory_pdf():
    fitz = pytest.importorskip("fitz")

    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), "PDF page text")
    pdf_bytes = document.tobytes()
    document.close()

    parsed = PdfParser().parse(pdf_bytes)

    assert parsed["text"] == "PDF page text"
    assert parsed["pages"] == [
        {
            "page_number": 1,
            "text": "PDF page text",
        }
    ]
    assert parsed["metadata"]["parser_name"] == "pymupdf"


def test_docx_parser_extracts_paragraph_text_from_in_memory_docx():
    docx = pytest.importorskip("docx")

    document = docx.Document()
    document.add_paragraph("DOCX paragraph one")
    document.add_paragraph("DOCX paragraph two")

    buffer = BytesIO()
    document.save(buffer)

    parsed = get_parser_for_extension(".docx").parse(buffer.getvalue())

    assert parsed["text"] == "DOCX paragraph one\nDOCX paragraph two"
    assert parsed["pages"] == [
        {
            "page_number": 1,
            "text": "DOCX paragraph one\nDOCX paragraph two",
        }
    ]
    assert parsed["metadata"]["parser_name"] == "python-docx"
