"""TestCase and TestCaseStep — the core test-asset entities.

Steps are stored in the ``TestCaseStep`` child table (not a JSON blob) per
MAJOR-003, so execution results can be recorded step-by-step in later phases.
"""

from typing import TYPE_CHECKING

from sqlalchemy import (
    JSON,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin

if TYPE_CHECKING:
    from app.models.test_case_review import TestCaseReview

# TestCase priority levels (P0 = most critical).
TEST_CASE_PRIORITIES = ("P0", "P1", "P2", "P3")

# TestCase type classification.
TEST_CASE_TYPES = (
    "smoke",
    "functional",
    "boundary",
    "exception",
    "performance",
    "security",
    "compatibility",
)

# TestCase state machine (frozen in P000 section 12):
#   draft -> pending_review -> approved / needs_work -> executed -> archived
TEST_CASE_STATUSES = (
    "draft",
    "pending_review",
    "approved",
    "needs_work",
    "executed",
    "archived",
)


class TestCase(Base, TimestampMixin):
    __tablename__ = "test_cases"
    __table_args__ = (
        UniqueConstraint("project_id", "case_id", name="uq_test_case_project_case_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Optional link to a requirement. SET NULL keeps the test case when its
    # requirement is deleted; deleting the project cascades and removes it.
    requirement_id: Mapped[int | None] = mapped_column(
        ForeignKey("requirements.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # Optional link to a test point (Phase 2, frozen in P000 section 12).
    # SET NULL keeps the test case when its test point is deleted.
    test_point_id: Mapped[int | None] = mapped_column(
        ForeignKey("test_points.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # Human-readable, project-scoped identifier such as "TC-001".
    case_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    priority: Mapped[str] = mapped_column(String(2), nullable=False, default="P2")
    type: Mapped[str] = mapped_column(String(30), nullable=False, default="functional")
    precondition: Mapped[str] = mapped_column(Text, nullable=False, default="")
    test_data: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    expected_result: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft", index=True)
    source: Mapped[str] = mapped_column(String(10), nullable=False, default="manual")

    steps: Mapped[list["TestCaseStep"]] = relationship(
        back_populates="test_case",
        cascade="all, delete-orphan",
        order_by="TestCaseStep.step_number",
    )
    project = relationship("Project", back_populates="test_cases")
    requirement = relationship("Requirement", back_populates="test_cases")
    test_point = relationship("TestPoint", back_populates="test_cases")
    reviews: Mapped[list["TestCaseReview"]] = relationship(
        back_populates="test_case",
        cascade="all, delete-orphan",
        order_by="TestCaseReview.created_at",
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<TestCase id={self.id} case_id={self.case_id!r} title={self.title!r}>"


class TestCaseStep(Base):
    __tablename__ = "test_case_steps"
    __table_args__ = (
        UniqueConstraint("test_case_id", "step_number", name="uq_test_case_step_number"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    test_case_id: Mapped[int] = mapped_column(
        ForeignKey("test_cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    step_number: Mapped[int] = mapped_column(Integer, nullable=False)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    expected_result: Mapped[str] = mapped_column(Text, nullable=False, default="")

    test_case = relationship("TestCase", back_populates="steps")

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<TestCaseStep test_case_id={self.test_case_id} step_number={self.step_number}>"
