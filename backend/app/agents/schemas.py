from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class RetrievalAgentInput(BaseModel):
    agent_run_id: UUID
    question: str = Field(min_length=1)
    document_ids: list[UUID] = Field(min_length=1)

    @field_validator("question")
    @classmethod
    def normalize_question(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("question must not be empty")
        return normalized


class RetrievalCandidate(BaseModel):
    chunk_id: UUID
    document_id: UUID
    file_name: str | None
    content: str | None
    page_number: int | None
    section_title: str | None
    chunk_index: int | None = None
    semantic_similarity: float = Field(ge=0.0, le=1.0)
    graph_relevance: float = Field(ge=0.0, le=1.0)
    keyword_overlap: float = Field(ge=0.0, le=1.0)
    metadata_match: float = Field(ge=0.0, le=1.0)
    recency_or_position_score: float = Field(ge=0.0, le=1.0)
    final_score: float = Field(ge=0.0, le=1.0)
    retrieval_reason: str | None


class RetrievalAgentOutput(BaseModel):
    question: str = Field(min_length=1)
    candidates: list[RetrievalCandidate]

    @field_validator("question")
    @classmethod
    def normalize_question(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("question must not be empty")
        return normalized


class VerificationAgentInput(BaseModel):
    agent_run_id: UUID
    question: str = Field(min_length=1)
    candidates: list[RetrievalCandidate]

    @field_validator("question")
    @classmethod
    def normalize_question(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("question must not be empty")
        return normalized


class EvidenceCoverageSelection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chunk_id: UUID
    quote: str = Field(min_length=1)
    purpose: str = Field(min_length=1)
    supports_simple_reasoning: bool

    @field_validator("quote", "purpose")
    @classmethod
    def normalize_coverage_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("field must not be empty")
        return normalized


class EvidenceCoverageRequirement(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requirement: str = Field(min_length=1)
    satisfied: bool
    evidence: list[EvidenceCoverageSelection]
    missing_detail: str | None = None

    @field_validator("requirement")
    @classmethod
    def normalize_requirement(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("requirement must not be empty")
        return normalized

    @field_validator("missing_detail")
    @classmethod
    def normalize_missing_detail(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("missing_detail must not be empty")
        return normalized

    @model_validator(mode="after")
    def validate_requirement_coverage(self) -> "EvidenceCoverageRequirement":
        if self.satisfied and not self.evidence:
            raise ValueError("satisfied requirement requires evidence")
        if self.satisfied and self.missing_detail is not None:
            raise ValueError("satisfied requirement must not include missing_detail")
        if not self.satisfied and self.missing_detail is None:
            raise ValueError("unsatisfied requirement requires missing_detail")
        return self


class EvidenceCoverageReview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answers_question: bool
    missing_information: bool
    requirements: list[EvidenceCoverageRequirement] = Field(min_length=1)
    selected_evidence: list[EvidenceCoverageSelection]
    confidence: float = Field(ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_consistent_coverage(self) -> "EvidenceCoverageReview":
        if self.answers_question == self.missing_information:
            raise ValueError(
                "answers_question and missing_information must be opposites"
            )
        if self.answers_question and not self.selected_evidence:
            raise ValueError("answerable coverage requires selected evidence")
        if not self.answers_question and self.selected_evidence:
            raise ValueError(
                "non-answerable coverage must not include selected evidence"
            )

        all_requirements_satisfied = all(
            requirement.satisfied for requirement in self.requirements
        )
        if self.answers_question != all_requirements_satisfied:
            raise ValueError(
                "answers_question must match whether every requirement is satisfied"
            )

        if self.answers_question:
            expected_evidence: list[EvidenceCoverageSelection] = []
            for requirement in self.requirements:
                for selection in requirement.evidence:
                    if selection not in expected_evidence:
                        expected_evidence.append(selection)
            if self.selected_evidence != expected_evidence:
                raise ValueError(
                    "selected_evidence must equal the deduplicated union of "
                    "satisfied requirement evidence"
                )
        return self


class VerifiedChunk(BaseModel):
    chunk_id: UUID
    document_id: UUID
    file_name: str | None
    quote: str = Field(min_length=1)
    page_number: int | None
    verification_reason: str = Field(min_length=1)
    supports_simple_reasoning: bool = False

    @field_validator("quote", "verification_reason")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("field must not be empty")
        return normalized


class RejectedChunk(BaseModel):
    chunk_id: UUID
    document_id: UUID
    file_name: str | None
    quote: str = Field(min_length=1)
    rejection_reason: str = Field(min_length=1)

    @field_validator("quote", "rejection_reason")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("field must not be empty")
        return normalized


class VerificationAgentOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    verified_chunks: list[VerifiedChunk]
    rejected_chunks: list[RejectedChunk]
    missing_information: bool
    confidence: float = Field(ge=0.0, le=1.0)


class Citation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file_name: str = Field(min_length=1)
    quote: str = Field(min_length=1)

    @field_validator("file_name", "quote")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("field must not be empty")
        return normalized


class AnswerClaimGrounding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim: str = Field(min_length=1)
    supported: bool
    supporting_citations: list[Citation]

    @field_validator("claim")
    @classmethod
    def normalize_claim(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("claim must not be empty")
        return normalized


class AnswerFieldGrounding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field_name: Literal["final_answer", "reasoning_summary"]
    text: str = Field(min_length=1)
    claims: list[AnswerClaimGrounding] = Field(min_length=1)


class AnswerGroundingReview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answers_question: bool
    field_reviews: list[AnswerFieldGrounding] = Field(min_length=2, max_length=2)
    confidence: float = Field(ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_reviewed_fields(self) -> "AnswerGroundingReview":
        reviewed_fields = {review.field_name for review in self.field_reviews}
        if reviewed_fields != {"final_answer", "reasoning_summary"}:
            raise ValueError(
                "grounding review must cover final_answer and reasoning_summary"
            )
        return self


class AnswerSelfCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")

    uses_only_verified_chunks: bool
    has_citation: bool
    has_unsupported_claims: bool
    is_ready: bool


class AnswerAgentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent_run_id: UUID
    question: str = Field(min_length=1)
    verification: VerificationAgentOutput

    @field_validator("question")
    @classmethod
    def normalize_question(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("question must not be empty")
        return normalized


class AnswerAgentOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    final_answer: str = Field(min_length=1)
    citations: list[Citation]
    reasoning_summary: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
    self_check: AnswerSelfCheck

    @field_validator("final_answer", "reasoning_summary")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("field must not be empty")
        return normalized


__all__ = [
    "AnswerClaimGrounding",
    "AnswerFieldGrounding",
    "AnswerAgentInput",
    "AnswerAgentOutput",
    "AnswerGroundingReview",
    "AnswerSelfCheck",
    "Citation",
    "EvidenceCoverageRequirement",
    "EvidenceCoverageReview",
    "EvidenceCoverageSelection",
    "RetrievalAgentInput",
    "RetrievalCandidate",
    "RetrievalAgentOutput",
    "VerificationAgentInput",
    "VerifiedChunk",
    "RejectedChunk",
    "VerificationAgentOutput",
]
