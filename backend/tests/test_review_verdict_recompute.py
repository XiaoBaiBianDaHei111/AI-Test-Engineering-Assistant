"""Verdict recompute tests (M2 core: never trust the LLM's self-reported verdict)."""

from app.services.ai.agents.test_case_reviewer import normalize_review


def _item(**overrides):
    data = {
        "scores": {"completeness": 4, "accuracy": 3, "executability": 4},
        "verdict": "approved",
        "issues": ["i1"],
        "missing_scenarios": ["m1"],
        "suggestions": ["s1"],
    }
    data.update(overrides)
    return data


def test_verdict_needs_work_when_any_dim_le_2():
    result = normalize_review(_item(scores={"completeness": 4, "accuracy": 3, "executability": 1}))
    assert result["verdict"] == "needs_work"


def test_verdict_approved_when_all_dims_ge_3():
    result = normalize_review(_item(scores={"completeness": 5, "accuracy": 4, "executability": 3}))
    assert result["verdict"] == "approved"


def test_llm_self_reported_verdict_overridden():
    # LLM says "approved" but a dimension <= 2 -> system overrides to needs_work.
    result = normalize_review(_item(verdict="approved", scores={"completeness": 2, "accuracy": 4, "executability": 4}))
    assert result["verdict"] == "needs_work"


def test_issues_capped_at_5():
    result = normalize_review(_item(issues=[f"issue-{i}" for i in range(10)]))
    assert len(result["issues"]) == 5


def test_missing_scenarios_preserved():
    result = normalize_review(_item(missing_scenarios=["登录失败无错误提示"]))
    assert result["missing_scenarios"] == ["登录失败无错误提示"]
