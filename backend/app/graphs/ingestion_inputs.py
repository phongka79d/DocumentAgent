from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


def document_id_text(state: Mapping[str, Any]) -> str | None:
    document_id = state.get("document_id")
    if document_id is None:
        return None
    return str(document_id).strip() or None


def resolve_document_id(state: Mapping[str, Any]) -> str | None:
    return document_id_text(state)


def resolve_document_record(state: Mapping[str, Any]) -> Mapping[str, Any]:
    document_record = state.get("document_record")
    if isinstance(document_record, Mapping):
        return document_record
    return {}


def resolve_file_name(state: Mapping[str, Any]) -> str | None:
    file_name = state.get("file_name")
    if isinstance(file_name, str) and file_name.strip():
        return file_name.strip()

    document_record = resolve_document_record(state)
    record_file_name = document_record.get("file_name")
    if isinstance(record_file_name, str) and record_file_name.strip():
        return record_file_name.strip()
    return None


def resolve_mime_type(state: Mapping[str, Any]) -> str | None:
    mime_type = state.get("mime_type")
    if isinstance(mime_type, str) and mime_type.strip():
        return mime_type.strip()

    document_record = resolve_document_record(state)
    record_mime_type = document_record.get("mime_type")
    if isinstance(record_mime_type, str) and record_mime_type.strip():
        return record_mime_type.strip()
    return None


def resolve_storage_path(state: Mapping[str, Any]) -> str | None:
    storage_path = state.get("storage_path")
    if isinstance(storage_path, str) and storage_path.strip():
        return storage_path.strip()

    document_record = resolve_document_record(state)
    record_storage_path = document_record.get("storage_path")
    if isinstance(record_storage_path, str) and record_storage_path.strip():
        return record_storage_path.strip()
    return None


def resolve_rows(response: Any) -> list[dict[str, Any]]:
    data = getattr(response, "data", response)
    if data is None:
        return []
    if isinstance(data, list):
        return [dict(row) for row in data]
    if isinstance(data, Mapping):
        return [dict(data)]
    if isinstance(data, Sequence) and not isinstance(data, (str, bytes)):
        return [dict(row) for row in data]
    return [dict(data)]


def normalize_bytes(downloaded: Any) -> bytes:
    if isinstance(downloaded, bytes):
        return downloaded
    if isinstance(downloaded, bytearray):
        return bytes(downloaded)
    if isinstance(downloaded, memoryview):
        return downloaded.tobytes()
    if hasattr(downloaded, "read"):
        data = downloaded.read()
        if isinstance(data, bytes):
            return data
        if isinstance(data, bytearray):
            return bytes(data)
    if isinstance(downloaded, str):
        return downloaded.encode("utf-8")
    raise TypeError("Downloaded document bytes could not be normalized")
