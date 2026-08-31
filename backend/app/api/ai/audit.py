"""GET /api/ai/audit — AI audit log listing (API level; frontend page is P2)."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas import AIAuditLogRead
from app.services.ai.audit import list_audit_logs

router = APIRouter()


@router.get("/audit", response_model=list[AIAuditLogRead])
def list_audit(
    agent: str | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    return list_audit_logs(db, agent=agent, status=status, limit=limit)
