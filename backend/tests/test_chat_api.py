import sys
from pathlib import Path
from uuid import UUID

import pytest
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.schemas.chat import ChatAskRequest, ChatAskResponse, ChatCitation


SESSION_ID = UUID("11111111-1111-1111-1111-111111111111")
DOCUMENT_ID = UUID("22222222-2222-2222-2222-222222222222")
AGENT_RUN_ID = UUID("33333333-3333-3333-3333-333333333333")


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
