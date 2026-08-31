"""Failure context builder (Phase 7): extract + evidence summary + length cap.

Assembles a bounded, JSON-serialisable context for the LLM layer from the
TestRunCase (error + failed steps), the executed script, and the run's evidence
(console errors, non-2xx network responses, screenshot presence). Every field is
individually capped and the whole payload is capped at
``FAILURE_CONTEXT_MAX_CHARS`` with a ``truncated`` flag when it overflows.
"""

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Evidence, TestRunCase
from app.services.assets import evidence_service

_ERROR_CAP = 2000
_FAILED_STEPS_CAP = 1000
_SCRIPT_CAP = 4000
_CONSOLE_ERRORS = 10
_NETWORK_NON_2XX = 10
_ENTRY_CAP = 200


def _read_evidence_json(evidence: Evidence) -> list:
    try:
        path = evidence_service.resolve_content_path(evidence)
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:  # noqa: BLE001 - degrade gracefully on missing/malformed evidence
        return []


def _evidence_summary(db: Session, run_case: TestRunCase) -> dict:
    rows = list(
        db.scalars(
            select(Evidence).where(Evidence.run_case_id == run_case.id)
        )
    )
    summary = {"console_errors": [], "network_non_2xx": [], "screenshot_count": 0}

    for row in rows:
        if row.kind == "screenshot":
            summary["screenshot_count"] += 1
        elif row.kind == "console":
            for entry in _read_evidence_json(row)[:_CONSOLE_ERRORS]:
                if entry.get("type") == "error":
                    summary["console_errors"].append(str(entry.get("text", ""))[:_ENTRY_CAP])
        elif row.kind == "network":
            for entry in _read_evidence_json(row)[:_NETWORK_NON_2XX]:
                status = entry.get("status")
                if status is not None and not (200 <= int(status) < 300):
                    summary["network_non_2xx"].append({
                        "url": str(entry.get("url", "")),
                        "status": status,
                    })
    return summary


def build_failure_context(db: Session, run_case: TestRunCase, script_text: str = "") -> dict:
    """Build the bounded failure context dict (used by the LLM layer)."""
    failed_steps = [
        {"step_number": s.step_number, "description": s.description, "message": s.message}
        for s in run_case.step_results
        if s.status == "failed"
    ]
    failed_steps_json = json.dumps(failed_steps, ensure_ascii=False)[:_FAILED_STEPS_CAP]

    payload = {
        "error": (run_case.error or "")[:_ERROR_CAP],
        "failed_steps": failed_steps_json,
        "script_summary": (script_text or "")[:_SCRIPT_CAP],
        "evidence_summary": _evidence_summary(db, run_case),
    }

    total = len(json.dumps(payload, ensure_ascii=False))
    truncated = total > settings.failure_context_max_chars
    if truncated:
        overhead = total - settings.failure_context_max_chars
        new_len = max(0, len(payload["script_summary"]) - overhead - 200)
        payload["script_summary"] = payload["script_summary"][:new_len]

    payload["truncated"] = truncated
    return payload
