"""Evidence / TraceParse — execution evidence entities (Phase 6)."""

from sqlalchemy import JSON, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin

EVIDENCE_KINDS = ("screenshot", "trace", "console", "network", "log")


class Evidence(Base, TimestampMixin):
    __tablename__ = "evidence"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(
        ForeignKey("test_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Nullable: run-level evidence (e.g. execution log) has no run_case_id.
    run_case_id: Mapped[int | None] = mapped_column(
        ForeignKey("test_run_cases.id", ondelete="CASCADE"), nullable=True, index=True
    )
    kind: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    # Relative path from the artifacts root (e.g. "3/screenshots/5_1.png").
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    meta: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    run = relationship("TestRun")
    run_case = relationship("TestRunCase")

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Evidence id={self.id} run={self.run_id} kind={self.kind}>"


class TraceParse(Base, TimestampMixin):
    __tablename__ = "trace_parses"

    id: Mapped[int] = mapped_column(primary_key=True)
    evidence_id: Mapped[int] = mapped_column(
        ForeignKey("evidence.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    actions: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    network: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    console: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    snapshots: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    evidence = relationship("Evidence")

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<TraceParse id={self.id} evidence_id={self.evidence_id}>"
