"""One-command development DB reset + seed (P011 hotfix, P1-2).

Deletes the local SQLite development DB (the ``DATABASE_URL`` default) and
re-seeds. For Docker PostgreSQL, use ``docker compose down -v && up --build``
instead.

Usage (from ``backend/``):

    python scripts/reset_db.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import settings  # noqa: E402
from app.core.database import Base, engine  # noqa: E402


def main() -> None:
    url = settings.database_url
    if not url.startswith("sqlite"):
        print("reset_db only handles SQLite; use `docker compose down -v && up --build` for PostgreSQL.")
        sys.exit(1)

    # "sqlite:///./ai_test_workflow.db" -> the file path (relative to CWD).
    db_path = Path(url.removeprefix("sqlite:///"))
    if db_path.exists():
        db_path.unlink()
        print(f"deleted {db_path}")

    Base.metadata.create_all(bind=engine)
    print("schema recreated (create_all)")

    # Re-seed (idempotent).
    import seed

    seed.main()
    print("reset_db done.")


if __name__ == "__main__":
    main()
