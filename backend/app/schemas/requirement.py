"""Requirement request/response schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.enums import AssetSource, RequirementStatus


class RequirementCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: str = Field(default="", max_length=20000)
    acceptance_criteria: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    ambiguities: list[str] = Field(default_factory=list)
    status: RequirementStatus = Field(default=RequirementStatus.parsed)
    source: AssetSource = Field(default=AssetSource.manual)
    doc_ref: str | None = Field(default=None, max_length=255)

    @field_validator("title")
    @classmethod
    def strip_title(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("title must not be blank")
        return value

    @field_validator("description")
    @classmethod
    def strip_description(cls, value: str) -> str:
        return value.strip()


class RequirementUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=20000)
    acceptance_criteria: list[str] | None = None
    risks: list[str] | None = None
    gaps: list[str] | None = None
    ambiguities: list[str] | None = None
    status: RequirementStatus | None = None
    source: AssetSource | None = None
    doc_ref: str | None = None

    @field_validator("title")
    @classmethod
    def strip_title(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("title must not be blank")
        return value

    @field_validator("description")
    @classmethod
    def strip_description(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else value


class RequirementRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    title: str
    description: str
    acceptance_criteria: list[str]
    risks: list[str]
    gaps: list[str]
    ambiguities: list[str]
    status: RequirementStatus
    source: AssetSource
    doc_ref: str | None
    created_at: datetime
    updated_at: datetime
