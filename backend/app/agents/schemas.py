from uuid import UUID

from pydantic import BaseModel, Field, field_validator


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


__all__ = [
    "RetrievalAgentInput",
    "RetrievalCandidate",
    "RetrievalAgentOutput",
]
