"""Shared test-local stubs (MINOR-002, P013).

These are *test* doubles (a driver stub and a script-generation stub), not project
mock infrastructure. They let orchestration-level tests exercise run_batch without
a real browser / LLM, while failing cases still resolve through the deterministic
rule layer.
"""

import io
import json
import zipfile

from app.execution.runner import (
    CaseOutcome,
    ConsoleEvidence,
    EvidenceArtifacts,
    NetworkEvidence,
    ScreenshotEvidence,
    StepOutcome,
)

LOCATOR_ERROR = 'Timeout 15000ms exceeded.\nwaiting for get_by_test_id("login-btn")'


def make_trace() -> bytes:
    """A minimal, valid Playwright trace.zip (one action/request/console event)."""
    lines = [
        json.dumps({"type": "before", "callId": "c1", "apiName": "page.goto", "startTime": 1000}),
        json.dumps({"type": "after", "callId": "c1", "endTime": 1050}),
        json.dumps({"type": "request", "sha1": "s1", "url": "http://example/", "method": "GET", "startTime": 1000, "endTime": 1010}),
        json.dumps({"type": "response", "sha1": "s1", "url": "http://example/", "status": 200}),
        json.dumps({"type": "console", "messageType": "log", "text": "hello"}),
    ]
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("trace.trace", "\n".join(lines) + "\n")
    return buf.getvalue()


class StubDriver:
    """Test-local ScriptExecutor: passes (or fails at one step) with fixed evidence."""

    def __init__(self, fail_step: int | None = None, fail_error: str = LOCATOR_ERROR, step_count: int = 5):
        self.fail_step = fail_step
        self.fail_error = fail_error
        self.step_count = step_count

    def execute(self, script_text: str, config: dict) -> CaseOutcome:
        steps: list[StepOutcome] = []
        evidence = EvidenceArtifacts()
        status = "passed"
        error = ""
        for i in range(1, self.step_count + 1):
            if self.fail_step is not None and i == self.fail_step:
                steps.append(StepOutcome(i, f"步骤{i}", "failed", self.fail_error, 10, False))
                evidence.screenshots.append(ScreenshotEvidence(i, f"步骤{i}", b"png"))
                status = "failed"
                error = self.fail_error
                break
            steps.append(StepOutcome(i, f"步骤{i}", "passed", "", 10, True))
            evidence.screenshots.append(ScreenshotEvidence(i, f"步骤{i}", b"png"))
        evidence.console.append(ConsoleEvidence("log", "hello", 1.0))
        evidence.network.append(NetworkEvidence("http://example/", "GET", 200, "document", 5))
        evidence.trace_bytes = make_trace()
        return CaseOutcome(status=status, duration_ms=100, steps=steps, error=error, evidence=evidence)


def success_script(db, test_case, config, provider):
    # Include the case title so script GET/PUT round-trips can target it.
    return {"status": "success", "script_text": f"# {test_case.title}\nSTEPS = []\n", "warnings": []}


def stub_execution(monkeypatch):
    """Keep run_batch offline: script generation + driver are test-local stubs."""
    monkeypatch.setattr("app.services.assets.test_run_service.generate_script", success_script)
    monkeypatch.setattr("app.services.assets.test_run_service.get_driver", lambda: StubDriver())


def make_script_generator(fail_title: str | None = None):
    def _gen(db, test_case, config, provider):
        if fail_title and fail_title in test_case.title:
            # locator-marker error so _maybe_analyze resolves via the rule layer.
            return {"status": "failed", "error_code": "waiting for get_by_test_id('x')", "script_text": ""}
        return {"status": "success", "script_text": "STEPS = []\n", "warnings": []}
    return _gen
