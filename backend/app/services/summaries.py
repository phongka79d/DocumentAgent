from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Any
from uuid import UUID

from app.core.config import Settings, get_settings
from app.core.contracts import SummaryType, TableName
from app.core.retry import RetryExhaustedError, retry_sync
from app.services.shopaikey_client import create_shopaikey_client
from app.services.supabase_client import create_supabase_client

DOCUMENT_SUMMARIES_TABLE = TableName.DOCUMENT_SUMMARIES
SUMMARY_SYSTEM_PROMPT = (
    "You summarize indexed document text. Use only the supplied extracted text or "
    "section summaries. Do not add outside facts. Return a concise summary only."
)


def _resolve_supabase_client(supabase_client: Any | None = None) -> Any:
    return supabase_client if supabase_client is not None else create_supabase_client()


def _resolve_settings(settings: Settings | None = None) -> Settings:
    return settings if settings is not None else get_settings()


def _resolve_shopaikey_client(
    settings: Settings,
    shopaikey_client: Any | None = None,
) -> Any:
    return shopaikey_client if shopaikey_client is not None else create_shopaikey_client(settings)


def _response_rows(response: Any) -> list[dict[str, Any]]:
    data = getattr(response, "data", response)
    if data is None:
        return []
    if isinstance(data, Mapping):
        return [dict(data)]
    if isinstance(data, Iterable) and not isinstance(data, (str, bytes)):
        return [dict(row) for row in data]
    return []


def _normalize_uuid(value: UUID | str, field_name: str) -> str:
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError, AttributeError) as exc:
        raise ValueError(f"{field_name} must be a valid UUID") from exc


def _normalize_text(value: Any, field_name: str, *, nullable: bool = False) -> str | None:
    if value is None and nullable:
        return None
    cleaned = str(value or "").strip()
    if not cleaned:
        if nullable:
            return None
        raise ValueError(f"{field_name} is required")
    return cleaned


def _normalize_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (str, bytes)):
        value = [value]
    if not isinstance(value, Sequence):
        raise ValueError("section_path must be a sequence")
    return [text for item in value if (text := str(item).strip())]


def _normalize_uuid_list(value: Any, field_name: str) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (str, bytes, UUID)):
        value = [value]
    if not isinstance(value, Iterable):
        raise ValueError(f"{field_name} must be a sequence")
    normalized: list[str] = []
    seen: set[str] = set()
    for item in value:
        item_id = _normalize_uuid(item, field_name)
        if item_id not in seen:
            normalized.append(item_id)
            seen.add(item_id)
    return normalized


def _chat_content(response: Any) -> str:
    choices = getattr(response, "choices", None)
    if choices is None and isinstance(response, Mapping):
        choices = response.get("choices")
    if not choices:
        raise ValueError("Summary response missing choices")
    first = choices[0]
    message = getattr(first, "message", None)
    if message is None and isinstance(first, Mapping):
        message = first.get("message")
    content = getattr(message, "content", None)
    if content is None and isinstance(message, Mapping):
        content = message.get("content")
    text = str(content or "").strip()
    if not text:
        raise ValueError("Summary response was empty")
    return text


def _chunk_id(chunk: Mapping[str, Any]) -> str:
    value = chunk.get("id") or chunk.get("chunk_id")
    return _normalize_uuid(value, "chunk_id")


def _chunk_content(chunk: Mapping[str, Any]) -> str:
    return _normalize_text(chunk.get("content"), "chunk content")


def _section_path(value: Any) -> list[str]:
    return _normalize_string_list(value)


def _section_group(chunk: Mapping[str, Any]) -> tuple[str, ...]:
    path = _section_path(chunk.get("section_path"))
    if path:
        return tuple(path)
    heading = _normalize_text(chunk.get("heading"), "heading", nullable=True)
    return (heading,) if heading else ()


def _chunk_index(chunk: Mapping[str, Any]) -> int:
    try:
        return int(chunk.get("chunk_index", 0))
    except (TypeError, ValueError):
        return 0


def _summary_heading(group_chunks: Sequence[Mapping[str, Any]], path: Sequence[str]) -> str | None:
    for chunk in group_chunks:
        heading = _normalize_text(chunk.get("heading"), "heading", nullable=True)
        if heading:
            return heading
    return path[-1] if path else None


def _call_summary_model(
    *,
    client: Any,
    model: str,
    max_tokens: int,
    user_prompt: str,
    settings: Settings,
) -> str:
    response = retry_sync(
        "summary_generation",
        lambda: client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0,
            max_tokens=max_tokens,
        ),
        settings=settings,
    )
    return _chat_content(response)


def _section_prompt(
    *,
    section_path: Sequence[str],
    heading: str | None,
    chunks: Sequence[Mapping[str, Any]],
) -> str:
    text_blocks = [
        f"Chunk {index + 1} ({_chunk_id(chunk)}):\n{_chunk_content(chunk)}"
        for index, chunk in enumerate(chunks)
    ]
    return (
        "Summarize this document section using only the extracted chunk text below.\n"
        f"Section path: {' > '.join(section_path) if section_path else '(none)'}\n"
        f"Heading: {heading or '(none)'}\n\n"
        "Extracted chunk text:\n"
        + "\n\n".join(text_blocks)
    )


def _document_prompt(section_records: Sequence[Mapping[str, Any]]) -> str:
    text_blocks = [
        (
            f"Section {index + 1} "
            f"({' > '.join(record.get('section_path') or []) or record.get('heading') or 'document'}):\n"
            f"{record['content']}"
        )
        for index, record in enumerate(section_records)
    ]
    return (
        "Summarize the whole document using only these section summaries. "
        "Do not use or invent facts outside these summaries.\n\n"
        "Section summaries:\n"
        + "\n\n".join(text_blocks)
    )


def _normalize_payload(
    *,
    document_id: UUID | str,
    summary_type: SummaryType | str,
    content: str,
    model: str,
    heading: str | None = None,
    section_path: Sequence[str] | None = None,
    source_chunk_ids: Iterable[UUID | str] | None = None,
) -> dict[str, Any]:
    normalized_type = SummaryType(summary_type).value
    normalized_path = _normalize_string_list(section_path)
    normalized_heading = _normalize_text(heading, "heading", nullable=True)
    if normalized_type == SummaryType.DOCUMENT:
        normalized_heading = None
        normalized_path = []
    return {
        "document_id": _normalize_uuid(document_id, "document_id"),
        "summary_type": normalized_type,
        "heading": normalized_heading,
        "section_path": normalized_path,
        "content": _normalize_text(content, "content"),
        "source_chunk_ids": _normalize_uuid_list(source_chunk_ids, "source_chunk_ids"),
        "model": _normalize_text(model, "model"),
    }


def _normalize_row(row: Mapping[str, Any]) -> dict[str, Any]:
    normalized = dict(row)
    if normalized.get("id") is not None:
        normalized["id"] = _normalize_uuid(normalized["id"], "id")
    if normalized.get("document_id") is not None:
        normalized["document_id"] = _normalize_uuid(
            normalized["document_id"], "document_id"
        )
    normalized["summary_type"] = SummaryType(normalized["summary_type"]).value
    normalized["section_path"] = _normalize_string_list(
        normalized.get("section_path")
    )
    normalized["source_chunk_ids"] = _normalize_uuid_list(
        normalized.get("source_chunk_ids"), "source_chunk_ids"
    )
    return normalized


def _summary_sort_key(row: Mapping[str, Any]) -> tuple[Any, ...]:
    summary_type = SummaryType(row["summary_type"])
    return (
        0 if summary_type is SummaryType.DOCUMENT else 1,
        tuple(row.get("section_path") or []),
        str(row.get("heading") or ""),
        str(row.get("id") or ""),
    )


def create_summary(
    *,
    document_id: UUID | str,
    summary_type: SummaryType | str,
    content: str,
    model: str,
    heading: str | None = None,
    section_path: Sequence[str] | None = None,
    source_chunk_ids: Iterable[UUID | str] | None = None,
    supabase_client: Any | None = None,
) -> dict[str, Any]:
    payload = _normalize_payload(
        document_id=document_id,
        summary_type=summary_type,
        heading=heading,
        section_path=section_path,
        content=content,
        source_chunk_ids=source_chunk_ids,
        model=model,
    )
    client = _resolve_supabase_client(supabase_client)
    rows = _response_rows(
        retry_sync(
            "summary_persistence",
            lambda: client.table(DOCUMENT_SUMMARIES_TABLE).insert(payload).execute(),
        )
    )
    return _normalize_row(rows[0]) if rows else payload


def list_summaries(
    document_id: UUID | str, *, supabase_client: Any | None = None
) -> list[dict[str, Any]]:
    normalized_document_id = _normalize_uuid(document_id, "document_id")
    client = _resolve_supabase_client(supabase_client)
    response = retry_sync(
        "summary_persistence",
        lambda: client.table(DOCUMENT_SUMMARIES_TABLE)
        .select("*")
        .eq("document_id", normalized_document_id)
        .execute(),
    )
    rows = [_normalize_row(row) for row in _response_rows(response)]
    return sorted(rows, key=_summary_sort_key)


def replace_document_summaries(
    document_id: UUID | str,
    summary_records: Iterable[Mapping[str, Any]],
    *,
    supabase_client: Any | None = None,
) -> list[dict[str, Any]]:
    normalized_document_id = _normalize_uuid(document_id, "document_id")
    payloads = [
        _normalize_payload(
            document_id=normalized_document_id,
            summary_type=record["summary_type"],
            heading=record.get("heading"),
            section_path=record.get("section_path"),
            content=record["content"],
            source_chunk_ids=record.get("source_chunk_ids"),
            model=record["model"],
        )
        for record in summary_records
    ]
    client = _resolve_supabase_client(supabase_client)
    retry_sync(
        "summary_persistence",
        lambda: client.table(DOCUMENT_SUMMARIES_TABLE)
        .delete()
        .eq("document_id", normalized_document_id)
        .execute(),
    )
    if not payloads:
        return []
    rows = _response_rows(
        retry_sync(
            "summary_persistence",
            lambda: client.table(DOCUMENT_SUMMARIES_TABLE).insert(payloads).execute(),
        )
    )
    normalized_rows = [_normalize_row(row) for row in rows] if rows else payloads
    return sorted(normalized_rows, key=_summary_sort_key)


def generate_document_summaries(
    document_id: UUID | str,
    chunks: Sequence[Mapping[str, Any]],
    *,
    settings: Settings | None = None,
    shopaikey_client: Any | None = None,
    supabase_client: Any | None = None,
) -> list[dict[str, Any]] | dict[str, Any]:
    resolved_settings = _resolve_settings(settings)
    if not resolved_settings.ENABLE_SUMMARIES:
        return []

    normalized_document_id = _normalize_uuid(document_id, "document_id")
    saved_chunks = sorted([dict(chunk) for chunk in chunks], key=_chunk_index)
    if not saved_chunks:
        return []

    try:
        client = _resolve_shopaikey_client(resolved_settings, shopaikey_client)
        grouped: dict[tuple[str, ...], list[Mapping[str, Any]]] = {}
        for chunk in saved_chunks:
            _chunk_id(chunk)
            _chunk_content(chunk)
            grouped.setdefault(_section_group(chunk), []).append(chunk)

        section_records: list[dict[str, Any]] = []
        for group_key in grouped:
            group_chunks = grouped[group_key]
            section_path = list(group_key)
            heading = _summary_heading(group_chunks, section_path)
            content = _call_summary_model(
                client=client,
                model=resolved_settings.SHOPAIKEY_CHAT_MODEL,
                max_tokens=resolved_settings.SUMMARY_SECTION_MAX_TOKENS,
                user_prompt=_section_prompt(
                    section_path=section_path,
                    heading=heading,
                    chunks=group_chunks,
                ),
                settings=resolved_settings,
            )
            section_records.append(
                {
                    "summary_type": SummaryType.SECTION,
                    "heading": heading,
                    "section_path": section_path,
                    "content": content,
                    "source_chunk_ids": [_chunk_id(chunk) for chunk in group_chunks],
                    "model": resolved_settings.SHOPAIKEY_CHAT_MODEL,
                }
            )

        all_source_chunk_ids: list[str] = []
        for record in section_records:
            for chunk_id in record["source_chunk_ids"]:
                if chunk_id not in all_source_chunk_ids:
                    all_source_chunk_ids.append(chunk_id)

        document_content = _call_summary_model(
            client=client,
            model=resolved_settings.SHOPAIKEY_CHAT_MODEL,
            max_tokens=resolved_settings.SUMMARY_DOCUMENT_MAX_TOKENS,
            user_prompt=_document_prompt(section_records),
            settings=resolved_settings,
        )
        summary_records = [
            {
                "summary_type": SummaryType.DOCUMENT,
                "heading": None,
                "section_path": [],
                "content": document_content,
                "source_chunk_ids": all_source_chunk_ids,
                "model": resolved_settings.SHOPAIKEY_CHAT_MODEL,
            },
            *section_records,
        ]
    except RetryExhaustedError:
        raise
    except Exception as exc:
        return {
            "status": "failed",
            "error_message": f"Summary generation failed: {exc}",
        }

    return replace_document_summaries(
        normalized_document_id,
        summary_records,
        supabase_client=supabase_client,
    )


def delete_document_summaries(
    document_id: UUID | str, *, supabase_client: Any | None = None
) -> None:
    normalized_document_id = _normalize_uuid(document_id, "document_id")
    client = _resolve_supabase_client(supabase_client)
    retry_sync(
        "summary_persistence",
        lambda: client.table(DOCUMENT_SUMMARIES_TABLE)
        .delete()
        .eq("document_id", normalized_document_id)
        .execute(),
    )
