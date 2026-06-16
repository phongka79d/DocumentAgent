import sys
from importlib import import_module
from pathlib import Path
from unittest.mock import Mock, call
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.agents import answer_agent as answer_agent_module
from app.agents.schemas import Citation
from app.schemas.chat import ChatAskRequest, ChatAskResponse, ChatCitation
from app.services import agent_run_service, chat_service


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


def test_chat_ask_request_rejects_empty_document_ids() -> None:
    with pytest.raises(ValidationError):
        ChatAskRequest.model_validate(
            {
                "question": "Which contract clause sets probation?",
                "document_ids": [],
            }
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
    create_agent_run = Mock()
    insert_user_message = Mock(return_value={"id": "user-message-id", "role": "user"})
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
        "insert_user_chat_message_for_documents",
        insert_user_message,
    )

    context = chat_service.prepare_chat_persistence(
        question="What is covered?",
        document_ids=[DOCUMENT_ID],
    )

    assert context.session == {"id": str(SESSION_ID), "title": "What is covered?"}
    assert context.user_message == {"id": "user-message-id", "role": "user"}
    list_owned_documents.assert_called_once_with([str(DOCUMENT_ID)])
    create_chat_session.assert_called_once_with(title="What is covered?")
    get_chat_session.assert_not_called()
    create_agent_run.assert_not_called()
    insert_user_message.assert_called_once_with(
        session_id=str(SESSION_ID),
        content="What is covered?",
        document_ids=[str(DOCUMENT_ID)],
    )


def test_prepare_chat_persistence_inserts_user_message_with_document_lock_rpc(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    list_owned_documents = Mock(return_value=[{"id": str(DOCUMENT_ID)}])
    create_chat_session = Mock(return_value={"id": str(SESSION_ID)})
    insert_user_message = Mock(
        return_value={"id": "user-message-id", "role": "user"}
    )
    generic_insert_message = Mock()
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
    monkeypatch.setattr(
        chat_service.supabase_service,
        "insert_user_chat_message_for_documents",
        insert_user_message,
    )
    monkeypatch.setattr(
        chat_service.supabase_service,
        "insert_chat_message",
        generic_insert_message,
    )

    context = chat_service.prepare_chat_persistence(
        question="What is covered?",
        document_ids=[DOCUMENT_ID],
    )

    assert context.user_message == {"id": "user-message-id", "role": "user"}
    insert_user_message.assert_called_once_with(
        session_id=str(SESSION_ID),
        content="What is covered?",
        document_ids=[str(DOCUMENT_ID)],
    )
    generic_insert_message.assert_not_called()


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


def test_prepare_chat_persistence_rejects_empty_document_ids_before_writes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    list_owned_documents = Mock()
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
            question="What is covered?",
            document_ids=[],
        )

    assert exc_info.value.public_message == "Select at least one document."
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
    create_agent_run = Mock()
    insert_user_message = Mock(return_value={"id": "user-message-id", "role": "user"})
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
        "insert_user_chat_message_for_documents",
        insert_user_message,
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
    create_agent_run.assert_not_called()
    assert context.user_message["role"] == "user"
    insert_user_message.assert_called_once_with(
        session_id=str(SESSION_ID),
        content="What is covered?",
        document_ids=[str(DOCUMENT_ID)],
    )


def test_persist_assistant_message_stores_safe_run_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    get_chat_session = Mock(return_value={"id": str(SESSION_ID)})
    insert_chat_message = Mock(
        return_value={"id": "assistant-message-id", "role": "assistant"}
    )
    monkeypatch.setattr(
        chat_service.supabase_service,
        "get_chat_session",
        get_chat_session,
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
    get_chat_session.assert_called_once_with(str(SESSION_ID))
    insert_chat_message.assert_called_once_with(
        session_id=str(SESSION_ID),
        role="assistant",
        content="Employees may work remotely two days per week.",
        metadata={"agent_run_id": str(AGENT_RUN_ID), "confidence": 0.82},
    )


def test_persist_assistant_message_rejects_not_owned_session_before_write(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        chat_service.supabase_service,
        "get_chat_session",
        Mock(return_value=None),
    )
    insert_chat_message = Mock()
    monkeypatch.setattr(
        chat_service.supabase_service,
        "insert_chat_message",
        insert_chat_message,
    )

    with pytest.raises(chat_service.ChatSessionNotFoundError):
        chat_service.persist_assistant_message(
            session_id=SESSION_ID,
            agent_run_id=AGENT_RUN_ID,
            answer="This must not be stored.",
            confidence=0.1,
        )

    insert_chat_message.assert_not_called()


def _chat_client():
    chat_api = import_module("app.api.chat")
    application = FastAPI()
    application.include_router(chat_api.router, prefix="/api/chat")
    return TestClient(application), chat_api


def test_chat_ask_route_is_registered_in_application() -> None:
    main = import_module("app.main")

    route = next(
        (
            route
            for route in main.create_app().routes
            if route.path == "/api/chat/ask"
        ),
        None,
    )

    assert route is not None
    assert "POST" in route.methods


def test_chat_ask_route_runs_workflow_and_persists_assistant_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, chat_api = _chat_client()
    prepare_chat = Mock(
        return_value=chat_service.ChatPersistenceContext(
            session={"id": str(SESSION_ID), "title": "Existing"},
            user_message={"id": "user-message-id", "role": "user"},
        )
    )
    run_workflow = Mock(
        return_value={
            "answer": "Employees may work remotely two days per week.",
            "confidence": 0.82,
            "citations": [
                Citation(
                    file_name="handbook.pdf",
                    quote="Remote work is allowed for two days each week.",
                )
            ],
            "agent_run_id": AGENT_RUN_ID,
        }
    )
    persist_assistant = Mock(
        return_value={"id": "assistant-message-id", "role": "assistant"}
    )
    monkeypatch.setattr(
        chat_api.chat_service,
        "prepare_chat_persistence",
        prepare_chat,
    )
    monkeypatch.setattr(chat_api, "run_qa_workflow", run_workflow)
    monkeypatch.setattr(
        chat_api.chat_service,
        "persist_assistant_message",
        persist_assistant,
    )

    response = client.post(
        "/api/chat/ask",
        json={
            "session_id": str(SESSION_ID),
            "question": "What is the remote work policy?",
            "document_ids": [str(DOCUMENT_ID)],
        },
    )

    assert response.status_code == 200
    assert response.json() == {
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
    prepare_chat.assert_called_once_with(
        session_id=SESSION_ID,
        question="What is the remote work policy?",
        document_ids=[DOCUMENT_ID],
    )
    run_workflow.assert_called_once_with(
        "What is the remote work policy?",
        [DOCUMENT_ID],
        session_id=str(SESSION_ID),
    )
    persist_assistant.assert_called_once_with(
        session_id=str(SESSION_ID),
        agent_run_id=AGENT_RUN_ID,
        answer="Employees may work remotely two days per week.",
        confidence=0.82,
    )


def test_chat_ask_route_preserves_public_schema_for_multi_part_grounded_answer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, chat_api = _chat_client()
    exact_quote = "Probation starts on June 1, 2026 and lasts two months."
    monkeypatch.setattr(
        chat_api.chat_service,
        "prepare_chat_persistence",
        Mock(
            return_value=chat_service.ChatPersistenceContext(
                session={"id": str(SESSION_ID), "title": "Existing"},
                user_message={"id": "user-message-id", "role": "user"},
            )
        ),
    )
    monkeypatch.setattr(
        chat_api,
        "run_qa_workflow",
        Mock(
            return_value={
                "answer": "Probation starts on June 1, 2026 and lasts two months.",
                "confidence": 0.86,
                "citations": [
                    Citation(file_name="contract.pdf", quote=exact_quote),
                ],
                "agent_run_id": AGENT_RUN_ID,
            }
        ),
    )
    monkeypatch.setattr(
        chat_api.chat_service,
        "persist_assistant_message",
        Mock(return_value={"id": "assistant-message-id", "role": "assistant"}),
    )

    response = client.post(
        "/api/chat/ask",
        json={
            "session_id": str(SESSION_ID),
            "question": "When does probation start and how long does it last?",
            "document_ids": [str(DOCUMENT_ID)],
        },
    )

    assert response.status_code == 200
    assert set(response.json()) == {
        "answer",
        "confidence",
        "citations",
        "agent_run_id",
    }
    assert response.json()["citations"] == [
        {"file_name": "contract.pdf", "quote": exact_quote}
    ]


def test_chat_ask_returns_200_when_grounding_exhaustion_becomes_insufficient(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, chat_api = _chat_client()
    monkeypatch.setattr(
        chat_api.chat_service,
        "prepare_chat_persistence",
        Mock(
            return_value=chat_service.ChatPersistenceContext(
                session={"id": str(SESSION_ID)},
                user_message={"id": "user-message-id"},
            )
        ),
    )
    monkeypatch.setattr(
        chat_api,
        "run_qa_workflow",
        Mock(
            return_value={
                "answer": answer_agent_module.INSUFFICIENT_EVIDENCE_ANSWER,
                "confidence": 0.0,
                "citations": [],
                "agent_run_id": AGENT_RUN_ID,
            }
        ),
    )
    monkeypatch.setattr(
        chat_api.chat_service,
        "persist_assistant_message",
        Mock(),
    )

    response = client.post(
        "/api/chat/ask",
        json={
            "question": "What happened and what result followed?",
            "document_ids": [str(DOCUMENT_ID)],
        },
    )

    assert response.status_code == 200
    assert response.json()["answer"] == answer_agent_module.INSUFFICIENT_EVIDENCE_ANSWER
    assert response.json()["confidence"] == 0.0
    assert response.json()["citations"] == []


def test_chat_ask_route_persists_user_and_assistant_messages_with_services(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, chat_api = _chat_client()
    insert_user_message = Mock(return_value={"id": "user-message-id", "role": "user"})
    insert_chat_message = Mock(
        return_value={"id": "assistant-message-id", "role": "assistant"}
    )
    run_workflow = Mock(
        return_value={
            "answer": "Employees may work remotely two days per week.",
            "confidence": 0.82,
            "citations": [],
            "agent_run_id": AGENT_RUN_ID,
        }
    )
    monkeypatch.setattr(
        chat_api.chat_service.supabase_service,
        "list_owned_document_metadata_by_ids",
        Mock(return_value=[{"id": str(DOCUMENT_ID)}]),
    )
    monkeypatch.setattr(
        chat_api.chat_service.supabase_service,
        "create_chat_session",
        Mock(return_value={"id": str(SESSION_ID), "title": "What is covered?"}),
    )
    monkeypatch.setattr(
        chat_api.chat_service.supabase_service,
        "get_chat_session",
        Mock(return_value={"id": str(SESSION_ID), "title": "What is covered?"}),
    )
    monkeypatch.setattr(
        chat_api.chat_service.supabase_service,
        "insert_user_chat_message_for_documents",
        insert_user_message,
    )
    monkeypatch.setattr(
        chat_api.chat_service.supabase_service,
        "insert_chat_message",
        insert_chat_message,
    )
    monkeypatch.setattr(chat_api, "run_qa_workflow", run_workflow)

    response = client.post(
        "/api/chat/ask",
        json={
            "question": "What is covered?",
            "document_ids": [str(DOCUMENT_ID)],
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "answer": "Employees may work remotely two days per week.",
        "confidence": 0.82,
        "citations": [],
        "agent_run_id": str(AGENT_RUN_ID),
    }
    insert_user_message.assert_called_once_with(
        session_id=str(SESSION_ID),
        content="What is covered?",
        document_ids=[str(DOCUMENT_ID)],
    )
    insert_chat_message.assert_called_once_with(
        session_id=str(SESSION_ID),
        role="assistant",
        content="Employees may work remotely two days per week.",
        metadata={"agent_run_id": str(AGENT_RUN_ID), "confidence": 0.82},
    )
    run_workflow.assert_called_once_with(
        "What is covered?",
        [DOCUMENT_ID],
        session_id=str(SESSION_ID),
    )


@pytest.mark.parametrize(
    "payload",
    [
        {"document_ids": [str(DOCUMENT_ID)]},
        {"question": "", "document_ids": [str(DOCUMENT_ID)]},
        {"question": "   ", "document_ids": [str(DOCUMENT_ID)]},
        {"question": "What is covered?"},
        {"question": "What is covered?", "document_ids": []},
        {"question": "What is covered?", "document_ids": ["not-a-uuid"]},
    ],
)
def test_chat_ask_route_returns_400_for_invalid_request_without_starting_workflow(
    monkeypatch: pytest.MonkeyPatch,
    payload: dict[str, object],
) -> None:
    client, chat_api = _chat_client()
    prepare_chat = Mock()
    run_workflow = Mock()
    persist_assistant = Mock()
    monkeypatch.setattr(
        chat_api.chat_service,
        "prepare_chat_persistence",
        prepare_chat,
    )
    monkeypatch.setattr(chat_api, "run_qa_workflow", run_workflow)
    monkeypatch.setattr(
        chat_api.chat_service,
        "persist_assistant_message",
        persist_assistant,
    )

    response = client.post("/api/chat/ask", json=payload)

    assert response.status_code == 400
    prepare_chat.assert_not_called()
    run_workflow.assert_not_called()
    persist_assistant.assert_not_called()


def test_chat_ask_route_rejects_unknown_document_without_starting_workflow(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, chat_api = _chat_client()
    run_workflow = Mock()
    persist_assistant = Mock()
    monkeypatch.setattr(
        chat_api.chat_service,
        "prepare_chat_persistence",
        Mock(side_effect=chat_service.SelectedDocumentNotFoundError()),
    )
    monkeypatch.setattr(chat_api, "run_qa_workflow", run_workflow)
    monkeypatch.setattr(
        chat_api.chat_service,
        "persist_assistant_message",
        persist_assistant,
    )

    response = client.post(
        "/api/chat/ask",
        json={
            "question": "What is covered?",
            "document_ids": [str(UNKNOWN_DOCUMENT_ID)],
        },
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Selected document not found."}
    run_workflow.assert_not_called()
    persist_assistant.assert_not_called()


def test_chat_ask_route_returns_404_when_run_session_is_not_owned(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, chat_api = _chat_client()
    monkeypatch.setattr(
        chat_api.chat_service,
        "prepare_chat_persistence",
        Mock(
            return_value=chat_service.ChatPersistenceContext(
                session={"id": str(SESSION_ID)},
                user_message={"id": "user-message-id"},
            )
        ),
    )
    monkeypatch.setattr(
        chat_api,
        "run_qa_workflow",
        Mock(side_effect=agent_run_service.AgentRunSessionNotFoundError()),
    )
    persist_assistant = Mock()
    monkeypatch.setattr(
        chat_api.chat_service,
        "persist_assistant_message",
        persist_assistant,
    )

    response = client.post(
        "/api/chat/ask",
        json={
            "question": "What is covered?",
            "document_ids": [str(DOCUMENT_ID)],
        },
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Chat session not found."}
    persist_assistant.assert_not_called()


def test_chat_ask_route_returns_500_for_workflow_failure_without_assistant_write(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, chat_api = _chat_client()
    monkeypatch.setattr(
        chat_api.chat_service,
        "prepare_chat_persistence",
        Mock(
            return_value=chat_service.ChatPersistenceContext(
                session={"id": str(SESSION_ID)},
                user_message={"id": "user-message-id"},
            )
        ),
    )
    monkeypatch.setattr(
        chat_api,
        "run_qa_workflow",
        Mock(
            side_effect=agent_run_service.AgentRunWorkflowError(
                RuntimeError("raw provider secret")
            )
        ),
    )
    persist_assistant = Mock()
    monkeypatch.setattr(
        chat_api.chat_service,
        "persist_assistant_message",
        persist_assistant,
    )

    response = client.post(
        "/api/chat/ask",
        json={
            "question": "What is covered?",
            "document_ids": [str(DOCUMENT_ID)],
        },
    )

    assert response.status_code == 500
    assert response.json() == {
        "detail": agent_run_service.SAFE_AGENT_RUN_FAILURE_MESSAGE
    }
    assert "provider secret" not in response.text.lower()
    persist_assistant.assert_not_called()


@pytest.mark.parametrize(
    ("service_error", "expected_status"),
    [
        (chat_service.ChatValidationError("Question must be non-empty."), 400),
        (chat_service.ChatSessionNotFoundError(), 404),
        (chat_service.SelectedDocumentNotFoundError(), 404),
        (chat_service.ChatDependencyError(), 500),
        (agent_run_service.AgentRunWorkflowError(RuntimeError("secret")), 500),
    ],
)
def test_chat_ask_route_maps_controlled_errors_safely(
    monkeypatch: pytest.MonkeyPatch,
    service_error: Exception,
    expected_status: int,
) -> None:
    client, chat_api = _chat_client()
    monkeypatch.setattr(
        chat_api.chat_service,
        "prepare_chat_persistence",
        Mock(side_effect=service_error),
    )

    response = client.post(
        "/api/chat/ask",
        json={
            "question": "What is covered?",
            "document_ids": [str(DOCUMENT_ID)],
        },
    )

    assert response.status_code == expected_status
    assert response.json() == {"detail": service_error.public_message}
    assert "secret" not in response.text.lower()
