"""HTML report generator tests (P8-003, AC-8-01/02/03)."""

from app.services.analysis.report_html import render

STATS = {
    "run_id": 1,
    "run_name": "Run-1",
    "run_status": "failed",
    "overview": {"total": 2, "passed": 1, "failed": 1, "blocked": 0,
                 "skipped": 0, "pass_rate": 0.5, "duration_ms": 1200},
    "priority": {"P0": {"total": 1, "passed": 1, "failed": 0, "pass_rate": 1.0},
                 "P1": {"total": 1, "passed": 0, "failed": 1, "pass_rate": 0.0},
                 "unknown": {"total": 0, "passed": 0, "failed": 0, "pass_rate": 0.0}},
    "failure_categories": {"BROKEN_LOCATOR": 0, "REAL_BUG": 1, "FLAKY": 0, "ENV_ISSUE": 0},
    "cases": [
        {"case_label": "登录", "status": "passed", "duration_ms": 10, "error": "", "priority": "P0",
         "failure_analysis": None, "evidence": {"screenshots": [], "trace": [], "console": [], "network": []}},
        {"case_label": "任务<script>alert(1)</script>", "status": "failed", "duration_ms": 20, "error": "boom",
         "priority": "P1",
         "failure_analysis": {"category": "REAL_BUG", "confidence": 0.9, "reason": "r", "suggested_fix": "f",
                              "decision_source": "llm", "needs_human": False, "status": "classified"},
         "evidence": {"screenshots": [{"id": 9, "step_number": 1, "size_bytes": 100}],
                      "trace": [], "console": [], "network": []}},
    ],
}


def test_self_contained_no_external_resources():
    html = render(STATS)
    assert "cdn" not in html.lower()
    assert "http://" not in html
    assert "https://" not in html
    assert "<script src" not in html


def test_xss_escaped():
    html = render(STATS)
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_screenshot_embedded_when_small():
    html = render(STATS, screenshot_provider=lambda eid: b"\x89PNG-small")
    assert "data:image/png;base64," in html


def test_screenshot_placeholder_when_large_or_missing():
    html = render(STATS, screenshot_provider=lambda eid: None)
    assert "服务模式可查看" in html
    assert "data:image/png;base64," not in html


def test_sections_present():
    html = render(STATS)
    assert "总览" in html
    assert "按优先级通过率" in html
    assert "失败分类分布" in html
    assert "用例明细" in html
    assert "失败分析" in html
    assert "50.0%" in html  # pass rate
    assert "REAL_BUG" in html
