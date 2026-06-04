from pathlib import Path
import sys
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.schemas.parsing import ParsedSection
from app.services.chunking_service import chunk_sections, estimate_token_count


def test_chunk_indexes_are_sequential_and_stable_in_source_order() -> None:
    sections = [
        ParsedSection(
            text="PDF one two three four.",
            file_name="source.pdf",
            page_number=2,
            metadata={"source_type": "pdf"},
        ),
        ParsedSection(
            text="DOCX alpha beta gamma delta.",
            file_name="source.docx",
            section_title="Employment Terms",
            metadata={"source_type": "docx"},
        ),
        ParsedSection(
            text="TXT red blue green yellow.",
            file_name="notes.txt",
            metadata={"source_type": "txt", "encoding": "utf-8"},
        ),
    ]

    first_chunks = chunk_sections(sections, chunk_size=3, chunk_overlap=1)
    second_chunks = chunk_sections(sections, chunk_size=3, chunk_overlap=1)

    assert [chunk.chunk_index for chunk in first_chunks] == list(range(len(first_chunks)))
    assert [chunk.model_dump() for chunk in first_chunks] == [
        chunk.model_dump() for chunk in second_chunks
    ]
    assert [chunk.metadata["source_type"] for chunk in first_chunks] == [
        "pdf",
        "pdf",
        "docx",
        "docx",
        "txt",
        "txt",
    ]


def test_pdf_page_metadata_is_preserved_on_chunk() -> None:
    document_id = UUID("11111111-1111-1111-1111-111111111111")
    section = ParsedSection(
        text="Page content keeps enough words for one deterministic chunk.",
        file_name="handbook.pdf",
        page_number=3,
        metadata={
            "document_id": document_id,
            "user_id": "single_user",
            "source_type": "pdf",
        },
    )

    chunks = chunk_sections([section], chunk_size=20, chunk_overlap=2)

    assert len(chunks) == 1
    assert chunks[0].document_id == document_id
    assert chunks[0].user_id == "single_user"
    assert chunks[0].file_name == "handbook.pdf"
    assert chunks[0].page_number == 3
    assert chunks[0].section_title is None
    assert chunks[0].metadata == section.metadata
    assert chunks[0].token_count == estimate_token_count(chunks[0].content)


def test_docx_section_title_metadata_is_preserved_on_chunk() -> None:
    section = ParsedSection(
        text="Probation terms include start date and review date.",
        file_name="contract.docx",
        section_title="Probation",
        metadata={
            "source_type": "docx",
            "paragraph_index": 7,
            "style_name": "Heading 2",
            "is_heading": True,
        },
    )

    chunks = chunk_sections([section], chunk_size=20, chunk_overlap=2)

    assert len(chunks) == 1
    assert chunks[0].file_name == "contract.docx"
    assert chunks[0].section_title == "Probation"
    assert chunks[0].metadata == section.metadata


def test_txt_metadata_is_preserved_on_chunk() -> None:
    section = ParsedSection(
        text="Plain text source keeps encoding metadata.",
        file_name="notes.txt",
        metadata={"source_type": "txt", "encoding": "latin-1"},
    )

    chunks = chunk_sections([section], chunk_size=20, chunk_overlap=2)

    assert len(chunks) == 1
    assert chunks[0].file_name == "notes.txt"
    assert chunks[0].metadata == {"source_type": "txt", "encoding": "latin-1"}


def test_csv_row_metadata_is_preserved_across_multiple_chunks() -> None:
    section = ParsedSection(
        text=(
            "Row 12:\n"
            "Name: Nguyen Van A\n"
            "Start Date: 2026-06-01\n"
            "Probation Period: 2 months\n"
            "Official Work Date: 2026-08-01"
        ),
        file_name="employees.csv",
        metadata={
            "source_type": "csv",
            "row_index": 12,
            "column_names": [
                "Name",
                "Start Date",
                "Probation Period",
                "Official Work Date",
            ],
        },
    )

    chunks = chunk_sections([section], chunk_size=5, chunk_overlap=1)

    assert len(chunks) > 1
    assert [chunk.chunk_index for chunk in chunks] == list(range(len(chunks)))
    for chunk in chunks:
        assert chunk.file_name == "employees.csv"
        assert chunk.metadata == section.metadata
        assert chunk.metadata["row_index"] == 12
        assert chunk.metadata["column_names"] == [
            "Name",
            "Start Date",
            "Probation Period",
            "Official Work Date",
        ]
