from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.document_parser import DocumentDecodingError, parse_document


FIXTURE_DIR = Path(__file__).parent / "fixtures"


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
