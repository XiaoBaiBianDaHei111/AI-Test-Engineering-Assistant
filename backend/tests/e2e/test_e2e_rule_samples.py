"""e2e qaMode rule-sample validation (Phase 10, MAJOR-005 backstop).

Validates that real captured error samples (tests/fixtures/qa_mode_errors/*.txt)
are classified by the rule layer. Env-gated: when samples are absent the test
skips (the gap is recorded in the fixtures README; Phase 7 D3 backstop remains).
"""

from pathlib import Path

import pytest

pytestmark = pytest.mark.e2e

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "qa_mode_errors"


def test_captured_selector_change_sample_classified():
    sample = FIXTURES / "selector-change.txt"
    if not sample.exists() or not sample.read_text(encoding="utf-8").strip():
        pytest.skip("selector-change real error sample not captured (env-gated)")
    from app.services.analysis.rule_classifier import rule_classify

    decision = rule_classify(sample.read_text(encoding="utf-8"))
    assert decision is not None
    assert decision.category == "BROKEN_LOCATOR"
    assert decision.source == "rule"
