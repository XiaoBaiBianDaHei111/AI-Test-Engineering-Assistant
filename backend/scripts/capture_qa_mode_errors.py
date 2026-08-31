"""Capture real Playwright error text per demo-app qaMode (Phase 6, P6-011).

Runs the Golden-PRD login flow against each fault-injection mode and writes the
actual Python Playwright error string to ``tests/fixtures/qa_mode_errors/<qa_mode>.txt``.
These samples are the Golden data for Phase 7 rule-signature tables.

Requires a browser (``playwright install chromium``) and the backend serving the
demo app at ``BASE_URL``. Env-gated: in a browser-less sandbox this script is not
run — the verification gap is recorded in A006 and Phase 7 falls back to known
Python error patterns + rule-layer unit tests.

Usage (from ``backend/``):

    python scripts/capture_qa_mode_errors.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

BASE_URL = "http://localhost:8000"
QA_MODES = ["selector-change", "logic-bug", "slow-network", "auth-break"]
OUT_DIR = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "qa_mode_errors"
CREDENTIALS = {"username": "testuser", "password": "Test@1234"}


def _login_flow(page, qa_mode: str) -> None:
    page.goto(f"{BASE_URL}/demo/?qaMode={qa_mode}")
    page.get_by_test_id("username").fill(CREDENTIALS["username"])
    page.get_by_test_id("password").fill(CREDENTIALS["password"])
    page.get_by_test_id("login-btn").click()
    # A successful login lands on the task view (Golden PRD semantics).
    page.get_by_test_id("task-title").wait_for(timeout=5000)


def main() -> None:
    from playwright.sync_api import sync_playwright

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            for qa_mode in QA_MODES:
                page = browser.new_page()
                page.set_default_timeout(5000)
                error_text = ""
                try:
                    _login_flow(page, qa_mode)
                except Exception as exc:  # noqa: BLE001 - capture the raw error text
                    error_text = str(exc)
                finally:
                    page.close()
                (OUT_DIR / f"{qa_mode}.txt").write_text(error_text, encoding="utf-8")
                print(f"[{qa_mode}] -> {error_text[:100] if error_text else 'NO ERROR'}")
        finally:
            browser.close()


if __name__ == "__main__":
    main()
