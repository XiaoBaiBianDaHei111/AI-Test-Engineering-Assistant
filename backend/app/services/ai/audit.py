"""AIAuditLog write + query helpers."""

import hashlib

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AIAuditLog


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def record_audit(
    db: Session,
    agent_name: str,
    schema_version: int,
    input_text: str,
    output_summary: str,
    tokens_in: int,
    tokens_out: int,
    latency_ms: int,
    status: str,
    failure_excerpt: str | None = None,
) -> AIAuditLog:
    """Create and return one audit record (one per agent invocation)."""
    log = AIAuditLog(
        agent_name=agent_name,
        schema_version=schema_version,
        input_hash=_hash(input_text or ""),
        input_summary=(input_text or "")[:200],
        output_summary=(output_summary or "")[:500],
        tokens_in=tokens_in or 0,
        tokens_out=tokens_out or 0,
        latency_ms=latency_ms or 0,
        status=status,
        failure_excerpt=(failure_excerpt or "")[:2000] if failure_excerpt else None,
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


def list_audit_logs(
    db: Session, agent: str | None = None, status: str | None = None, limit: int = 50
) -> list[AIAuditLog]:
    stmt = select(AIAuditLog)
    if agent:
        stmt = stmt.where(AIAuditLog.agent_name == agent)
    if status:
        stmt = stmt.where(AIAuditLog.status == status)
    stmt = stmt.order_by(AIAuditLog.created_at.desc(), AIAuditLog.id.desc()).limit(limit)
    return list(db.scalars(stmt))
