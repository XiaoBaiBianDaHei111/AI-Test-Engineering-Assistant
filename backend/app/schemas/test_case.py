"""TestCase / TestCaseStep request/response schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.enums import AssetSource, TestCasePriority, TestCaseStatus, TestCaseType


class TestCaseStepCreate(BaseModel):
    step_number: int = Field(..., ge=1)
    action: str = Field(..., min_length=1)
    expected_result: str = Field(default="")

    @field_validator("action")
    @classmethod
    def strip_action(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("action must not be blank")
        return value


class TestCaseStepRead(TestCaseStepCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int


class TestCaseCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    # Optional; when omitted a project-scoped id is auto-generated (TC-001, ...).
    case_id: str | None = Field(default=None, max_length=50)
    priority: TestCasePriority = Field(default=TestCasePriority.P2)
    type: TestCaseType = Field(default=TestCaseType.functional)
    precondition: str = Field(default="")
    test_data: dict = Field(default_factory=dict)
    expected_result: str = Field(default="")
    status: TestCaseStatus = Field(default=TestCaseStatus.draft)
    source: AssetSource = Field(default=AssetSource.manual)
    requirement_id: int | None = None
    test_point_id: int | None = None
    steps: list[TestCaseStepCreate] = Field(default_factory=list)

    @field_validator("title")
    @classmethod
    def strip_title(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("title must not be blank")
        return value

    @field_validator("case_id")
    @classmethod
    def strip_case_id(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else value

    @model_validator(mode="after")
    def validate_steps(self) -> "TestCaseCreate":
        numbers = [step.step_number for step in self.steps]
        if len(numbers) != len(set(numbers)):
            raise ValueError("step_number must be unique within a test case")
        return self


class TestCaseUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    priority: TestCasePriority | None = None
    type: TestCaseType | None = None
    precondition: str | None = None
    test_data: dict | None = None
    expected_result: str | None = None
    status: TestCaseStatus | None = None
    source: AssetSource | None = None
    requirement_id: int | None = None
    test_point_id: int | None = None
    # When provided, replaces the full step list. Omitted = leave steps unchanged.
    steps: list[TestCaseStepCreate] | None = None

    @field_validator("title")
    @classmethod
    def strip_title(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("title must not be blank")
        return value

    @model_validator(mode="after")
    def validate_steps(self) -> "TestCaseUpdate":
        if self.steps is not None:
            numbers = [step.step_number for step in self.steps]
            if len(numbers) != len(set(numbers)):
                raise ValueError("step_number must be unique within a test case")
        return self


class TestCaseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    requirement_id: int | None
    test_point_id: int | None
    case_id: str
    title: str
    priority: TestCasePriority
    type: TestCaseType
    precondition: str
    test_data: dict
    expected_result: str
    status: TestCaseStatus
    source: AssetSource
    steps: list[TestCaseStepRead]
    created_at: datetime
    updated_at: datetime
