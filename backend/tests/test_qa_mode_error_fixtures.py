"""qaMode real-error sample fixtures + capture scripts (P6-011, AC-6-08).

The real Playwright error samples are env-gated (no browser in the sandbox); the
gap is recorded in tests/fixtures/qa_mode_errors/README.md. When samples exist,
each is locked as non-empty Golden data for Phase 7 rule signatures.
"""

from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "qa_mode_errors"


def test_capture_script_exists_and_compiles():
    script = SCRIPTS / "capture_qa_mode_errors.py"
    assert script.exists()
    compile(script.read_text(encoding="utf-8"), str(script), "exec")


def test_cleanup_script_exists_and_compiles():
    script = SCRIPTS / "cleanup_evidence.py"
    assert script.exists()
    compile(script.read_text(encoding="utf-8"), str(script), "exec")


def test_qa_mode_fixtures_locked_if_present():
    samples = sorted(FIXTURES.glob("*.txt"))
    for sample in samples:
        assert sample.read_text(encoding="utf-8").strip(), f"{sample.name} is empty"
