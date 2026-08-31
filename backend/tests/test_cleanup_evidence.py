"""Evidence cleanup script tests (P6-008, AC-6-06)."""

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from cleanup_evidence import cleanup  # noqa: E402


def _age_dir(path: Path, age_days: int) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    mtime = (datetime.now() - timedelta(days=age_days)).timestamp()
    os.utime(path, (mtime, mtime))
    return path


def test_old_dir_deleted(tmp_path):
    artifacts = tmp_path / "artifacts"
    old = _age_dir(artifacts / "1", age_days=31)
    result = cleanup(artifacts, retention_days=30)
    assert result["deleted"] == 1
    assert not old.exists()


def test_new_dir_kept(tmp_path):
    artifacts = tmp_path / "artifacts"
    new = _age_dir(artifacts / "2", age_days=1)
    result = cleanup(artifacts, retention_days=30)
    assert result["kept"] == 1
    assert new.exists()


def test_dry_run_does_not_delete(tmp_path):
    artifacts = tmp_path / "artifacts"
    old = _age_dir(artifacts / "3", age_days=31)
    result = cleanup(artifacts, retention_days=30, dry_run=True)
    assert result["deleted"] == 1
    assert old.exists()


def test_non_numeric_dir_ignored(tmp_path):
    artifacts = tmp_path / "artifacts"
    other = _age_dir(artifacts / "notes", age_days=100)
    result = cleanup(artifacts, retention_days=30)
    assert result["deleted"] == 0
    assert other.exists()


def test_missing_dir(tmp_path):
    result = cleanup(tmp_path / "nope", retention_days=30)
    assert result["scanned"] == 0
    assert result["deleted"] == 0
