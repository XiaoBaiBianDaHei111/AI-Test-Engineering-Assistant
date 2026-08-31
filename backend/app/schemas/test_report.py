"""TestReport / QualitySummary request/response schemas + enums (Phase 8)."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class Recommendation(str, Enum):
    go = "GO"
    conditional_go = "CONDITIONAL_GO"
    no_go = "NO_GO"


class QualitySummaryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    report_id: int
    overall_score: int
    pass_rate: float
    risk_factors: list
    recommendation: str
    reasoning: str
    created_at: datetime
    updated_at: datetime


class TestReportRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    run_id: int
    html_path: str
    json_path: str
    summary: dict
    created_at: datetime
    updated_at: datetime
    quality_summary: QualitySummaryRead | None = Field(default=None)


class ReportDetail(TestReportRead):
    # Full statistics (read from the report JSON file at request time).
    stats: dict = Field(default_factory=dict)
