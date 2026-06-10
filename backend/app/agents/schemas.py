from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


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


class VerifiedChunk(BaseModel):
    chunk_id: UUID
    document_id: UUID
    file_name: str | None
    quote: str = Field(min_length=1)
    page_number: int | None
    verification_reason: str = Field(min_length=1)
    supports_simple_reasoning: bool

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
    "AnswerAgentInput",
    "AnswerAgentOutput",
    "AnswerSelfCheck",
    "Citation",
    "RetrievalAgentInput",
    "RetrievalCandidate",
    "RetrievalAgentOutput",
    "VerificationAgentInput",
    "VerifiedChunk",
    "RejectedChunk",
    "VerificationAgentOutput",
]
