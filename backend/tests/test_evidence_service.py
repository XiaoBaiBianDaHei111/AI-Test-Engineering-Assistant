"""Evidence service tests (P6-003, AC-6-03/6-06)."""

import pytest

from app.core.config import settings
from app.core.exceptions import NotFoundError, ValidationFailedError
from app.services.assets import evidence_service


def test_save_evidence_screenshot(db_session):
    ev = evidence_service.save_evidence(db_session, 7, 3, "screenshot", "3_1.png", b"\x89PNG")
    assert ev.id is not None
    assert ev.run_id == 7
    assert ev.run_case_id == 3
    assert ev.kind == "screenshot"
    assert ev.file_path == "7/screenshots/3_1.png"
    assert ev.meta["size_bytes"] == 4
    path = evidence_service.resolve_content_path(ev)
    assert path.is_file()
    assert path.read_bytes() == b"\x89PNG"


def test_save_evidence_rejects_bad_kind(db_session):
    with pytest.raises(ValidationFailedError):
        evidence_service.save_evidence(db_session, 1, None, "video", "x.mp4", b"data")


@pytest.mark.parametrize("filename", ["../evil.png", "a/b.png", "..", ".", ""])
def test_save_evidence_rejects_traversal_filename(db_session, filename):
    with pytest.raises(ValidationFailedError):
        evidence_service.save_evidence(db_session, 1, None, "screenshot", filename, b"data")


def test_resolve_content_path_rejects_traversal(db_session):
    ev = evidence_service.save_evidence(db_session, 1, None, "log", "run_1.log", b"data")
    ev.file_path = "../outside.txt"  # poison the stored path
    db_session.commit()
    with pytest.raises(NotFoundError):
        evidence_service.resolve_content_path(ev)


def test_resolve_content_path_missing_file(db_session):
    ev = evidence_service.save_evidence(db_session, 1, None, "log", "run_1.log", b"data")
    (evidence_service.run_dir(1) / "logs" / "run_1.log").unlink()
    with pytest.raises(NotFoundError):
        evidence_service.resolve_content_path(ev)


def test_get_evidence_not_found(db_session):
    with pytest.raises(NotFoundError):
        evidence_service.get_evidence_or_404(db_session, 9999)


def test_list_evidence_filters_run_vs_case(db_session):
    evidence_service.save_evidence(db_session, 1, None, "log", "run_1.log", b"log")
    evidence_service.save_evidence(db_session, 1, 5, "screenshot", "5_1.png", b"png")
    run_level = evidence_service.list_evidence(db_session, 1, run_case_id=None)
    case_level = evidence_service.list_evidence(db_session, 1, run_case_id=5)
    assert [e.kind for e in run_level] == ["log"]
    assert [e.kind for e in case_level] == ["screenshot"]


def test_volume_warning(monkeypatch, db_session, caplog):
    monkeypatch.setattr(settings, "evidence_max_run_bytes", 10)
    ev = evidence_service.save_evidence(db_session, 1, None, "trace", "1.zip", b"x" * 64)
    assert ev.meta["volume_exceeded"] is True
    assert any("evidence exceeds" in record.message for record in caplog.records)


def test_run_dir_built_from_server():
    assert evidence_service.run_dir(42).name == "42"
