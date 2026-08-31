"""Failure analysis endpoints (Phase 7): get / retry / confirm."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import NotFoundError
from app.schemas import FailureAnalysisCreate, FailureAnalysisRead
from app.services.analysis.failure_analyzer import (
    analyze_failure,
    confirm_analysis,
    get_analysis,
)

router = APIRouter()


@router.get("/failure-analysis/{run_case_id}", response_model=FailureAnalysisRead)
def get_failure_analysis(run_case_id: int, db: Session = Depends(get_db)):
    analysis = get_analysis(db, run_case_id)
    if analysis is None:
        raise NotFoundError("Failure analysis not found", {"run_case_id": run_case_id})
    return analysis


@router.post("/failure-analysis", response_model=FailureAnalysisRead)
def retry_failure_analysis(payload: FailureAnalysisCreate, db: Session = Depends(get_db)):
    return analyze_failure(db, payload.run_case_id)


@router.post("/failure-analysis/{analysis_id}/confirm", response_model=FailureAnalysisRead)
def confirm(analysis_id: int, db: Session = Depends(get_db)):
    return confirm_analysis(db, analysis_id)
