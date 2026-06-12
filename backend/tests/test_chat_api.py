import sys
from pathlib import Path
from unittest.mock import Mock
from uuid import UUID

import pytest
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.schemas.chat import ChatAskRequest, ChatAskResponse, ChatCitation
from app.services import chat_service


SESSION_ID = UUID("11111111-1111-1111-1111-111111111111")
DOCUMENT_ID = UUID("22222222-2222-2222-2222-222222222222")
AGENT_RUN_ID = UUID("33333333-3333-3333-3333-333333333333")
UNKNOWN_DOCUMENT_ID = UUID("44444444-4444-4444-4444-444444444444")
OTHER_USER_DOCUMENT_ID = UUID("55555555-5555-5555-5555-555555555555")


def test_chat_service_error_taxonomy_exposes_safe_public_messages() -> None:
    errors = [
        chat_service.ChatValidationError("Question must be non-empty."),
        chat_service.ChatSessionNotFoundError(),
        chat_service.SelectedDocumentNotFoundError(),
        chat_service.ChatDependencyError(),
        chat_service.ChatWorkflowError(RuntimeError("raw provider stack trace")),
    ]

    assert [error.public_message for error in errors] == [
        "Question must be non-empty.",
        "Chat session not found.",
        "Selected document not found.",
        "Chat persistence is temporarily unavailable.",
        "Workflow failed. Please try again later.",
    ]
    assert "provider" not in str(errors[-1]).lower()


def test_chat_ask_request_allows_omitted_session_id() -> None:
    request = ChatAskRequest(
        question="  What is the remote work policy?  ",
        document_ids=[DOCUMENT_ID],
    )

    assert request.session_id is None
    assert request.question == "What is the remote work policy?"
    assert request.document_ids == [DOCUMENT_ID]


def test_chat_ask_request_allows_nullable_session_id() -> None:
    request = ChatAskRequest.model_validate(
        {
            "session_id": None,
            "question": "Which contract clause sets probation?",
            "document_ids": [str(DOCUMENT_ID)],
        }
    )

    assert request.session_id is None
    assert request.document_ids == [DOCUMENT_ID]


def test_chat_ask_request_validates_uuid_fields() -> None:
    request = ChatAskRequest.model_validate(
        {
            "session_id": str(SESSION_ID),
            "question": "Which contract clause sets probation?",
            "document_ids": [str(DOCUMENT_ID)],
        }
    )

    assert request.session_id == SESSION_ID
    assert request.document_ids == [DOCUMENT_ID]


def test_chat_ask_request_rejects_missing_document_ids() -> None:
    with pytest.raises(ValidationError):
        ChatAskRequest.model_validate(
            {"question": "Which contract clause sets probation?"}
        )


def test_chat_ask_request_rejects_invalid_document_uuid() -> None:
    with pytest.raises(ValidationError):
        ChatAskRequest.model_validate(
            {
                "question": "Which contract clause sets probation?",
                "document_ids": ["not-a-uuid"],
            }
        )


@pytest.mark.parametrize("question", ["", "   ", "\n\t"])
def test_chat_ask_request_rejects_empty_or_whitespace_question(
    question: str,
) -> None:
    with pytest.raises(ValidationError):
        ChatAskRequest(question=question, document_ids=[DOCUMENT_ID])


def test_chat_ask_response_matches_plan_12_field_names() -> None:
    response = ChatAskResponse(
        answer="Employees may work remotely two days per week.",
        confidence=0.82,
        citations=[
            ChatCitation(
                file_name="handbook.pdf",
                quote="Remote work is allowed for two days each week.",
            )
        ],
        agent_run_id=AGENT_RUN_ID,
    )

    assert response.model_dump(mode="json") == {
        "answer": "Employees may work remotely two days per week.",
        "confidence": 0.82,
        "citations": [
            {
                "file_name": "handbook.pdf",
                "quote": "Remote work is allowed for two days each week.",
            }
        ],
        "agent_run_id": str(AGENT_RUN_ID),
    }


def test_chat_ask_response_rejects_confidence_outside_unit_interval() -> None:
    with pytest.raises(ValidationError):
        ChatAskResponse(
            answer="Employees may work remotely two days per week.",
            confidence=1.2,
            citations=[],
            agent_run_id=AGENT_RUN_ID,
        )


def test_prepare_chat_persistence_creates_session_when_session_id_is_omitted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    list_owned_documents = Mock(return_value=[{"id": str(DOCUMENT_ID)}])
    create_chat_session = Mock(
        return_value={"id": str(SESSION_ID), "title": "What is covered?"}
    )
    get_chat_session = Mock()
    create_agent_run = Mock(
        return_value={"id": str(AGENT_RUN_ID), "status": "running"}
    )
    insert_chat_message = Mock(return_value={"id": "user-message-id", "role": "user"})
    monkeypatch.setattr(
        chat_service.supabase_service,
        "list_owned_document_metadata_by_ids",
        list_owned_documents,
    )
    monkeypatch.setattr(
        chat_service.supabase_service,
        "create_chat_session",
        create_chat_session,
    )
    monkeypatch.setattr(chat_service.supabase_service, "get_chat_session", get_chat_session)
    monkeypatch.setattr(chat_service.supabase_service, "create_agent_run", create_agent_run)
    monkeypatch.setattr(
        chat_service.supabase_service,
        "insert_chat_message",
        insert_chat_message,
    )

    context = chat_service.prepare_chat_persistence(
        question="What is covered?",
        document_ids=[DOCUMENT_ID],
    )

    assert context.session == {"id": str(SESSION_ID), "title": "What is covered?"}
    assert context.agent_run == {"id": str(AGENT_RUN_ID), "status": "running"}
    assert context.user_message == {"id": "user-message-id", "role": "user"}
    list_owned_documents.assert_called_once_with([str(DOCUMENT_ID)])
    create_chat_session.assert_called_once_with(title="What is covered?")
    get_chat_session.assert_not_called()
    create_agent_run.assert_called_once_with(
        session_id=str(SESSION_ID),
        question="What is covered?",
        selected_document_ids=[str(DOCUMENT_ID)],
    )
    insert_chat_message.assert_called_once_with(
        session_id=str(SESSION_ID),
        role="user",
        content="What is covered?",
        metadata={
            "agent_run_id": str(AGENT_RUN_ID),
            "document_ids": [str(DOCUMENT_ID)],
        },
    )


def test_prepare_chat_persistence_rejects_empty_question_before_writes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    list_owned_documents = Mock(return_value=[{"id": str(DOCUMENT_ID)}])
    create_chat_session = Mock()
    get_chat_session = Mock()
    create_agent_run = Mock()
    insert_chat_message = Mock()
    monkeypatch.setattr(
        chat_service.supabase_service,
        "list_owned_document_metadata_by_ids",
        list_owned_documents,
    )
    monkeypatch.setattr(
        chat_service.supabase_service,
        "create_chat_session",
        create_chat_session,
    )
    monkeypatch.setattr(chat_service.supabase_service, "get_chat_session", get_chat_session)
    monkeypatch.setattr(chat_service.supabase_service, "create_agent_run", create_agent_run)
    monkeypatch.setattr(
        chat_service.supabase_service,
        "insert_chat_message",
        insert_chat_message,
    )

    with pytest.raises(chat_service.ChatValidationError) as exc_info:
        chat_service.prepare_chat_persistence(
            question="  ",
            document_ids=[DOCUMENT_ID],
        )

    assert exc_info.value.public_message == "Question must be non-empty."
    assert str(exc_info.value) == "Question must be non-empty."
    list_owned_documents.assert_not_called()
    create_chat_session.assert_not_called()
    get_chat_session.assert_not_called()
    create_agent_run.assert_not_called()
    insert_chat_message.assert_not_called()


def test_prepare_chat_persistence_raises_safe_not_found_for_unknown_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        chat_service.supabase_service,
        "list_owned_document_metadata_by_ids",
        Mock(return_value=[{"id": str(DOCUMENT_ID)}]),
    )
    monkeypatch.setattr(
        chat_service.supabase_service,
        "get_chat_session",
        Mock(return_value=None),
    )
    create_chat_session = Mock()
    create_agent_run = Mock()
    insert_chat_message = Mock()
    monkeypatch.setattr(
        chat_service.supabase_service,
        "create_chat_session",
        create_chat_session,
    )
    monkeypatch.setattr(chat_service.supabase_service, "create_agent_run", create_agent_run)
    monkeypatch.setattr(
        chat_service.supabase_service,
        "insert_chat_message",
        insert_chat_message,
    )

    with pytest.raises(chat_service.ChatSessionNotFoundError) as exc_info:
        chat_service.prepare_chat_persistence(
            session_id=SESSION_ID,
            question="What is covered?",
            document_ids=[DOCUMENT_ID],
        )

    assert str(exc_info.value) == "Chat session not found."
    assert exc_info.value.public_message == "Chat session not found."
    create_chat_session.assert_not_called()
    create_agent_run.assert_not_called()
    insert_chat_message.assert_not_called()


def test_prepare_chat_persistence_rejects_unknown_selected_document_before_writes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    list_owned_documents = Mock(return_value=[])
    create_chat_session = Mock()
    get_chat_session = Mock()
    create_agent_run = Mock()
    insert_chat_message = Mock()
    monkeypatch.setattr(
        chat_service.supabase_service,
        "list_owned_document_metadata_by_ids",
        list_owned_documents,
    )
    monkeypatch.setattr(
        chat_service.supabase_service,
        "create_chat_session",
        create_chat_session,
    )
    monkeypatch.setattr(chat_service.supabase_service, "get_chat_session", get_chat_session)
    monkeypatch.setattr(chat_service.supabase_service, "create_agent_run", create_agent_run)
    monkeypatch.setattr(
        chat_service.supabase_service,
        "insert_chat_message",
        insert_chat_message,
    )

    with pytest.raises(chat_service.SelectedDocumentNotFoundError) as exc_info:
        chat_service.prepare_chat_persistence(
            question="What is covered?",
            document_ids=[UNKNOWN_DOCUMENT_ID],
        )

    assert str(exc_info.value) == "Selected document not found."
    list_owned_documents.assert_called_once_with([str(UNKNOWN_DOCUMENT_ID)])
    create_chat_session.assert_not_called()
    get_chat_session.assert_not_called()
    create_agent_run.assert_not_called()
    insert_chat_message.assert_not_called()


def test_prepare_chat_persistence_rejects_not_owned_selected_document_before_writes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    list_owned_documents = Mock(return_value=[{"id": str(DOCUMENT_ID)}])
    create_chat_session = Mock()
    get_chat_session = Mock()
    create_agent_run = Mock()
    insert_chat_message = Mock()
    monkeypatch.setattr(
        chat_service.supabase_service,
        "list_owned_document_metadata_by_ids",
        list_owned_documents,
    )
    monkeypatch.setattr(
        chat_service.supabase_service,
        "create_chat_session",
        create_chat_session,
    )
    monkeypatch.setattr(chat_service.supabase_service, "get_chat_session", get_chat_session)
    monkeypatch.setattr(chat_service.supabase_service, "create_agent_run", create_agent_run)
    monkeypatch.setattr(
        chat_service.supabase_service,
        "insert_chat_message",
        insert_chat_message,
    )

    with pytest.raises(chat_service.SelectedDocumentNotFoundError):
        chat_service.prepare_chat_persistence(
            question="What is covered?",
            document_ids=[DOCUMENT_ID, OTHER_USER_DOCUMENT_ID],
        )

    list_owned_documents.assert_called_once_with(
        [str(DOCUMENT_ID), str(OTHER_USER_DOCUMENT_ID)]
    )
    create_chat_session.assert_not_called()
    get_chat_session.assert_not_called()
    create_agent_run.assert_not_called()
    insert_chat_message.assert_not_called()


def test_prepare_chat_persistence_wraps_dependency_failures_with_safe_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        chat_service.supabase_service,
        "list_owned_document_metadata_by_ids",
        Mock(side_effect=RuntimeError("raw database password leaked")),
    )

    with pytest.raises(chat_service.ChatDependencyError) as exc_info:
        chat_service.prepare_chat_persistence(
            question="What is covered?",
            document_ids=[DOCUMENT_ID],
        )

    assert (
        exc_info.value.public_message
        == "Chat persistence is temporarily unavailable."
    )
    assert str(exc_info.value) == "Chat persistence is temporarily unavailable."
    assert "password" not in str(exc_info.value).lower()


def test_prepare_chat_persistence_uses_existing_owned_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    list_owned_documents = Mock(return_value=[{"id": str(DOCUMENT_ID)}])
    get_chat_session = Mock(return_value={"id": str(SESSION_ID), "title": "Existing"})
    create_chat_session = Mock()
    create_agent_run = Mock(
        return_value={"id": str(AGENT_RUN_ID), "status": "running"}
    )
    insert_chat_message = Mock(return_value={"id": "user-message-id", "role": "user"})
    monkeypatch.setattr(
        chat_service.supabase_service,
        "list_owned_document_metadata_by_ids",
        list_owned_documents,
    )
    monkeypatch.setattr(chat_service.supabase_service, "get_chat_session", get_chat_session)
    monkeypatch.setattr(
        chat_service.supabase_service,
        "create_chat_session",
        create_chat_session,
    )
    monkeypatch.setattr(chat_service.supabase_service, "create_agent_run", create_agent_run)
    monkeypatch.setattr(
        chat_service.supabase_service,
        "insert_chat_message",
        insert_chat_message,
    )

    context = chat_service.prepare_chat_persistence(
        session_id=SESSION_ID,
        question="What is covered?",
        document_ids=[DOCUMENT_ID],
    )

    assert context.session["id"] == str(SESSION_ID)
    list_owned_documents.assert_called_once_with([str(DOCUMENT_ID)])
    get_chat_session.assert_called_once_with(str(SESSION_ID))
    create_chat_session.assert_not_called()
    create_agent_run.assert_called_once_with(
        session_id=str(SESSION_ID),
        question="What is covered?",
        selected_document_ids=[str(DOCUMENT_ID)],
    )
    assert context.user_message["role"] == "user"


def test_persist_assistant_message_stores_safe_run_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    insert_chat_message = Mock(
        return_value={"id": "assistant-message-id", "role": "assistant"}
    )
    monkeypatch.setattr(
        chat_service.supabase_service,
        "insert_chat_message",
        insert_chat_message,
    )

    result = chat_service.persist_assistant_message(
        session_id=SESSION_ID,
        agent_run_id=AGENT_RUN_ID,
        answer="Employees may work remotely two days per week.",
        confidence=0.82,
    )

    assert result == {"id": "assistant-message-id", "role": "assistant"}
    insert_chat_message.assert_called_once_with(
        session_id=str(SESSION_ID),
        role="assistant",
        content="Employees may work remotely two days per week.",
        metadata={"agent_run_id": str(AGENT_RUN_ID), "confidence": 0.82},
    )
