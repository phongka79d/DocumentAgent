from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from app.services import supabase_service


SAFE_CHAT_DEPENDENCY_MESSAGE = "Chat persistence is temporarily unavailable."
SAFE_CHAT_WORKFLOW_FAILURE_MESSAGE = "Workflow failed. Please try again later."


class ChatServiceError(RuntimeError):
    """Base class for controlled chat service failures."""

    def __init__(self, public_message: str) -> None:
        self.public_message = public_message
        super().__init__(public_message)


class ChatValidationError(ChatServiceError, ValueError):
    """Raised when chat input fails service-level validation."""


class ChatSessionNotFoundError(ChatServiceError, LookupError):
    """Raised when a requested chat session is not owned by the configured user."""

    def __init__(self) -> None:
        super().__init__("Chat session not found.")


class SelectedDocumentNotFoundError(ChatServiceError, LookupError):
    """Raised when a selected document is missing or not owned by the user."""

    def __init__(self) -> None:
        super().__init__("Selected document not found.")


class ChatDependencyError(ChatServiceError):
    """Raised when chat persistence cannot safely complete because of a dependency."""

    def __init__(self) -> None:
        super().__init__(SAFE_CHAT_DEPENDENCY_MESSAGE)


class ChatWorkflowError(ChatServiceError):
    """Raised when the QA workflow fails behind a safe service boundary."""

    def __init__(self, error: BaseException | str | None = None) -> None:
        super().__init__(SAFE_CHAT_WORKFLOW_FAILURE_MESSAGE)


@dataclass(frozen=True)
class ChatPersistenceContext:
    session: dict[str, Any]
    agent_run: dict[str, Any]
    user_message: dict[str, Any]


def _stringify_uuid(value: UUID | str) -> str:
    return str(value)


def _stringify_uuid_list(values: Sequence[UUID | str]) -> list[str]:
    return [_stringify_uuid(value) for value in values]


def _validate_selected_document_ownership(
    document_ids: Sequence[UUID | str],
) -> list[str]:
    selected_document_ids = _stringify_uuid_list(document_ids)
    try:
        owned_documents = supabase_service.list_owned_document_metadata_by_ids(
            selected_document_ids
        )
    except Exception as exc:
        raise ChatDependencyError() from exc

    owned_document_ids = {
        str(document["id"])
        for document in owned_documents
        if document.get("id") is not None
    }

    if any(document_id not in owned_document_ids for document_id in selected_document_ids):
        raise SelectedDocumentNotFoundError()

    return selected_document_ids


def _session_id_from_row(session: dict[str, Any]) -> str:
    return str(session["id"])


def _agent_run_id_from_row(agent_run: dict[str, Any]) -> str:
    return str(agent_run["id"])


def _title_from_question(question: str) -> str:
    title = question.strip()
    if not title:
        return "New chat"
    return title[:80]


def _get_or_create_owned_session(
    session_id: UUID | str | None,
    *,
    question: str,
) -> dict[str, Any]:
    if session_id is None:
        try:
            return supabase_service.create_chat_session(
                title=_title_from_question(question)
            )
        except Exception as exc:
            raise ChatDependencyError() from exc

    try:
        session = supabase_service.get_chat_session(str(session_id))
    except Exception as exc:
        raise ChatDependencyError() from exc

    if session is None:
        raise ChatSessionNotFoundError()

    return session


def prepare_chat_persistence(
    *,
    question: str,
    document_ids: Sequence[UUID | str],
    session_id: UUID | str | None = None,
) -> ChatPersistenceContext:
    trimmed_question = question.strip()
    if not trimmed_question:
        raise ChatValidationError("Question must be non-empty.")

    selected_document_ids = _validate_selected_document_ownership(document_ids)
    session = _get_or_create_owned_session(session_id, question=trimmed_question)
    resolved_session_id = _session_id_from_row(session)

    try:
        agent_run = supabase_service.create_agent_run(
            session_id=resolved_session_id,
            question=trimmed_question,
            selected_document_ids=selected_document_ids,
        )
    except Exception as exc:
        raise ChatDependencyError() from exc

    agent_run_id = _agent_run_id_from_row(agent_run)

    try:
        user_message = supabase_service.insert_chat_message(
            session_id=resolved_session_id,
            role="user",
            content=trimmed_question,
            metadata={
                "agent_run_id": agent_run_id,
                "document_ids": selected_document_ids,
            },
        )
    except Exception as exc:
        raise ChatDependencyError() from exc

    return ChatPersistenceContext(
        session=session,
        agent_run=agent_run,
        user_message=user_message,
    )


def persist_assistant_message(
    *,
    session_id: UUID | str,
    agent_run_id: UUID | str,
    answer: str,
    confidence: float,
) -> dict[str, Any]:
    try:
        return supabase_service.insert_chat_message(
            session_id=str(session_id),
            role="assistant",
            content=answer,
            metadata={
                "agent_run_id": str(agent_run_id),
                "confidence": confidence,
            },
        )
    except Exception as exc:
        raise ChatDependencyError() from exc


__all__ = [
    "SAFE_CHAT_DEPENDENCY_MESSAGE",
    "SAFE_CHAT_WORKFLOW_FAILURE_MESSAGE",
    "ChatPersistenceContext",
    "ChatDependencyError",
    "ChatSessionNotFoundError",
    "ChatServiceError",
    "ChatValidationError",
    "ChatWorkflowError",
    "SelectedDocumentNotFoundError",
    "persist_assistant_message",
    "prepare_chat_persistence",
]
