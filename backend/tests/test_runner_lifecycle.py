"""PlaywrightDriver lifecycle tests (P6-001 SUGGESTION-2/4, AC-6-07)."""

import app.execution.runner as runner_mod
from app.execution.runner import PlaywrightDriver


def test_time_imported_at_module_level():
    # R005-A005 SUGGESTION-4: `import time` must be module-level, not inside execute.
    assert hasattr(runner_mod, "time")


class _FakeTracing:
    def start(self, **kwargs):
        pass

    def stop(self):
        return b""


class _FakeContext:
    def __init__(self, browser):
        self.browser = browser
        self.tracing = _FakeTracing()

    def new_page(self):
        raise RuntimeError("boom new_page")

    def close(self):
        self.browser.context_closed = True


class _FakeBrowser:
    def __init__(self):
        self.closed = False
        self.context_closed = False

    def new_context(self):
        return _FakeContext(self)

    def close(self):
        self.closed = True


class _FakeChromium:
    def __init__(self):
        self.created = []

    def launch(self, **kwargs):
        browser = _FakeBrowser()
        self.created.append(browser)
        return browser


class _FakePlaywright:
    def __init__(self, chromium):
        self.chromium = chromium

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


def test_browser_and_context_closed_on_new_page_failure(monkeypatch):
    chromium = _FakeChromium()
    monkeypatch.setattr(
        "playwright.sync_api.sync_playwright", lambda: _FakePlaywright(chromium)
    )
    monkeypatch.setattr(runner_mod, "load_script_module", lambda t: {"STEPS": [("step", lambda p: None)]})

    outcome = PlaywrightDriver().execute("script", {"headless": True})

    assert outcome.status == "failed"
    assert "boom new_page" in outcome.error
    browser = chromium.created[0]
    assert browser.closed is True
    assert browser.context_closed is True
