"""APITestCase — REST interface test-case entity (Phase 9)."""

from sqlalchemy import JSON, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin

HTTP_METHODS = ("GET", "POST", "PUT", "PATCH", "DELETE")
API_CASE_STATUSES = ("active", "archived")


class APITestCase(Base, TimestampMixin):
    __tablename__ = "api_test_cases"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    requirement_id: Mapped[int | None] = mapped_column(
        ForeignKey("requirements.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    method: Mapped[str] = mapped_column(String(10), nullable=False, default="GET")
    url: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    headers: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    body: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    assertions: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", index=True)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<APITestCase id={self.id} {self.method} {self.url}>"
