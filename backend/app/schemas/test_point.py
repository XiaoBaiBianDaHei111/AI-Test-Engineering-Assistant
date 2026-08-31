"""TestPoint request/response schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.enums import TestPointStatus, TestPointTechnique


class TestPointCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    technique: TestPointTechnique = Field(default=TestPointTechnique.equivalence)
    description: str = Field(default="", max_length=10000)

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


class TestPointUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    technique: TestPointTechnique | None = None
    description: str | None = Field(default=None, max_length=10000)
    status: TestPointStatus | None = None

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


class TestPointRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    requirement_id: int
    title: str
    technique: TestPointTechnique
    description: str
    status: TestPointStatus
    created_at: datetime
    updated_at: datetime
