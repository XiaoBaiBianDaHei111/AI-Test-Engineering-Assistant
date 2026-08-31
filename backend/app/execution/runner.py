"""Playwright execution engine (Phase 5) + evidence collection (Phase 6).

``ScriptExecutor`` is the driver protocol; ``PlaywrightDriver`` is the only
implementation (real headless chromium, P013 removed the fake stand-in).
"""

import time
from dataclasses import dataclass, field
from typing import Protocol

from app.core.config import settings

# Python Playwright locator-error signatures (also used by Phase 7 rule layer).
_LOCATOR_ERROR_MARKERS = (
    "waiting for",
    "get_by_test_id",
    "locator",
    "resolve",
    "Timeout",
    "strict mode violation",
)


@dataclass
class StepOutcome:
    step_number: int
    description: str
    status: str  # passed | failed
    message: str
    duration_ms: int
    element_found: bool


@dataclass
class ScreenshotEvidence:
    step_number: int
    description: str
    bytes: bytes


@dataclass
class ConsoleEvidence:
    type: str
    text: str
    timestamp: float


@dataclass
class NetworkEvidence:
    url: str
    method: str
    status: int
    resource_type: str
    duration_ms: int
    # Phase 9: API responses carry a truncated body (browser network does not).
    response_body: str = ""
    body_truncated: bool = False


@dataclass
class EvidenceArtifacts:
    """Execution evidence captured by a driver (Phase 6, deviation D1)."""

    screenshots: list[ScreenshotEvidence] = field(default_factory=list)
    console: list[ConsoleEvidence] = field(default_factory=list)
    network: list[NetworkEvidence] = field(default_factory=list)
    trace_bytes: bytes = b""


@dataclass
class CaseOutcome:
    status: str  # passed | failed
    duration_ms: int
    steps: list[StepOutcome] = field(default_factory=list)
    error: str = ""
    evidence: EvidenceArtifacts = field(default_factory=EvidenceArtifacts)


def load_script_module(script_text: str) -> dict:
    """Compile + exec a generated script, returning its namespace (has STEPS)."""
    namespace: dict = {"__name__": "generated_script"}
    exec(compile(script_text, "<script>", "exec"), namespace)
    return namespace


def is_locator_error(message: str) -> bool:
    return any(marker in message for marker in _LOCATOR_ERROR_MARKERS)


class ScriptExecutor(Protocol):
    def execute(self, script_text: str, config: dict) -> CaseOutcome: ...


class PlaywrightDriver:
    """Runs the generated script in a real (headless) chromium and collects evidence."""

    def execute(self, script_text: str, config: dict) -> CaseOutcome:
        from playwright.sync_api import sync_playwright

        module = load_script_module(script_text)
        steps = module.get("STEPS", [])
        headless = config.get("headless", True)
        timeout_ms = settings.playwright_action_timeout_ms

        run_started = time.monotonic()
        outcomes: list[StepOutcome] = []
        status = "passed"
        error = ""
        evidence = EvidenceArtifacts()

        browser = None
        context = None
        request_starts: dict[str, float] = {}

        def _ms(started: float) -> int:
            return int((time.monotonic() - started) * 1000)

        def on_console(msg) -> None:
            evidence.console.append(
                ConsoleEvidence(type=msg.type, text=msg.text, timestamp=time.time())
            )

        def on_request(request) -> None:
            request_starts[request.url] = time.monotonic()

        def on_response(response) -> None:
            start = request_starts.pop(response.url, None)
            evidence.network.append(
                NetworkEvidence(
                    url=response.url,
                    method=response.request.method,
                    status=response.status,
                    resource_type=response.request.resource_type,
                    duration_ms=_ms(start) if start else 0,
                )
            )

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=headless)
                context = browser.new_context()
                context.tracing.start(screenshots=True, snapshots=True, sources=False)
                page = context.new_page()
                page.set_default_timeout(timeout_ms)
                page.on("console", on_console)
                page.on("request", on_request)
                page.on("response", on_response)

                for index, (description, fn) in enumerate(steps, start=1):
                    step_started = time.monotonic()
                    try:
                        fn(page)
                        outcomes.append(
                            StepOutcome(index, description, "passed", "", _ms(step_started), True)
                        )
                    except Exception as exc:  # noqa: BLE001 - per-step isolation
                        outcomes.append(
                            StepOutcome(
                                index, description, "failed", str(exc), _ms(step_started),
                                not is_locator_error(str(exc)),
                            )
                        )
                        status = "failed"
                        error = str(exc)

                    try:
                        screenshot = page.screenshot()
                    except Exception:  # noqa: BLE001 - screenshot is best-effort
                        screenshot = b""
                    evidence.screenshots.append(ScreenshotEvidence(index, description, screenshot))
                    if status == "failed":
                        break

                try:
                    evidence.trace_bytes = context.tracing.stop() or b""
                except Exception:  # noqa: BLE001 - trace is best-effort
                    evidence.trace_bytes = b""
        except Exception as exc:  # noqa: BLE001 - browser-level failure
            status = "failed"
            error = str(exc)
        finally:
            # R005-A005 SUGGESTION-2: always close browser/context, even on
            # browser-level exceptions (e.g. new_page failing).
            if context is not None:
                try:
                    context.close()
                except Exception:  # noqa: BLE001
                    pass
            if browser is not None:
                try:
                    browser.close()
                except Exception:  # noqa: BLE001
                    pass

        return CaseOutcome(
            status=status,
            duration_ms=_ms(run_started),
            steps=outcomes,
            error=error,
            evidence=evidence,
        )


def get_driver() -> ScriptExecutor:
    """Return the real Playwright executor (P013: only real mode)."""
    return PlaywrightDriver()
