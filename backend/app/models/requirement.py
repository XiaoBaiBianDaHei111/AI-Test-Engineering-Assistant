"""Requirement — a structured requirement derived from (or manually entered for) a PRD."""

from typing import TYPE_CHECKING

from sqlalchemy import JSON, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin

if TYPE_CHECKING:
    from app.models.test_case import TestCase
    from app.models.test_point import TestPoint

# Requirement state machine (frozen in P000 section 12):
#   parsed -> confirmed -> archived
REQUIREMENT_STATUSES = ("parsed", "confirmed", "archived")

# Who/what produced this asset.
ASSET_SOURCES = ("ai", "manual")


class Requirement(Base, TimestampMixin):
    __tablename__ = "requirements"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # Structured analysis outputs (JSON lists). gaps/ambiguities are populated by
    # the Phase 2 requirements-analysis agent; stored from the start per MAJOR-003.
    acceptance_criteria: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    risks: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    gaps: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    ambiguities: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="parsed", index=True)
    source: Mapped[str] = mapped_column(String(10), nullable=False, default="manual")
    doc_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)

    project = relationship("Project", back_populates="requirements")
    test_cases: Mapped[list["TestCase"]] = relationship(back_populates="requirement")
    test_points: Mapped[list["TestPoint"]] = relationship(
        back_populates="requirement", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Requirement id={self.id} title={self.title!r}>"
