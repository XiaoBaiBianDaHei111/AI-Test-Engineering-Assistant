"""APITestCase request/response schemas + assertion enums (Phase 9)."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class HttpMethod(str, Enum):
    get = "GET"
    post = "POST"
    put = "PUT"
    patch = "PATCH"
    delete = "DELETE"


class AssertionType(str, Enum):
    status = "status"
    json_field = "json_field"
    response_time = "response_time"
    header = "header"


class ApiTestCaseStatus(str, Enum):
    active = "active"
    archived = "archived"


class ApiAssertion(BaseModel):
    """A restricted assertion (P000 risks: only 4 pre-defined types)."""

    type: AssertionType
    expected: Any = None  # status int / json_field literal or "non_empty" / header str
    path: str | None = None  # json_field dot-path
    expected_ms: int | None = Field(default=None, ge=0)  # response_time
    name: str | None = None  # header name / response_time direction (less_than|greater_than)

    @model_validator(mode="after")
    def check_params(self) -> "ApiAssertion":
        if self.type == AssertionType.status:
            if not isinstance(self.expected, int):
                raise ValueError("status assertion requires an integer 'expected'")
        elif self.type == AssertionType.json_field:
            if not self.path:
                raise ValueError("json_field assertion requires 'path'")
        elif self.type == AssertionType.response_time:
            if self.expected_ms is None:
                raise ValueError("response_time assertion requires 'expected_ms'")
            if self.name is not None and self.name not in {"less_than", "greater_than"}:
                raise ValueError("response_time assertion 'name' must be 'less_than' or 'greater_than'")
        elif self.type == AssertionType.header:
            if not self.name or self.expected is None:
                raise ValueError("header assertion requires 'name' and 'expected'")
        return self


class ApiTestCaseCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    method: HttpMethod
    url: str = Field(..., min_length=1, max_length=500)
    headers: dict = Field(default_factory=dict)
    body: dict | None = None
    assertions: list[ApiAssertion] = Field(..., min_length=1)
    requirement_id: int | None = None
    status: ApiTestCaseStatus = Field(default=ApiTestCaseStatus.active)

    @field_validator("name")  # noqa: F821 - declared below
    @classmethod
    def strip_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("name must not be blank")
        return value


class ApiTestCaseUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    method: HttpMethod | None = None
    url: str | None = Field(default=None, min_length=1, max_length=500)
    headers: dict | None = None
    body: dict | None = None
    assertions: list[ApiAssertion] | None = None
    requirement_id: int | None = None
    status: ApiTestCaseStatus | None = None


class ApiTestCaseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    requirement_id: int | None
    name: str
    method: str
    url: str
    headers: dict
    body: dict | None
    assertions: list
    status: str
    created_at: datetime
    updated_at: datetime
