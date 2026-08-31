"""Report statistics aggregation (Phase 8, M1).

Single source of truth = the database. ``build_report_stats`` reads TestRun /
TestRunCase / TestStepResult / FailureAnalysis / Evidence / TestCase and returns
a JSON-serialisable dict consumed by the HTML generator, JSON export, and the
quality summarizer (statistics only — never raw case text).
"""

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Evidence, FailureAnalysis, TestCase, TestRun, TestRunCase

PRIORITIES = ("P0", "P1", "P2", "P3")
FAILURE_CATEGORIES = ("BROKEN_LOCATOR", "REAL_BUG", "FLAKY", "ENV_ISSUE")


def _pass_rate(passed: int, failed: int) -> float:
    denominator = max(1, passed + failed)
    return round(passed / denominator, 4)


def _priority_bucket(priority: str | None) -> str:
    return priority if priority in PRIORITIES else "unknown"


def build_report_stats(db: Session, run_id: int) -> dict:
    """Aggregate the full report statistics for a run."""
    run = db.scalar(
        select(TestRun)
        .options(selectinload(TestRun.run_cases).selectinload(TestRunCase.step_results))
        .where(TestRun.id == run_id)
    )
    if run is None:
        return {"run_id": run_id}

    run_cases = list(run.run_cases)

    # Failure analyses + evidence per case (indexed by run_case_id).
    analyses = {
        fa.run_case_id: fa
        for fa in db.scalars(
            select(FailureAnalysis).where(
                FailureAnalysis.run_case_id.in_([rc.id for rc in run_cases] or [0])
            )
        )
    }
    evidence_rows = list(
        db.scalars(
            select(Evidence).where(
                Evidence.run_case_id.in_([rc.id for rc in run_cases] or [0])
            )
        )
    )
    evidence_by_case: dict[int, dict] = {}
    for ev in evidence_rows:
        bucket = evidence_by_case.setdefault(
            ev.run_case_id, {"screenshots": [], "trace": [], "console": [], "network": []}
        )
        if ev.kind == "screenshot":
            bucket["screenshots"].append({
                "id": ev.id,
                "step_number": ev.meta.get("step_number") if isinstance(ev.meta, dict) else None,
                "size_bytes": ev.meta.get("size_bytes") if isinstance(ev.meta, dict) else None,
            })
        elif ev.kind in ("trace", "console", "network"):
            bucket[ev.kind].append({"id": ev.id})

    # TestCase priorities (deleted case -> unknown).
    priorities: dict[int, str | None] = {}
    case_ids = [rc.test_case_id for rc in run_cases if rc.test_case_id is not None]
    if case_ids:
        for tc in db.scalars(select(TestCase).where(TestCase.id.in_(case_ids))):
            priorities[tc.id] = tc.priority

    # Overview
    passed = sum(1 for rc in run_cases if rc.status == "passed")
    failed = sum(1 for rc in run_cases if rc.status == "failed")
    blocked = sum(1 for rc in run_cases if rc.status == "blocked")
    skipped = sum(1 for rc in run_cases if rc.status == "skipped")
    running = sum(1 for rc in run_cases if rc.status == "running")
    total = len(run_cases)

    overview = {
        "total": total,
        "passed": passed,
        "failed": failed,
        "blocked": blocked,
        "skipped": skipped,
        "running": running,
        "pass_rate": _pass_rate(passed, failed),
        "duration_ms": int(
            (run.ended_at - run.started_at).total_seconds() * 1000
        ) if (run.ended_at and run.started_at) else 0,
    }

    # Priority distribution
    priority_stats: dict[str, dict] = {p: {"total": 0, "passed": 0, "failed": 0} for p in PRIORITIES}
    priority_stats["unknown"] = {"total": 0, "passed": 0, "failed": 0}
    for rc in run_cases:
        bucket = _priority_bucket(priorities.get(rc.test_case_id))
        priority_stats[bucket]["total"] += 1
        if rc.status == "passed":
            priority_stats[bucket]["passed"] += 1
        elif rc.status == "failed":
            priority_stats[bucket]["failed"] += 1
    for bucket in priority_stats.values():
        bucket["pass_rate"] = _pass_rate(bucket["passed"], bucket["failed"])

    # Failure category distribution
    failure_categories = {c: 0 for c in FAILURE_CATEGORIES}
    for fa in analyses.values():
        if fa.category in failure_categories:
            failure_categories[fa.category] += 1

    # Case detail
    cases = []
    for rc in run_cases:
        fa = analyses.get(rc.id)
        cases.append({
            "case_label": rc.case_label,
            "status": rc.status,
            "duration_ms": rc.duration_ms,
            "error": (rc.error or "")[:2000],
            "priority": priorities.get(rc.test_case_id),
            "failure_analysis": (
                {
                    "category": fa.category,
                    "confidence": fa.confidence,
                    "reason": fa.reason,
                    "suggested_fix": fa.suggested_fix,
                    "decision_source": fa.decision_source,
                    "needs_human": fa.needs_human,
                    "status": fa.status,
                } if fa else None
            ),
            "evidence": evidence_by_case.get(rc.id, {
                "screenshots": [], "trace": [], "console": [], "network": [],
            }),
        })

    return {
        "run_id": run_id,
        "run_name": run.name,
        "run_status": run.status,
        "overview": overview,
        "priority": priority_stats,
        "failure_categories": failure_categories,
        "cases": cases,
    }
