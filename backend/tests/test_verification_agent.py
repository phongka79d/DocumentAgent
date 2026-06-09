import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.agents.prompts import (
    VERIFICATION_AGENT_OUTPUT_KEYS,
    VERIFICATION_AGENT_SYSTEM_PROMPT,
)
from app.agents.schemas import VerificationAgentOutput


def _verification_output_payload(confidence: float) -> dict[str, object]:
    return {
        "verified_chunks": [],
        "rejected_chunks": [],
        "missing_information": False,
        "confidence": confidence,
    }


@pytest.mark.parametrize("confidence", [0.0, 0.42, 1.0])
def test_verification_agent_output_accepts_confidence_within_bounds(
    confidence: float,
) -> None:
    output = VerificationAgentOutput.model_validate(
        _verification_output_payload(confidence)
    )

    assert output.confidence == confidence


@pytest.mark.parametrize("confidence", [-0.01, 1.01])
def test_verification_agent_output_rejects_out_of_range_confidence(
    confidence: float,
) -> None:
    with pytest.raises(ValidationError) as exc_info:
        VerificationAgentOutput.model_validate(_verification_output_payload(confidence))

    assert "confidence" in str(exc_info.value)


def test_verification_prompt_contains_required_output_shape() -> None:
    prompt = VERIFICATION_AGENT_SYSTEM_PROMPT

    assert "Return only valid JSON" in prompt
    assert "exactly these top-level keys" in prompt
    for key in VERIFICATION_AGENT_OUTPUT_KEYS:
        assert f'"{key}"' in prompt


def test_verification_prompt_contains_accept_reject_and_missing_rules() -> None:
    prompt = VERIFICATION_AGENT_SYSTEM_PROMPT.lower()

    for phrase in [
        "directly answers",
        "date",
        "period",
        "condition",
        "definition",
        "ambiguity",
        "simple reasoning",
        "loosely related",
        "duplicated",
        "contradicted",
        "unclear",
        "wrong document",
        "missing_information",
        "guessing beyond the document",
    ]:
        assert phrase in prompt


def test_verification_prompt_limits_agent_scope() -> None:
    prompt = VERIFICATION_AGENT_SYSTEM_PROMPT.lower()

    assert "evaluate only the provided agent 1 candidate chunks" in prompt
    assert "do not retrieve more chunks" in prompt
    assert "generate a final answer" in prompt
    assert "user-facing citations" in prompt
