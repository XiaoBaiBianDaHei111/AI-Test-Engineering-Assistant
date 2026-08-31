"""TestRun / TestRunCase / TestStepResult — execution result entities (Phase 5)."""

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin

RUN_STATUSES = ("pending", "running", "completed", "failed", "cancelled")
RUN_CASE_STATUSES = ("pending", "running", "passed", "failed", "blocked", "skipped")
STEP_STATUSES = ("passed", "failed")

QA_MODES = ("none", "selector-change", "logic-bug", "slow-network", "auth-break")


class TestRun(Base, TimestampMixin):
    __tablename__ = "test_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    config: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    # P2 queue fields (reserved, frozen in P000 section 12).
    enqueued_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    project = relationship("Project", back_populates="test_runs")
    run_cases: Mapped[list["TestRunCase"]] = relationship(
        back_populates="run", cascade="all, delete-orphan", order_by="TestRunCase.id"
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<TestRun id={self.id} status={self.status}>"


class TestRunCase(Base, TimestampMixin):
    __tablename__ = "test_run_cases"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(
        ForeignKey("test_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    test_case_id: Mapped[int | None] = mapped_column(
        ForeignKey("test_cases.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # Phase 9: kind ui/api + api_case_id (NULL for UI cases) — API cases reuse TestRun.
    kind: Mapped[str] = mapped_column(String(10), nullable=False, default="ui")
    api_case_id: Mapped[int | None] = mapped_column(
        ForeignKey("api_test_cases.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # Snapshot label ("TC-001 标题" / API 用例名) so history stays readable (D3).
    case_label: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error: Mapped[str] = mapped_column(Text, nullable=False, default="")
    evidence_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)  # Phase 6
    script_path: Mapped[str] = mapped_column(String(500), nullable=False, default="")

    run = relationship("TestRun", back_populates="run_cases")
    step_results: Mapped[list["TestStepResult"]] = relationship(
        back_populates="run_case",
        cascade="all, delete-orphan",
        order_by="TestStepResult.step_number",
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<TestRunCase id={self.id} status={self.status} label={self.case_label!r}>"


class TestStepResult(Base):
    __tablename__ = "test_step_results"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_case_id: Mapped[int] = mapped_column(
        ForeignKey("test_run_cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    step_number: Mapped[int] = mapped_column(Integer, nullable=False)
    # Snapshot of the step description for UI/report display (D3).
    description: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="passed")
    message: Mapped[str] = mapped_column(Text, nullable=False, default="")
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    screenshot_ref: Mapped[str | None] = mapped_column(String(500), nullable=True)  # Phase 6
    element_found: Mapped[bool] = mapped_column(default=True)

    run_case = relationship("TestRunCase", back_populates="step_results")

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<TestStepResult run_case_id={self.run_case_id} step={self.step_number} status={self.status}>"
