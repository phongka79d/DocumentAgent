from __future__ import annotations

from typing import Any

from app.services.validation import HTML_MIME_TYPE

from .base import BaseParser, PARSER_VERSION, ParseError, ParsedDocument
from .structure import (
    build_heading_block,
    build_paragraph_block,
    build_table_block,
    flatten_table_to_markdown,
)

_HTML_HEADING_TAGS = frozenset({f"h{level}" for level in range(1, 7)})
_HTML_PARAGRAPH_TAGS = frozenset({"p", "li", "blockquote", "pre", "code"})
_HTML_TABLE_TAG = "table"
_HTML_VISIBLE_BLOCK_TAGS = _HTML_HEADING_TAGS | _HTML_PARAGRAPH_TAGS | frozenset({_HTML_TABLE_TAG})
_HTML_REMOVED_TAGS = frozenset({"script", "style", "noscript", "template"})


def _load_beautiful_soup() -> tuple[Any, type[Any]]:
    try:
        from bs4 import BeautifulSoup  # type: ignore[import-not-found]
        from bs4.element import Tag  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover - dependency should be installed
        raise ParseError("beautifulsoup4 is required to parse HTML documents") from exc

    return BeautifulSoup, Tag


def _remove_non_visible_elements(soup: Any) -> None:
    for tag_name in _HTML_REMOVED_TAGS:
        for element in soup.find_all(tag_name):
            element.decompose()


def _has_visible_block_ancestor(tag: Any, tag_class: type[Any]) -> bool:
    for parent in tag.parents:
        if isinstance(parent, tag_class) and getattr(parent, "name", None) in _HTML_VISIBLE_BLOCK_TAGS:
            return True
    return False


def _extract_block_text(tag: Any) -> str:
    tag_name = str(getattr(tag, "name", "") or "").lower()
    if tag_name in {"pre", "code"}:
        return tag.get_text("\n", strip=False)

    return tag.get_text(" ", strip=True)


def _extract_table_rows(table_tag: Any) -> list[list[str]]:
    rows: list[list[str]] = []

    for row_tag in table_tag.find_all("tr"):
        parent_table = row_tag.find_parent("table")
        if parent_table is not table_tag:
            continue

        cell_tags = row_tag.find_all(["th", "td"], recursive=False)
        if not cell_tags:
            continue

        rows.append([cell.get_text(" ", strip=True) for cell in cell_tags])

    return rows


def _heading_level_from_tag_name(tag_name: str) -> int | None:
    if len(tag_name) == 2 and tag_name.startswith("h") and tag_name[1].isdigit():
        heading_level = int(tag_name[1])
        if 1 <= heading_level <= 6:
            return heading_level
    return None


class HtmlParser(BaseParser):
    parser_name = "html"
    parser_version = PARSER_VERSION
    supported_extensions = frozenset({".html", ".htm"})
    supported_mime_types = frozenset({HTML_MIME_TYPE})

    def parse(
        self,
        file_bytes: bytes,
        *,
        file_name: str | None = None,
        mime_type: str | None = None,
    ) -> ParsedDocument:
        beautiful_soup, tag_class = _load_beautiful_soup()
        soup = beautiful_soup(file_bytes, "html.parser")
        _remove_non_visible_elements(soup)

        container = soup.body if soup.body is not None else soup
        blocks: list[dict[str, Any]] = []

        for element in container.descendants:
            if not isinstance(element, tag_class):
                continue

            tag_name = str(getattr(element, "name", "") or "").lower()
            if tag_name not in _HTML_VISIBLE_BLOCK_TAGS:
                continue

            if _has_visible_block_ancestor(element, tag_class):
                continue

            if tag_name == _HTML_TABLE_TAG:
                rows = _extract_table_rows(element)
                if not rows:
                    continue

                table_text = flatten_table_to_markdown(rows)
                if not table_text.strip():
                    continue

                blocks.append(
                    build_table_block(
                        table_text,
                        page_number=None,
                        metadata=None,
                    )
                )
                continue

            block_text = _extract_block_text(element)
            if not block_text.strip():
                continue

            if tag_name in _HTML_HEADING_TAGS:
                heading_level = _heading_level_from_tag_name(tag_name)
                blocks.append(
                    build_heading_block(
                        block_text,
                        heading_level=heading_level,
                        page_number=None,
                        metadata=None,
                    )
                )
            else:
                blocks.append(build_paragraph_block(block_text, page_number=None))

        if not blocks:
            fallback_text = container.get_text(" ", strip=True)
            if fallback_text.strip():
                blocks.append(build_paragraph_block(fallback_text, page_number=None))

        full_text = "\n\n".join(block["text"] for block in blocks)
        return self.build_document(text=full_text, page_texts=[full_text], blocks=blocks)
