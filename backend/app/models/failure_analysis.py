"""FailureAnalysis — AI failure classification result entity (Phase 7)."""

from sqlalchemy import JSON, Boolean, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin

FAILURE_CATEGORIES = ("BROKEN_LOCATOR", "REAL_BUG", "FLAKY", "ENV_ISSUE")
DECISION_SOURCES = ("rule", "llm")
ANALYSIS_STATUSES = ("pending", "classified", "confirmed")


class FailureAnalysis(Base, TimestampMixin):
    __tablename__ = "failure_analyses"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_case_id: Mapped[int] = mapped_column(
        ForeignKey("test_run_cases.id", ondelete="CASCADE"),
        nullable=False, unique=True, index=True,
    )
    category: Mapped[str] = mapped_column(String(30), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    suggested_fix: Mapped[str] = mapped_column(Text, nullable=False, default="")
    decision_source: Mapped[str] = mapped_column(String(10), nullable=False, default="llm")
    needs_human: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")

    run_case = relationship("TestRunCase")

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<FailureAnalysis id={self.id} run_case={self.run_case_id} {self.category}>"
