"""TestCaseReview — a single review record (human or AI) for a test case."""

from sqlalchemy import JSON, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin

REVIEWER_TYPES = ("ai", "human")
REVIEW_VERDICTS = ("approved", "needs_work")


class TestCaseReview(Base, TimestampMixin):
    __tablename__ = "test_case_reviews"

    id: Mapped[int] = mapped_column(primary_key=True)
    test_case_id: Mapped[int] = mapped_column(
        ForeignKey("test_cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    reviewer_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    verdict: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    # AI-only: {completeness, accuracy, executability} (0-5); human review keeps None.
    scores: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    issues: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    missing_scenarios: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    suggestions: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    test_case = relationship("TestCase", back_populates="reviews")

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<TestCaseReview id={self.id} type={self.reviewer_type} verdict={self.verdict}>"
