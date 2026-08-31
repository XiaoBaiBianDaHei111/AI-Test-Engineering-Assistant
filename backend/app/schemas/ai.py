"""AI request/response schemas and AI output schemas (Phase 2).

``SCHEMA_VERSION`` must be kept in sync manually across three places:
    1. this module (Pydantic output schemas),
    2. the prompt YAML files (``schema_version`` field),
    3. AIAuditLog.schema_version (written from this constant).
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.api_test_case import ApiAssertion, HttpMethod
from app.schemas.enums import TestCasePriority, TestCaseType, TestPointTechnique
from app.schemas.requirement import RequirementRead
from app.schemas.test_point import TestPointRead

SCHEMA_VERSION = 7

FailureCategoryLiteral = Literal["BROKEN_LOCATOR", "REAL_BUG", "FLAKY", "ENV_ISSUE"]
RecommendationLiteral = Literal["GO", "CONDITIONAL_GO", "NO_GO"]


# ---------------------------------------------------------------------------
# AI output schemas (what the LLM is asked to produce, then validated against)
# ---------------------------------------------------------------------------

class RequirementItem(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: str = Field(default="", max_length=20000)
    acceptance_criteria: list[str] = Field(..., min_length=1)
    risks: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    ambiguities: list[str] = Field(default_factory=list)


class AnalysisResult(BaseModel):
    requirements: list[RequirementItem] = Field(default_factory=list)


class TestPointItem(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    technique: TestPointTechnique
    description: str = Field(default="", max_length=10000)


class TestPointResult(BaseModel):
    test_points: list[TestPointItem] = Field(default_factory=list)


class TestCaseStepItem(BaseModel):
    action: str = Field(..., min_length=1)
    expected_result: str = Field(default="")


class TestCaseItem(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    priority: TestCasePriority
    type: TestCaseType
    precondition: str = Field(default="")
    steps: list[TestCaseStepItem] = Field(..., min_length=3)
    test_data: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def last_step_has_expected(self) -> "TestCaseItem":
        if self.steps and not self.steps[-1].expected_result.strip():
            raise ValueError("last step expected_result must not be empty")
        return self


class TestCaseListResult(BaseModel):
    test_cases: list[TestCaseItem] = Field(default_factory=list)


class ReviewScores(BaseModel):
    completeness: int = Field(..., ge=0, le=5)
    accuracy: int = Field(..., ge=0, le=5)
    executability: int = Field(..., ge=0, le=5)


class TestCaseReviewItem(BaseModel):
    scores: ReviewScores
    # verdict is optional: the system recomputes it from scores (never trusts the LLM).
    verdict: str | None = None
    issues: list[str] = Field(default_factory=list)
    missing_scenarios: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)


class ReviewResult(BaseModel):
    review: list[TestCaseReviewItem] = Field(default_factory=list)


class ScriptStepItem(BaseModel):
    description: str = Field(..., min_length=1, max_length=300)
    code: str = Field(..., min_length=1, max_length=500)


class ScriptResult(BaseModel):
    script: list[ScriptStepItem] = Field(default_factory=list)


class FailureAnalysisItem(BaseModel):
    category: FailureCategoryLiteral
    confidence: float = Field(..., ge=0, le=1)
    reason: str = Field(..., min_length=1, max_length=1000)
    suggested_fix: str = Field(..., min_length=1, max_length=1000)


class FailureAnalysisResult(BaseModel):
    analysis: list[FailureAnalysisItem] = Field(default_factory=list)


class QualitySummaryItem(BaseModel):
    overall_score: int = Field(..., ge=0, le=100)
    recommendation: RecommendationLiteral
    risk_factors: list[str] = Field(default_factory=list)
    reasoning: str = Field(..., min_length=1, max_length=2000)


class QualitySummaryResult(BaseModel):
    quality_summary: list[QualitySummaryItem] = Field(default_factory=list)


class ApiTestCaseItem(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    method: HttpMethod
    url: str = Field(..., min_length=1, max_length=500)
    headers: dict = Field(default_factory=dict)
    body: dict | None = None
    assertions: list[ApiAssertion] = Field(..., min_length=1)


class ApiTestCaseResult(BaseModel):
    api_test_cases: list[ApiTestCaseItem] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# API request schemas
# ---------------------------------------------------------------------------

class AnalyzeRequirementRequest(BaseModel):
    project_id: int
    prd_text: str = Field(..., min_length=1, max_length=500_000)


class ExtractTestPointsRequest(BaseModel):
    requirement_id: int


class GenerateTestCasesRequest(BaseModel):
    project_id: int
    test_point_ids: list[int] = Field(..., min_length=1)


class ReviewTestCasesRequest(BaseModel):
    test_case_ids: list[int] = Field(..., min_length=1, max_length=50)


# ---------------------------------------------------------------------------
# API response schemas
# ---------------------------------------------------------------------------

class AnalyzeRequirementResponse(BaseModel):
    status: str  # success | partial | failed
    requirements: list[RequirementRead]
    warnings: list[str]


class ExtractTestPointsResponse(BaseModel):
    status: str  # success | partial | failed
    test_points: list[TestPointRead]
    warnings: list[str]


class GenerateTestCasesResponse(BaseModel):
    run_id: int
    status: str  # started
    total: int


class ReviewTestCasesResponse(BaseModel):
    reviewed: int
    failed: list[dict]
    warnings: list[str]


class AIAuditLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    agent_name: str
    schema_version: int
    input_hash: str
    input_summary: str
    output_summary: str
    tokens_in: int
    tokens_out: int
    latency_ms: int
    status: str
    failure_excerpt: str | None = None
    created_at: datetime
