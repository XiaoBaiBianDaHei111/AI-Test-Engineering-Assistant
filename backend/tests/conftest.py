"""Pytest fixtures: file SQLite database + FastAPI TestClient (real mode, P013).

Each test runs against a fresh, isolated file SQLite database. No mock/fake
provider is injected: pure-logic tests run offline; real-integration tests are
marked ``@pytest.mark.real`` and gated by ``require_llm_key``/``require_browser``.
"""

import os

# Force SQLite for the application engine (used by the app lifespan's create_all)
# so a local ``.env`` pointing at a remote PostgreSQL does not break tests. This
# must run before any ``app.*`` import (Settings is instantiated at import time).
os.environ["DATABASE_URL"] = "sqlite:///./ai_test_workflow.db"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import NullPool  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(autouse=True)
def _clear_cancel_requests():
    """The run-cancel flag is in-memory; clear it between tests to avoid leaks."""
    yield
    from app.services.assets import test_run_service

    test_run_service._cancel_requests.clear()


@pytest.fixture(autouse=True)
def _isolated_artifacts(tmp_path, monkeypatch):
    """Redirect script + evidence + report writes to a per-test temp dir (Phase 6/8)."""
    monkeypatch.setattr(settings, "artifacts_dir", str(tmp_path / "artifacts"))
    monkeypatch.setattr(settings, "reports_dir", str(tmp_path / "artifacts" / "reports"))
    yield


@pytest.fixture()
def require_llm_key():
    """Gate for real-LLM integration tests: skip without a DeepSeek key (P013)."""
    key = os.environ.get("DEEPSEEK_API_KEY") or settings.llm_api_key
    if not key:
        pytest.skip("real LLM test: no DEEPSEEK_API_KEY / LLM_API_KEY configured")


@pytest.fixture()
def require_browser():
    """Gate for real-browser integration tests: skip without Playwright browsers (P013)."""
    if not os.environ.get("PLAYWRIGHT_BROWSERS_PATH"):
        pytest.skip("real browser test: PLAYWRIGHT_BROWSERS_PATH not set")


@pytest.fixture()
def db_engine(tmp_path):
    # File-backed SQLite with NullPool: every session gets its own connection, so
    # background tasks (which open their own session) see committed data and run
    # without fighting a shared in-memory connection.
    engine = create_engine(
        f"sqlite:///{tmp_path / 'test.db'}",
        connect_args={"check_same_thread": False},
        poolclass=NullPool,
    )
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture()
def session_factory(db_engine):
    return sessionmaker(
        bind=db_engine, autoflush=False, autocommit=False, expire_on_commit=False
    )


@pytest.fixture()
def db_session(session_factory):
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def sample_project(client) -> dict:
    response = client.post(
        "/api/projects", json={"name": "Demo Project", "description": "demo"}
    )
    assert response.status_code == 201
    return response.json()


@pytest.fixture()
def confirmed_requirement(sample_project, client) -> dict:
    """Create and confirm (Gate 1) a requirement, returning its JSON."""
    created = client.post(
        f"/api/projects/{sample_project['id']}/requirements",
        json={"title": "用户登录", "description": "login flow"},
    ).json()
    confirmed = client.patch(
        f"/api/requirements/{created['id']}", json={"status": "confirmed"}
    ).json()
    assert confirmed["status"] == "confirmed"
    return confirmed


@pytest.fixture()
def confirmed_test_point(confirmed_requirement, client) -> dict:
    """Create and confirm (Gate 2) a test point under the confirmed requirement."""
    created = client.post(
        f"/api/requirements/{confirmed_requirement['id']}/test-points",
        json={"title": "正常登录", "technique": "equivalence"},
    ).json()
    confirmed = client.patch(
        f"/api/test-points/{created['id']}", json={"status": "confirmed"}
    ).json()
    assert confirmed["status"] == "confirmed"
    return confirmed
