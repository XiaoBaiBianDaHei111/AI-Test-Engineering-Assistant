"""TestPoint — a single thing-to-test derived from a requirement."""

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin

if TYPE_CHECKING:
    from app.models.test_case import TestCase

# TestPoint state machine: extracted -> confirmed -> archived
TEST_POINT_STATUSES = ("extracted", "confirmed", "archived")

# Restricted test-design techniques (frozen in P000 section 12 / P002 section 6.2).
TEST_POINT_TECHNIQUES = (
    "equivalence",
    "boundary",
    "state_transition",
    "exception",
    "error_guessing",
)


class TestPoint(Base, TimestampMixin):
    __tablename__ = "test_points"

    id: Mapped[int] = mapped_column(primary_key=True)
    # A test point derives from a requirement and has no value without it, so it
    # cascades (deleting the requirement deletes its test points).
    requirement_id: Mapped[int] = mapped_column(
        ForeignKey("requirements.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    technique: Mapped[str] = mapped_column(String(30), nullable=False, default="equivalence")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="extracted", index=True)

    requirement = relationship("Requirement", back_populates="test_points")
    test_cases: Mapped[list["TestCase"]] = relationship(back_populates="test_point")

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<TestPoint id={self.id} title={self.title!r} status={self.status}>"
