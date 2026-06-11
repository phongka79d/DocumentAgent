import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

import pytest
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.schemas.agent_runs import (
    AgentRunEvidenceResponse,
    AgentRunLogsResponse,
    AgentRunLogStepResponse,
)


AGENT_RUN_ID = UUID("11111111-1111-1111-1111-111111111111")
CHUNK_ID = UUID("22222222-2222-2222-2222-222222222222")
DOCUMENT_ID = UUID("33333333-3333-3333-3333-333333333333")
CREATED_AT = datetime(2026, 6, 1, 10, 0, tzinfo=timezone.utc)


def test_agent_run_evidence_response_reuses_agent_2_chunk_shapes() -> None:
    response = AgentRunEvidenceResponse.model_validate(
        {
            "verified_chunks": [
                {
                    "chunk_id": str(CHUNK_ID),
                    "document_id": str(DOCUMENT_ID),
                    "file_name": "contract.pdf",
                    "quote": "Probation starts on June 1, 2026.",
                    "page_number": 3,
                    "verification_reason": "The chunk directly states the date.",
                    "supports_simple_reasoning": True,
                }
            ],
            "rejected_chunks": [
                {
                    "chunk_id": str(CHUNK_ID),
                    "document_id": str(DOCUMENT_ID),
                    "file_name": "contract.pdf",
                    "quote": "The office closes on Fridays.",
                    "rejection_reason": "This does not answer the question.",
                }
            ],
        }
    )

    assert response.model_dump(mode="json") == {
        "verified_chunks": [
            {
                "chunk_id": str(CHUNK_ID),
                "document_id": str(DOCUMENT_ID),
                "file_name": "contract.pdf",
                "quote": "Probation starts on June 1, 2026.",
                "page_number": 3,
                "verification_reason": "The chunk directly states the date.",
                "supports_simple_reasoning": True,
            }
        ],
        "rejected_chunks": [
            {
                "chunk_id": str(CHUNK_ID),
                "document_id": str(DOCUMENT_ID),
                "file_name": "contract.pdf",
                "quote": "The office closes on Fridays.",
                "rejection_reason": "This does not answer the question.",
            }
        ],
    }


def test_agent_run_evidence_response_requires_verified_and_rejected_chunks() -> None:
    with pytest.raises(ValidationError):
        AgentRunEvidenceResponse.model_validate({"verified_chunks": []})


def test_agent_run_logs_response_matches_plan_12_field_names_and_order() -> None:
    response = AgentRunLogsResponse(
        agent_run_id=AGENT_RUN_ID,
        steps=[
            AgentRunLogStepResponse(
                agent_name="retrieval_agent",
                input={"question": "When does probation start?"},
                output={"candidate_count": 2},
                status="success",
                created_at=CREATED_AT,
            ),
            AgentRunLogStepResponse(
                agent_name="verification_agent",
                input={"candidate_count": 2},
                output={"verified_chunks": [], "rejected_chunks": []},
                status="failed",
                created_at=CREATED_AT,
            ),
        ],
    )

    assert response.model_dump(mode="json") == {
        "agent_run_id": str(AGENT_RUN_ID),
        "steps": [
            {
                "agent_name": "retrieval_agent",
                "input": {"question": "When does probation start?"},
                "output": {"candidate_count": 2},
                "status": "success",
                "created_at": "2026-06-01T10:00:00Z",
            },
            {
                "agent_name": "verification_agent",
                "input": {"candidate_count": 2},
                "output": {"verified_chunks": [], "rejected_chunks": []},
                "status": "failed",
                "created_at": "2026-06-01T10:00:00Z",
            },
        ],
    }


def test_agent_run_log_step_response_rejects_unserializable_payloads() -> None:
    with pytest.raises(ValidationError):
        AgentRunLogStepResponse(
            agent_name="retrieval_agent",
            input={"client": object()},
            output={},
            status="success",
            created_at=CREATED_AT,
        )


def test_agent_run_log_step_response_rejects_unknown_status() -> None:
    with pytest.raises(ValidationError):
        AgentRunLogStepResponse(
            agent_name="retrieval_agent",
            input={},
            output={},
            status="running",
            created_at=CREATED_AT,
        )
