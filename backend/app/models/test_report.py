"""TestReport / QualitySummary — report & quality-summary entities (Phase 8)."""

from sqlalchemy import JSON, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin

RECOMMENDATIONS = ("GO", "CONDITIONAL_GO", "NO_GO")


class TestReport(Base, TimestampMixin):
    __tablename__ = "test_reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(
        ForeignKey("test_runs.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    html_path: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    json_path: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    # Compact statistics for list views (full stats live in the JSON file).
    summary: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    run = relationship("TestRun")
    quality_summary = relationship(
        "QualitySummary", back_populates="report", uselist=False,
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<TestReport id={self.id} run={self.run_id}>"


class QualitySummary(Base, TimestampMixin):
    __tablename__ = "quality_summaries"

    id: Mapped[int] = mapped_column(primary_key=True)
    report_id: Mapped[int] = mapped_column(
        ForeignKey("test_reports.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    overall_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pass_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    risk_factors: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    recommendation: Mapped[str] = mapped_column(String(20), nullable=False, default="NO_GO")
    reasoning: Mapped[str] = mapped_column(Text, nullable=False, default="")

    report = relationship("TestReport", back_populates="quality_summary")

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<QualitySummary id={self.id} report={self.report_id} {self.recommendation}>"
