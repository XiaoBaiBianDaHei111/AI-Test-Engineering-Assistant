"""Evidence persistence service (Phase 6).

Files are written under ``artifacts/<run_id>/{screenshots,traces,console,network,logs}/``
(the Phase 1 frozen layout); every ``Evidence.file_path`` is a path *relative to
the artifacts root* built entirely by the server (no user-controlled fragments),
and content reads are resolved and re-checked to stay inside the run directory.
"""

from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import NotFoundError, ValidationFailedError
from app.core.logging import logger
from app.models import Evidence, TraceParse
from app.models.evidence import EVIDENCE_KINDS

_KIND_SUBDIR = {
    "screenshot": "screenshots",
    "trace": "traces",
    "console": "console",
    "network": "network",
    "log": "logs",
}


def run_dir(run_id: int) -> Path:
    """Artifacts directory for a run (server-built, no user fragments)."""
    return Path(settings.artifacts_dir) / str(run_id)


def _run_dir_size_bytes(run_id: int) -> int:
    directory = run_dir(run_id)
    if not directory.exists():
        return 0
    return sum(f.stat().st_size for f in directory.rglob("*") if f.is_file())


def _validate_filename(filename: str) -> str:
    """A filename must be a plain basename (no separators, no traversal)."""
    if not filename or filename in {".", ".."}:
        raise ValidationFailedError("Invalid evidence filename", {"filename": filename})
    if Path(filename).name != filename:
        raise ValidationFailedError("Evidence filename must be a basename", {"filename": filename})
    return filename


def _evidence_path(run_id: int, kind: str, filename: str) -> Path:
    """Build the absolute write path for an evidence file."""
    subdir = _KIND_SUBDIR[kind]
    return run_dir(run_id) / subdir / _validate_filename(filename)


def save_evidence(
    db: Session,
    run_id: int,
    run_case_id: int | None,
    kind: str,
    filename: str,
    data: bytes,
    meta: dict | None = None,
) -> Evidence:
    """Write an evidence file and its index row; warn (never fail) on volume cap."""
    if kind not in EVIDENCE_KINDS:
        raise ValidationFailedError("Unknown evidence kind", {"kind": kind})

    path = _evidence_path(run_id, kind, filename)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)

    # Relative path from the artifacts root (forward slashes, cross-platform).
    relative = (Path(str(run_id)) / _KIND_SUBDIR[kind] / _validate_filename(filename)).as_posix()

    record_meta = dict(meta or {})
    record_meta["size_bytes"] = len(data)
    if _run_dir_size_bytes(run_id) > settings.evidence_max_run_bytes:
        record_meta["volume_exceeded"] = True
        logger.warning("run %s evidence exceeds %s bytes", run_id, settings.evidence_max_run_bytes)

    evidence = Evidence(
        run_id=run_id, run_case_id=run_case_id, kind=kind,
        file_path=relative, meta=record_meta,
    )
    db.add(evidence)
    db.commit()
    db.refresh(evidence)
    return evidence


def list_evidence(db: Session, run_id: int, run_case_id: int | None = None) -> list[Evidence]:
    query = select(Evidence).where(Evidence.run_id == run_id)
    if run_case_id is not None:
        query = query.where(Evidence.run_case_id == run_case_id)
    else:
        query = query.where(Evidence.run_case_id.is_(None))  # run-level only
    return list(
        db.scalars(query.order_by(Evidence.kind, Evidence.id.desc()))
    )


def get_evidence_or_404(db: Session, evidence_id: int) -> Evidence:
    evidence = db.get(Evidence, evidence_id)
    if evidence is None:
        raise NotFoundError("Evidence not found", {"id": evidence_id})
    return evidence


def resolve_content_path(evidence: Evidence) -> Path:
    """Resolve an evidence file's on-disk path, rejecting traversal outside the run dir."""
    root = run_dir(evidence.run_id).resolve()
    candidate = (Path(settings.artifacts_dir) / evidence.file_path).resolve()
    if root != candidate.parent and root not in candidate.parents:
        raise NotFoundError("Evidence file not found", {"id": evidence.id})
    if not candidate.is_file():
        raise NotFoundError("Evidence file not found", {"id": evidence.id})
    return candidate


def get_trace_parse(db: Session, evidence_id: int) -> TraceParse | None:
    return db.scalar(select(TraceParse).where(TraceParse.evidence_id == evidence_id))
