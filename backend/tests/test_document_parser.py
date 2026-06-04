from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.document_parser import (
    DocumentDecodingError,
    EmptyDocumentError,
    UnreadableDocumentError,
    parse_document,
)


FIXTURE_DIR = Path(__file__).parent / "fixtures"


def test_pdf_parser_returns_non_empty_page_sections_and_metadata() -> None:
    file_bytes = (FIXTURE_DIR / "sample.pdf").read_bytes()

    sections = parse_document(file_bytes, "pdf", "sample.pdf")

    assert len(sections) == 1
    section = sections[0]
    assert "Document Agent sample PDF text." in section.text
    assert "This PDF fixture has extractable text." in section.text
    assert section.text.strip()
    assert section.page_number == 1
    assert section.file_name == "sample.pdf"
    assert section.metadata["source_type"] == "pdf"


def test_docx_parser_returns_non_empty_paragraph_sections_and_heading_metadata() -> None:
    file_bytes = (FIXTURE_DIR / "sample.docx").read_bytes()

    sections = parse_document(file_bytes, "docx", "sample.docx")

    assert len(sections) == 4
    heading = sections[0]
    paragraph = sections[1]
    assert heading.text == "Sample Contract Heading"
    assert heading.section_title == "Sample Contract Heading"
    assert heading.file_name == "sample.docx"
    assert heading.metadata["source_type"] == "docx"
    assert heading.metadata["paragraph_index"] == 1
    assert heading.metadata["style_name"] == "Heading 1"
    assert heading.metadata["is_heading"] is True
    assert "extractable paragraph text" in paragraph.text
    assert paragraph.section_title == "Sample Contract Heading"
    assert paragraph.metadata["is_heading"] is False
    assert all(section.text.strip() for section in sections)


def test_txt_parser_returns_non_empty_text_and_encoding_metadata() -> None:
    file_bytes = (FIXTURE_DIR / "sample.txt").read_bytes()

    sections = parse_document(file_bytes, "txt", "sample.txt")

    assert len(sections) == 1
    section = sections[0]
    assert "Document Agent sample text." in section.text
    assert "This TXT fixture contains extractable text." in section.text
    assert section.text.strip()
    assert section.file_name == "sample.txt"
    assert section.metadata["source_type"] == "txt"
    assert section.metadata["encoding"] == "utf-8"


def test_csv_parser_includes_column_names_row_indexes_and_metadata() -> None:
    file_bytes = (FIXTURE_DIR / "sample.csv").read_bytes()

    sections = parse_document(file_bytes, "csv", "sample.csv")

    assert len(sections) == 3
    first_section = sections[0]
    assert first_section.text.strip()
    assert "Row 2:" in first_section.text
    assert "Name: Nguyen Van A" in first_section.text
    assert "Start Date: 2026-06-01" in first_section.text
    assert "Probation Period: 2 months" in first_section.text
    assert "Official Work Date: 2026-08-01" in first_section.text
    assert first_section.file_name == "sample.csv"
    assert first_section.metadata["source_type"] == "csv"
    assert first_section.metadata["row_index"] == 2
    assert first_section.metadata["column_names"] == [
        "Name",
        "Start Date",
        "Probation Period",
        "Official Work Date",
    ]


def test_csv_decoding_failure_identifies_csv_document() -> None:
    invalid_utf8_csv = b"Name,Value\nAlice,\xff\n"

    with pytest.raises(DocumentDecodingError, match="CSV"):
        parse_document(invalid_utf8_csv, "csv", "bad.csv")


@pytest.mark.parametrize(
    "empty_bytes",
    [
        b"",
        b"   \n\t  ",
    ],
)
def test_empty_txt_input_fails_with_clear_empty_document_error(
    empty_bytes: bytes,
) -> None:
    with pytest.raises(EmptyDocumentError, match="Parsed document is empty."):
        parse_document(empty_bytes, "txt", "empty.txt")


def test_unreadable_pdf_input_fails_with_clear_parser_error() -> None:
    with pytest.raises(UnreadableDocumentError, match="Could not read PDF document."):
        parse_document(b"not a pdf fixture", "pdf", "bad.pdf")
