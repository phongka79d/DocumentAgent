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
from app.parsing.base import UnsupportedDocumentTypeError, build_parsed_document
from app.parsing.html import HtmlParser
from app.parsing.structure import (
    build_heading_block,
    build_paragraph_block,
    build_table_block,
    flatten_table_to_markdown,
    normalize_block_text,
)
from app.services.validation import DOCX_MIME_TYPE, HTML_MIME_TYPE


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
        "blocks": [
            {
                "type": "paragraph",
                "text": "caf\u00e9",
                "page_number": None,
                "heading_level": None,
                "section_path": [],
                "metadata": {},
            }
        ],
    }


def test_text_parser_splits_paragraph_blocks_on_blank_lines():
    parser = TextParser()
    text = (
        "First paragraph line 1\n"
        "Second line\n\n"
        "Second paragraph\n\n"
        "Third paragraph line 1\n"
        "Third paragraph line 2"
    )

    parsed = parser.parse(text.encode("utf-8"))

    assert parsed["text"] == text
    assert parsed["blocks"] == [
        build_paragraph_block("First paragraph line 1\nSecond line", None),
        build_paragraph_block("Second paragraph", None),
        build_paragraph_block("Third paragraph line 1\nThird paragraph line 2", None),
    ]


def test_markdown_parser_emits_headings_tables_and_list_groups():
    parser = MarkdownParser()
    markdown = (
        "# Title\n\n"
        "Some *content*.\n\n"
        "- first item\n"
        "- second item\n\n"
        "| Name | Role |\n"
        "| --- | --- |\n"
        "| Ada | Research |"
    )

    parsed = parser.parse(markdown.encode("utf-8"))

    assert parsed["text"] == markdown
    assert parsed["blocks"] == [
        build_heading_block(
            "Title",
            heading_level=1,
            page_number=None,
            metadata=None,
        ),
        build_paragraph_block("Some *content*.", None),
        build_paragraph_block("- first item\n- second item", None),
        build_table_block(
            flatten_table_to_markdown(
                [
                    ["Name", "Role"],
                    ["Ada", "Research"],
                ]
            ),
            page_number=None,
            metadata=None,
        ),
    ]
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
        ("page.html", "text/html", "html"),
        ("snippet.htm", "text/plain", "html"),
        ("page", HTML_MIME_TYPE, "html"),
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
        {".pdf", ".docx", ".txt", ".md", ".markdown", ".html", ".htm"}
    )
    assert PARSER_REGISTRY.supported_mime_types == frozenset(
        {
            "application/pdf",
            DOCX_MIME_TYPE,
            "text/plain",
            "application/markdown",
            "text/markdown",
            "text/x-markdown",
            HTML_MIME_TYPE,
        }
    )

    assert get_parser_for_extension(".pdf").parser_name == "pymupdf"
    assert get_parser_for_extension(".docx").parser_name == "python-docx"
    assert get_parser_for_extension(".txt").parser_name == "text"
    assert get_parser_for_extension(".md").parser_name == "markdown"
    assert get_parser_for_extension(".markdown").parser_name == "markdown"
    assert get_parser_for_extension(".html").parser_name == "html"
    assert get_parser_for_extension(".htm").parser_name == "html"

    assert get_parser_for_mime_type("application/pdf").parser_name == "pymupdf"
    assert get_parser_for_mime_type(DOCX_MIME_TYPE).parser_name == "python-docx"
    assert get_parser_for_mime_type("text/plain").parser_name == "text"
    assert get_parser_for_mime_type("text/markdown").parser_name == "markdown"
    assert get_parser_for_mime_type("application/markdown").parser_name == "markdown"
    assert get_parser_for_mime_type(HTML_MIME_TYPE).parser_name == "html"


def test_empty_extracted_text_raises_parse_error():
    parser = TextParser()

    with pytest.raises(EmptyExtractedTextError, match="Extracted text is empty"):
        parser.parse(b" \t\r\n")


def test_html_parser_extracts_visible_headings_paragraphs_and_tables():
    html = (
        "<!doctype html>"
        "<html>"
        "  <head>"
        "    <style>.hidden { display: none; }</style>"
        "    <script>console.log('ignore me')</script>"
        "    <template><p>Invisible template</p></template>"
        "  </head>"
        "  <body>"
        "    <h1>Welcome</h1>"
        "    <p>Visible paragraph with <strong>inline</strong> text.</p>"
        "    <ul>"
        "      <li>First item</li>"
        "      <li>Second item</li>"
        "    </ul>"
        "    <blockquote>Quoted line</blockquote>"
        "    <pre><code>print('hello')</code></pre>"
        "    <code>standalone code</code>"
        "    <table>"
        "      <tr><th>Name</th><th>Role</th></tr>"
        "      <tr><td>Ada</td><td>Research</td></tr>"
        "    </table>"
        "    <noscript>noscript text</noscript>"
        "  </body>"
        "</html>"
    )

    parsed = HtmlParser().parse(html.encode("utf-8"))

    expected_table_text = flatten_table_to_markdown(
        [
            ["Name", "Role"],
            ["Ada", "Research"],
        ]
    )
    expected_blocks = [
        build_heading_block("Welcome", heading_level=1, page_number=None, metadata=None),
        build_paragraph_block("Visible paragraph with inline text.", None),
        build_paragraph_block("First item", None),
        build_paragraph_block("Second item", None),
        build_paragraph_block("Quoted line", None),
        build_paragraph_block("print('hello')", None),
        build_paragraph_block("standalone code", None),
        build_table_block(expected_table_text, page_number=None, metadata=None),
    ]

    assert parsed["blocks"] == expected_blocks
    assert parsed["text"] == "\n\n".join(block["text"] for block in expected_blocks)
    assert parsed["pages"] == [
        {
            "page_number": 1,
            "text": parsed["text"],
        }
    ]
    assert parsed["metadata"] == {
        "parser_name": "html",
        "parser_version": "1.0.0",
    }
    assert "console.log" not in parsed["text"]
    assert "Invisible template" not in parsed["text"]
    assert "noscript text" not in parsed["text"]


def test_html_parser_rejects_empty_visible_text_after_removing_non_visible_elements():
    html = (
        "<html>"
        "  <head>"
        "    <style>body { color: red; }</style>"
        "    <script>console.log('hidden')</script>"
        "  </head>"
        "  <body>"
        "    <template><p>Hidden template</p></template>"
        "    <noscript>Hidden noscript</noscript>"
        "  </body>"
        "</html>"
    )

    with pytest.raises(EmptyExtractedTextError, match="Extracted text is empty for parser html"):
        HtmlParser().parse(html.encode("utf-8"))


def test_registry_rejects_unsupported_type():
    with pytest.raises(UnsupportedDocumentTypeError, match="Unsupported document type"):
        get_parser_for_file("archive.zip", mime_type="application/zip")


def test_pdf_parser_extracts_page_text_and_blocks_from_in_memory_pdf():
    fitz = pytest.importorskip("fitz")

    document = fitz.open()
    first_page = document.new_page()
    first_page.insert_text((72, 72), "PDF page one text")
    second_page = document.new_page()
    second_page.insert_text((72, 72), "PDF page two text")
    pdf_bytes = document.tobytes()
    document.close()

    parsed = PdfParser().parse(pdf_bytes)

    assert parsed["text"] == "PDF page one text\n\nPDF page two text"
    assert parsed["pages"] == [
        {
            "page_number": 1,
            "text": "PDF page one text",
        },
        {
            "page_number": 2,
            "text": "PDF page two text",
        }
    ]
    assert parsed["metadata"]["parser_name"] == "pymupdf"
    assert parsed["blocks"][0]["page_number"] == 1
    assert parsed["blocks"][1]["page_number"] == 2
    for block in parsed["blocks"]:
        assert block["type"] == "paragraph"
        assert block["heading_level"] is None
        assert set(block["metadata"]) >= {"font_size", "is_bold", "bbox"}
        assert block["metadata"]["font_size"] > 0
        assert isinstance(block["metadata"]["bbox"], list)
        assert len(block["metadata"]["bbox"]) == 4


def test_docx_parser_extracts_headings_tables_and_paragraph_text_from_in_memory_docx():
    docx = pytest.importorskip("docx")

    document = docx.Document()
    document.add_paragraph("DOCX Heading One", style="Heading 1")
    document.add_paragraph("DOCX Heading Six", style="Heading 6")
    document.add_paragraph("DOCX paragraph one")
    table = document.add_table(rows=2, cols=2)
    table.cell(0, 0).text = "Name"
    table.cell(0, 1).text = "Role"
    table.cell(1, 0).text = "Ada"
    table.cell(1, 1).text = "Research | Development"

    buffer = BytesIO()
    document.save(buffer)

    parsed = get_parser_for_extension(".docx").parse(buffer.getvalue())

    expected_table_text = flatten_table_to_markdown(
        [
            ["Name", "Role"],
            ["Ada", "Research | Development"],
        ]
    )
    expected_full_text = (
        "DOCX Heading One\n\n"
        "DOCX Heading Six\n\n"
        "DOCX paragraph one\n\n"
        f"{expected_table_text}"
    )

    assert parsed["text"] == expected_full_text
    assert parsed["pages"] == [
        {
            "page_number": 1,
            "text": expected_full_text,
        }
    ]
    assert parsed["metadata"]["parser_name"] == "python-docx"
    assert parsed["blocks"] == [
        build_heading_block("DOCX Heading One", heading_level=1, page_number=None, metadata=None),
        build_heading_block("DOCX Heading Six", heading_level=6, page_number=None, metadata=None),
        build_paragraph_block("DOCX paragraph one", None),
        build_table_block(expected_table_text, page_number=None, metadata=None),
    ]


def test_normalize_block_text_normalizes_line_endings_and_trims_edges():
    assert normalize_block_text("  First\r\nSecond\x0c  ") == "First\nSecond"


def test_block_builders_create_expected_structured_blocks():
    paragraph_block = build_paragraph_block("  Paragraph text\r\n", page_number=2)
    heading_metadata = {"font_size": 18, "is_bold": True}
    heading_block = build_heading_block(
        "  Section title\n",
        heading_level=3,
        page_number=4,
        metadata=heading_metadata,
    )
    markdown_table = flatten_table_to_markdown(
        [
            ["Name", "Role"],
            ["Ada", "Research | Development"],
            ["Bob"],
        ]
    )
    table_block = build_table_block(
        markdown_table,
        page_number=5,
        metadata={"source": "docx"},
    )

    assert paragraph_block == {
        "type": "paragraph",
        "text": "Paragraph text",
        "page_number": 2,
        "heading_level": None,
        "section_path": [],
        "metadata": {},
    }
    assert heading_block == {
        "type": "heading",
        "text": "Section title",
        "page_number": 4,
        "heading_level": 3,
        "section_path": [],
        "metadata": heading_metadata,
    }
    assert markdown_table == (
        "| Name | Role |\n"
        "| --- | --- |\n"
        "| Ada | Research \\| Development |\n"
        "| Bob |  |"
    )
    assert table_block == {
        "type": "table",
        "text": markdown_table,
        "page_number": 5,
        "heading_level": None,
        "section_path": [],
        "metadata": {"source": "docx"},
    }


def test_build_parsed_document_can_include_optional_blocks_without_breaking_old_fields():
    block = build_paragraph_block("Paragraph", page_number=1)

    parsed = build_parsed_document(
        text="Paragraph",
        parser_name="text",
        blocks=[block],
    )

    assert parsed["text"] == "Paragraph"
    assert parsed["pages"] == [
        {
            "page_number": 1,
            "text": "Paragraph",
        }
    ]
    assert parsed["metadata"] == {
        "parser_name": "text",
        "parser_version": "1.0.0",
    }
    assert parsed["blocks"] == [block]


def test_build_document_can_pass_optional_blocks_and_still_keep_existing_contract():
    block = build_heading_block(
        "Title",
        heading_level=1,
        page_number=1,
        metadata={"font_size": 24},
    )

    parsed = TextParser().build_document(text="Title", blocks=[block])

    assert parsed["text"] == "Title"
    assert parsed["pages"] == [
        {
            "page_number": 1,
            "text": "Title",
        }
    ]
    assert parsed["metadata"] == {
        "parser_name": "text",
        "parser_version": "1.0.0",
    }
    assert parsed["blocks"] == [block]


def test_build_document_omits_blocks_when_not_supplied():
    parsed = TextParser().build_document(text="Title")

    assert "blocks" not in parsed
