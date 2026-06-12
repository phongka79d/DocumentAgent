from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ChatAskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: UUID | None = None
    question: str = Field(min_length=1)
    document_ids: list[UUID] = Field(min_length=1)

    @field_validator("question")
    @classmethod
    def normalize_question(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("question must not be empty")
        return normalized


class ChatCitation(BaseModel):
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


class ChatAskResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
    citations: list[ChatCitation]
    agent_run_id: UUID

    @field_validator("answer")
    @classmethod
    def normalize_answer(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("answer must not be empty")
        return normalized


__all__ = [
    "ChatAskRequest",
    "ChatAskResponse",
    "ChatCitation",
]
