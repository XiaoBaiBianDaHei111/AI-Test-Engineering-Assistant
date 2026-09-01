"""FailureAnalysis request/response schemas + enums (Phase 7)."""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class FailureCategory(StrEnum):
    broken_locator = "BROKEN_LOCATOR"
    real_bug = "REAL_BUG"
    flaky = "FLAKY"
    env_issue = "ENV_ISSUE"


class DecisionSource(StrEnum):
    rule = "rule"
    llm = "llm"


class AnalysisStatus(StrEnum):
    pending = "pending"
    classified = "classified"
    confirmed = "confirmed"


class FailureAnalysisRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    run_case_id: int
    category: str
    confidence: float
    reason: str
    suggested_fix: str
    decision_source: str
    needs_human: bool
    status: str
    created_at: datetime
    updated_at: datetime


class FailureAnalysisCreate(BaseModel):
    run_case_id: int = Field(..., ge=1)
