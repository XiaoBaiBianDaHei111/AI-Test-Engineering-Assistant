"""Evidence endpoints (Phase 6): list / content / trace-parse."""

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import NotFoundError
from app.schemas import EvidenceRead, TraceParseRead
from app.services.assets import evidence_service

router = APIRouter()

_MEDIA_TYPES = {
    "screenshot": "image/png",
    "trace": "application/zip",
    "console": "application/json",
    "network": "application/json",
    "log": "text/plain",
}


@router.get("/runs/{run_id}/cases/{run_case_id}/evidence", response_model=list[EvidenceRead])
def list_case_evidence(run_id: int, run_case_id: int, db: Session = Depends(get_db)):
    return evidence_service.list_evidence(db, run_id, run_case_id)


@router.get("/runs/{run_id}/evidence", response_model=list[EvidenceRead])
def list_run_evidence(run_id: int, db: Session = Depends(get_db)):
    return evidence_service.list_evidence(db, run_id, run_case_id=None)


@router.get("/evidence/{evidence_id}/content")
def get_evidence_content(evidence_id: int, db: Session = Depends(get_db)):
    evidence = evidence_service.get_evidence_or_404(db, evidence_id)
    path = evidence_service.resolve_content_path(evidence)
    media_type = _MEDIA_TYPES.get(evidence.kind, "application/octet-stream")
    return FileResponse(path, media_type=media_type, filename=path.name)


@router.get("/evidence/{evidence_id}/trace-parse", response_model=TraceParseRead)
def get_trace_parse(evidence_id: int, db: Session = Depends(get_db)):
    # Ensure the evidence itself exists (404 vs "not parsed" semantics).
    evidence_service.get_evidence_or_404(db, evidence_id)
    trace_parse = evidence_service.get_trace_parse(db, evidence_id)
    if trace_parse is None:
        raise NotFoundError("Trace parse not found", {"evidence_id": evidence_id})
    return trace_parse
