"""Test report + quality summary service (Phase 8)."""

import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.core.exceptions import NotFoundError, ValidationFailedError
from app.models import (
    Evidence,
    FailureAnalysis,
    QualitySummary,
    TestReport,
    TestRun,
)
from app.services.ai.agents.quality_summarizer import (
    analyze_with_llm,
    derive_recommendation,
)
from app.services.ai.providers import LLMProvider, get_provider
from app.services.analysis.report_html import render as render_html
from app.services.analysis.report_markdown import render as render_markdown
from app.services.analysis.report_stats import build_report_stats
from app.services.assets import evidence_service


def _report_path(report_id: int, ext: str) -> Path:
    return Path(settings.reports_dir) / f"{report_id}.{ext}"


def _screenshot_provider(db: Session):
    def read(evidence_id: int) -> bytes | None:
        evidence = db.get(Evidence, evidence_id)
        if evidence is None:
            return None
        try:
            return evidence_service.resolve_content_path(evidence).read_bytes()
        except Exception:  # noqa: BLE001 - missing evidence degrades to placeholder
            return None
    return read


def _upsert_report(db: Session, run: TestRun, stats: dict, summary: dict) -> TestReport:
    # D6 pattern: delete + reinsert so a previous report is cleanly replaced.
    existing = db.scalar(select(TestReport).where(TestReport.run_id == run.id))
    if existing is not None:
        db.delete(existing)
        db.flush()

    report = TestReport(run_id=run.id, html_path="", json_path="", summary=summary)
    db.add(report)
    db.flush()  # assign report.id for file naming

    html_path = _report_path(report.id, "html")
    json_path = _report_path(report.id, "json")
    html_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_text(render_html(stats, _screenshot_provider(db)), encoding="utf-8")
    json_path.write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")

    report.html_path = str(html_path)
    report.json_path = str(json_path)
    db.commit()
    db.refresh(report)
    return report


def generate_report(db: Session, run_id: int) -> TestReport:
    """Generate (or regenerate) the report for a completed/failed run."""
    run = db.get(TestRun, run_id)
    if run is None:
        raise NotFoundError("Test run not found", {"id": run_id})
    if run.status not in {"completed", "failed"}:
        raise ValidationFailedError(
            "Report can only be generated for completed/failed runs",
            {"run_id": run_id, "status": run.status},
        )

    stats = build_report_stats(db, run_id)
    overview = stats.get("overview", {})
    summary = {
        "run_id": run_id,
        "run_name": stats.get("run_name", ""),
        "run_status": run.status,
        "total": overview.get("total", 0),
        "passed": overview.get("passed", 0),
        "failed": overview.get("failed", 0),
        "blocked": overview.get("blocked", 0),
        "skipped": overview.get("skipped", 0),
        "pass_rate": overview.get("pass_rate", 0.0),
        "duration_ms": overview.get("duration_ms", 0),
    }
    return _upsert_report(db, run, stats, summary)


def get_report_or_404(db: Session, run_id: int) -> TestReport:
    report = db.scalar(
        select(TestReport)
        .options(selectinload(TestReport.quality_summary))
        .where(TestReport.run_id == run_id)
    )
    if report is None:
        raise NotFoundError("Report not found", {"run_id": run_id})
    return report


def list_reports(db: Session, project_id: int, limit: int = 20) -> list[TestReport]:
    return list(
        db.scalars(
            select(TestReport)
            .options(selectinload(TestReport.quality_summary))
            .join(TestRun, TestReport.run_id == TestRun.id)
            .where(TestRun.project_id == project_id)
            .order_by(TestReport.created_at.desc(), TestReport.id.desc())
            .limit(limit)
        )
    )


def get_report_detail(db: Session, run_id: int) -> dict:
    report = get_report_or_404(db, run_id)
    stats = {}
    try:
        if report.json_path:
            stats = json.loads(Path(report.json_path).read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 - degrade to empty stats
        stats = {}
    return {
        "id": report.id,
        "run_id": report.run_id,
        "html_path": report.html_path,
        "json_path": report.json_path,
        "summary": report.summary,
        "created_at": report.created_at,
        "updated_at": report.updated_at,
        "quality_summary": report.quality_summary,
        "stats": stats,
    }


def _stats_summary_for_llm(db: Session, run_id: int, stats: dict) -> dict:
    """Statistics-only input for the LLM (no raw case text — prevents hallucination)."""
    overview = stats.get("overview", {})
    run = db.scalar(
        select(TestRun).options(selectinload(TestRun.run_cases)).where(TestRun.id == run_id)
    )
    case_ids = [rc.id for rc in run.run_cases] if run else []
    needs_human_count = 0
    if case_ids:
        needs_human_count = len(
            db.scalars(
                select(FailureAnalysis.id).where(
                    FailureAnalysis.run_case_id.in_(case_ids),
                    FailureAnalysis.needs_human.is_(True),
                    FailureAnalysis.status != "confirmed",
                )
            ).all()
        )
    return {
        "overview": overview,
        "priority": stats.get("priority", {}),
        "failure_categories": stats.get("failure_categories", {}),
        "needs_human_count": needs_human_count,
        "blocked_count": overview.get("blocked", 0),
    }


def generate_quality_summary(
    db: Session, report_id: int, provider: LLMProvider | None = None
) -> QualitySummary:
    report = db.get(TestReport, report_id)
    if report is None:
        raise NotFoundError("Report not found", {"id": report_id})

    stats = {}
    try:
        if report.json_path:
            stats = json.loads(Path(report.json_path).read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        stats = {}

    provider = provider or get_provider()
    llm_summary_input = _stats_summary_for_llm(db, report.run_id, stats)
    item = analyze_with_llm(db, llm_summary_input, provider)

    # MINOR-001: recommendation + overall_score are rule-derived (never trust LLM).
    pass_rate = float(stats.get("overview", {}).get("pass_rate", 0.0))
    blocked = int(stats.get("overview", {}).get("blocked", 0))
    recommendation = derive_recommendation(pass_rate, blocked)
    overall_score = round(pass_rate * 100)

    # upsert
    existing = db.scalar(select(QualitySummary).where(QualitySummary.report_id == report_id))
    if existing is not None:
        db.delete(existing)
        db.flush()
    summary = QualitySummary(
        report_id=report_id,
        overall_score=overall_score,
        pass_rate=pass_rate,
        risk_factors=item["risk_factors"],
        recommendation=recommendation,
        reasoning=item["reasoning"],
    )
    db.add(summary)
    db.commit()
    db.refresh(summary)
    return summary


def render_markdown_for_run(db: Session, run_id: int) -> str:
    report = get_report_or_404(db, run_id)
    stats = {}
    try:
        if report.json_path:
            stats = json.loads(Path(report.json_path).read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        stats = {}
    return render_markdown(stats)
