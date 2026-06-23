from __future__ import annotations

import argparse
import time
from pathlib import Path
from typing import Callable

from app.api.routes.documents import run_document_index, run_document_reindex
from app.core.config import Settings, get_settings
from app.core.contracts import DocumentStatus
from app.evaluation.dataset import DEFAULT_FIXTURE_DIRECTORY, FIXTURE_FILES
from app.models.schemas import DocumentResponse
from app.services import documents as document_service
from app.services.hashing import compute_sha256


MARKDOWN_MIME_TYPE = "text/markdown"
REQUIRED_CONFIGURATION = {
    "SUPABASE_URL": ("", "https://your-project.supabase.co"),
    "SUPABASE_SERVICE_ROLE_KEY": ("", "your-supabase-service-role-key"),
    "QDRANT_URL": ("", "https://your-cluster-url.cloud.qdrant.io"),
    "QDRANT_API_KEY": ("", "your-qdrant-key"),
    "SHOPAIKEY_API_KEY": ("", "your-key"),
    "JINA_API_KEY": ("", "your-jina-key"),
}


class SeedConfigurationError(RuntimeError):
    """Raised when live corpus seeding is not configured."""


class SeedTimeoutError(RuntimeError):
    """Raised when an indexed document does not reach ready state in time."""


def require_live_configuration(settings: Settings) -> None:
    missing = [
        name
        for name, placeholders in REQUIRED_CONFIGURATION.items()
        if str(getattr(settings, name, "")).strip() in placeholders
    ]
    if missing:
        raise SeedConfigurationError(
            "Live seeding requires configured values for: " + ", ".join(missing)
        )


def wait_until_ready(
    document_id: str,
    *,
    settings: Settings,
    timeout_seconds: float,
    poll_interval_seconds: float,
    get_document: Callable[..., DocumentResponse | None] = document_service.get_document,
) -> DocumentResponse:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() <= deadline:
        document = get_document(document_id, settings=settings)
        if document is None:
            raise SeedTimeoutError("Document disappeared while waiting for indexing")
        if document.status == DocumentStatus.READY:
            return document
        if document.status == DocumentStatus.FAILED:
            raise SeedTimeoutError("Document indexing failed")
        time.sleep(poll_interval_seconds)
    raise SeedTimeoutError("Timed out waiting for document readiness")


def seed_fixture(
    title: str,
    path: Path,
    *,
    settings: Settings,
    timeout_seconds: float,
    poll_interval_seconds: float,
) -> DocumentResponse:
    file_bytes = path.read_bytes()
    upload = document_service.register_uploaded_document(
        file_name=path.name,
        mime_type=MARKDOWN_MIME_TYPE,
        file_size=len(file_bytes),
        file_hash=compute_sha256(file_bytes),
        file_bytes=file_bytes,
        title=title,
        content_type=MARKDOWN_MIME_TYPE,
        settings=settings,
    )
    document = upload.document
    if upload.duplicate:
        run_document_reindex(document.id, settings=settings)
    elif document.status == DocumentStatus.READY:
        return document
    elif document.status != DocumentStatus.PROCESSING:
        run_document_index(document.id, settings=settings)
    return wait_until_ready(
        str(document.id),
        settings=settings,
        timeout_seconds=timeout_seconds,
        poll_interval_seconds=poll_interval_seconds,
    )


def seed_corpus(
    fixture_directory: Path,
    *,
    settings: Settings,
    timeout_seconds: float = 120.0,
    poll_interval_seconds: float = 1.0,
) -> dict[str, str]:
    require_live_configuration(settings)
    mappings: dict[str, str] = {}
    for title, file_name in FIXTURE_FILES.items():
        document = seed_fixture(
            title,
            fixture_directory / file_name,
            settings=settings,
            timeout_seconds=timeout_seconds,
            poll_interval_seconds=poll_interval_seconds,
        )
        mappings[title] = str(document.id)
    return mappings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Upload and index the deterministic evaluation corpus."
    )
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURE_DIRECTORY)
    parser.add_argument("--timeout", type=float, default=120.0)
    args = parser.parse_args(argv)
    try:
        mappings = seed_corpus(
            args.fixtures,
            settings=get_settings(),
            timeout_seconds=args.timeout,
        )
    except SeedConfigurationError as exc:
        parser.exit(2, f"BLOCKED_BY_USER_ACTION: {exc}\n")
    except Exception:
        parser.exit(1, "Evaluation corpus seeding failed; inspect provider logs securely.\n")
    for title, document_id in mappings.items():
        print(f"{title}: {document_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
