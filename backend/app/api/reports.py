"""Report + quality summary endpoints (Phase 8)."""

from pathlib import Path

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse, PlainTextResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import NotFoundError
from app.schemas import QualitySummaryRead, TestReportRead
from app.services.assets import test_report_service

router = APIRouter()


def _download_name(report, ext: str) -> str:
    """B-5: semantic download name ``{run_name}-{report_id}.{ext}`` (ASCII-safe)."""
    run_name = (report.summary or {}).get("run_name") or f"run-{report.run_id}"
    return f"{run_name}-{report.id}.{ext}"


@router.get("/reports/{run_id}")
def get_report(run_id: int, db: Session = Depends(get_db)):
    detail = test_report_service.get_report_detail(db, run_id)
    detail["quality_summary"] = (
        QualitySummaryRead.model_validate(detail["quality_summary"]).model_dump(mode="json")
        if detail["quality_summary"] else None
    )
    return detail


@router.get("/reports/{run_id}/html")
def get_report_html(run_id: int, db: Session = Depends(get_db)):
    report = test_report_service.get_report_or_404(db, run_id)
    path = Path(report.html_path)
    if not path.exists():
        raise NotFoundError("Report HTML file not found", {"run_id": run_id})
    return FileResponse(path, media_type="text/html", filename=_download_name(report, "html"))


@router.post("/reports/{run_id}/generate", response_model=TestReportRead)
def generate_report(run_id: int, db: Session = Depends(get_db)):
    return test_report_service.generate_report(db, run_id)


@router.get("/reports")
def list_reports(
    project_id: int = Query(...),
    limit: int = Query(default=20, ge=1, le=200),
    db: Session = Depends(get_db),
):
    reports = test_report_service.list_reports(db, project_id, limit=limit)
    return [
        {
            "id": r.id,
            "run_id": r.run_id,
            "summary": r.summary,
            "created_at": r.created_at,
            "updated_at": r.updated_at,
            "recommendation": r.quality_summary.recommendation if r.quality_summary else None,
        }
        for r in reports
    ]


@router.get("/reports/{run_id}/export")
def export_report(run_id: int, format: str = Query("json"), db: Session = Depends(get_db)):
    report = test_report_service.get_report_or_404(db, run_id)
    if format == "markdown":
        # B-3: attach Content-Disposition so markdown downloads instead of inline-render.
        return PlainTextResponse(
            test_report_service.render_markdown_for_run(db, run_id),
            media_type="text/markdown",
            headers={"Content-Disposition": f'attachment; filename="{_download_name(report, "md")}"'},
        )
    path = Path(report.json_path)
    if not path.exists():
        raise NotFoundError("Report JSON file not found", {"run_id": run_id})
    return FileResponse(path, media_type="application/json", filename=_download_name(report, "json"))


@router.post("/quality-summary/{report_id}", response_model=QualitySummaryRead)
def generate_quality_summary(report_id: int, db: Session = Depends(get_db)):
    return test_report_service.generate_quality_summary(db, report_id)
