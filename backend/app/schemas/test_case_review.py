"""TestCaseReview request/response schemas."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ReviewVerdict(str, Enum):
    approved = "approved"
    needs_work = "needs_work"


class ReviewerType(str, Enum):
    ai = "ai"
    human = "human"


class ReviewScores(BaseModel):
    completeness: int = Field(..., ge=0, le=5)
    accuracy: int = Field(..., ge=0, le=5)
    executability: int = Field(..., ge=0, le=5)


class TestCaseReviewCreate(BaseModel):
    """Human review input: verdict + optional notes."""
    verdict: ReviewVerdict
    issues: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)

    @field_validator("issues", "suggestions")
    @classmethod
    def strip_items(cls, value: list[str]) -> list[str]:
        return [item.strip() for item in value if item and item.strip()]


class TestCaseReviewRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    test_case_id: int
    reviewer_type: ReviewerType
    verdict: ReviewVerdict
    scores: dict | None
    issues: list[str]
    missing_scenarios: list[str]
    suggestions: list[str]
    created_at: datetime
    updated_at: datetime
