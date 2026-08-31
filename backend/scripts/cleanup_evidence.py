"""Evidence retention cleanup (Phase 6, P6-008).

Deletes run directories under ``artifacts/`` whose mtime is older than
``EVIDENCE_RETENTION_DAYS`` (default 30). Only deletes files/directories — the
``Evidence`` / ``TraceParse`` rows are left intact (records stay for
traceability, the frontend shows a missing-file placeholder).

Idempotent; supports ``--dry-run``. Usage (from ``backend/``):

    python scripts/cleanup_evidence.py --dry-run
    python scripts/cleanup_evidence.py
"""

import argparse
import shutil
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import settings  # noqa: E402


def cleanup(artifacts_dir, retention_days, dry_run=False, now=None) -> dict:
    """Delete expired run dirs; return a summary dict (pure, testable)."""
    root = Path(artifacts_dir)
    if not root.exists():
        return {"scanned": 0, "deleted": 0, "kept": 0, "dry_run": dry_run}

    cutoff = (now or datetime.now()) - timedelta(days=retention_days)
    deleted = 0
    kept = 0
    for child in root.iterdir():
        # Only run directories (numeric names) are eligible.
        if not child.is_dir() or not child.name.isdigit():
            continue
        mtime = datetime.fromtimestamp(child.stat().st_mtime)
        if mtime < cutoff:
            if not dry_run:
                shutil.rmtree(child)
            deleted += 1
        else:
            kept += 1
    return {"scanned": deleted + kept, "deleted": deleted, "kept": kept, "dry_run": dry_run}


def main() -> None:
    parser = argparse.ArgumentParser(description="Delete expired evidence run directories")
    parser.add_argument("--dry-run", action="store_true", help="report without deleting")
    parser.add_argument(
        "--days", type=int, default=settings.evidence_retention_days,
        help=f"retention days (default {settings.evidence_retention_days})",
    )
    parser.add_argument(
        "--artifacts-dir", default=settings.artifacts_dir,
        help=f"artifacts directory (default {settings.artifacts_dir})",
    )
    args = parser.parse_args()

    summary = cleanup(args.artifacts_dir, args.days, dry_run=args.dry_run)
    action = "would delete" if summary["dry_run"] else "deleted"
    print(
        f"[cleanup_evidence] scanned={summary['scanned']} {action}={summary['deleted']} "
        f"kept={summary['kept']} (retention={args.days}d)"
    )


if __name__ == "__main__":
    main()
