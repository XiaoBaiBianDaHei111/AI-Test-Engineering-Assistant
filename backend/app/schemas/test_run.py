"""TestRun / TestRunCase / TestStepResult request/response schemas."""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.schemas.failure_analysis import FailureAnalysisRead


class QaMode(StrEnum):
    none = "none"
    selector_change = "selector-change"
    logic_bug = "logic-bug"
    slow_network = "slow-network"
    auth_break = "auth-break"


class BrowserType(StrEnum):
    chromium = "chromium"


class RunConfig(BaseModel):
    base_url: str = Field(default="http://localhost:8001", max_length=300)
    qa_mode: QaMode = Field(default=QaMode.none)
    browser: BrowserType = Field(default=BrowserType.chromium)
    headless: bool = True


class TestRunCreate(BaseModel):
    project_id: int
    test_case_ids: list[int] = Field(default_factory=list)
    api_case_ids: list[int] = Field(default_factory=list)
    config: RunConfig = Field(default_factory=RunConfig)


class RunCreateResponse(BaseModel):
    run_id: int
    status: str  # started
    total: int


class TestStepResultRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    run_case_id: int
    step_number: int
    description: str
    status: str
    message: str
    duration_ms: int
    screenshot_ref: str | None
    element_found: bool


class TestRunCaseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    run_id: int
    test_case_id: int | None
    kind: str = "ui"
    api_case_id: int | None = None
    case_label: str
    status: str
    duration_ms: int
    error: str
    evidence_ids: list
    script_path: str
    created_at: datetime
    updated_at: datetime


class TestRunCaseDetail(TestRunCaseRead):
    step_results: list[TestStepResultRead] = Field(default_factory=list)
    # Nested failure analysis (Phase 7); computed at the endpoint, null when none.
    failure_analysis: FailureAnalysisRead | None = None


class TestRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    name: str
    status: str
    config: dict
    enqueued_at: datetime | None
    priority: int
    started_at: datetime | None
    ended_at: datetime | None
    created_at: datetime
    updated_at: datetime
    # Nested run cases (serialized as "cases"); populated from the ORM
    # ``run_cases`` relationship so both list and detail endpoints stay in sync
    # with the frontend contract.
    cases: list[TestRunCaseRead] = Field(default_factory=list, validation_alias="run_cases")

    # Aggregate counts computed from run cases at read time (no stored aggregates).
    @computed_field
    @property
    def total_count(self) -> int:
        return len(self.cases)

    @computed_field
    @property
    def passed_count(self) -> int:
        return sum(1 for c in self.cases if c.status == "passed")

    @computed_field
    @property
    def failed_count(self) -> int:
        return sum(1 for c in self.cases if c.status in ("failed", "blocked"))

    @computed_field
    @property
    def running_count(self) -> int:
        return sum(1 for c in self.cases if c.status == "running")
