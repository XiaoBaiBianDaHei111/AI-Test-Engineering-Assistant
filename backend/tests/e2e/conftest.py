"""e2e smoke fixtures (Phase 10, env-gated).

These tests require a running backend (demo app + demo API) and a real browser.
They are excluded by default via ``addopts = -m "not e2e"``; run them explicitly
with ``pytest -m e2e`` in a browser-ready environment (CI e2e job).
"""

import os

import httpx
import pytest

BASE_URL = os.environ.get("E2E_BASE_URL", "http://localhost:8000")


@pytest.fixture(scope="session")
def e2e_base_url():
    try:
        response = httpx.get(f"{BASE_URL}/api/health", timeout=5.0)
        response.raise_for_status()
    except Exception as exc:  # noqa: BLE001 - skip with a clear reason when backend is down
        pytest.skip(f"e2e backend not reachable at {BASE_URL}: {exc}")
    return BASE_URL


@pytest.fixture(scope="session")
def e2e_api(e2e_base_url):
    return httpx.Client(base_url=f"{e2e_base_url}/api", timeout=30.0)
