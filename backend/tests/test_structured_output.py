"""Structured-output pipeline tests (P2-004)."""

import pytest

from app.schemas.ai import SCHEMA_VERSION, RequirementItem, TestPointItem as _TestPointItem
from app.services.ai.prompts import load_prompt
from app.services.ai.providers import ChatResult
from app.services.ai.structured import (
    ExtractionError,
    extract_json,
    run_with_repair,
    validate_and_normalize,
)


def test_extract_json_fenced():
    text = '```json\n{"requirements": []}\n```'
    assert extract_json(text) == {"requirements": []}


def test_extract_json_prose_wrapped():
    text = '以下是分析结果：\n{"requirements": [{"title": "登录", "acceptance_criteria": ["a"]}]}\n结束。'
    result = extract_json(text)
    assert result["requirements"][0]["title"] == "登录"


def test_extract_json_invalid_raises():
    with pytest.raises(ExtractionError):
        extract_json("这里没有任何 JSON")


def test_validate_dedupes_by_normalized_title():
    parsed = {
        "requirements": [
            {"title": "登录", "acceptance_criteria": ["a"]},
            {"title": "  登录  ", "acceptance_criteria": ["b"]},
            {"title": "任务", "acceptance_criteria": ["c"]},
        ]
    }
    items, dropped = validate_and_normalize(parsed, RequirementItem, "requirements")
    assert len(items) == 2
    assert any(d["reason"] == "duplicate" for d in dropped)


def test_validate_drops_invalid_item():
    parsed = {
        "requirements": [
            {"title": "ok", "acceptance_criteria": ["a"]},
            {"title": ""},
        ]
    }
    items, dropped = validate_and_normalize(parsed, RequirementItem, "requirements")
    assert len(items) == 1
    assert any(d["reason"] == "invalid_item" for d in dropped)


def test_validate_technique_enum_drops_invalid():
    parsed = {
        "test_points": [
            {"title": "正常登录", "technique": "equivalence"},
            {"title": "非法技术", "technique": "black_magic"},
        ]
    }
    items, dropped = validate_and_normalize(parsed, _TestPointItem, "test_points")
    assert len(items) == 1
    assert any(d["reason"] == "invalid_item" for d in dropped)


def test_run_with_repair_recovers():
    calls = []

    def llm(system, user):
        calls.append(1)
        if len(calls) == 1:
            return ChatResult("```json\n{this is not valid```")
        return ChatResult('{"requirements": [{"title": "登录", "acceptance_criteria": ["a"]}]}')

    outcome = run_with_repair(llm, "sys", "user", RequirementItem, "requirements", max_repairs=2)
    assert outcome.status == "retry"
    assert outcome.attempts == 2
    assert len(outcome.items) == 1


def test_run_with_repair_exhausts_on_invalid():
    def llm(system, user):
        return ChatResult("not json at all")

    outcome = run_with_repair(llm, "sys", "user", RequirementItem, "requirements", max_repairs=2)
    assert outcome.status == "failed"
    assert outcome.error_code == "AI_OUTPUT_INVALID"
    assert outcome.attempts == 3  # 1 initial + 2 repairs


def test_run_with_repair_empty_result():
    def llm(system, user):
        return ChatResult('{"requirements": []}')

    outcome = run_with_repair(llm, "sys", "user", RequirementItem, "requirements", max_repairs=2)
    assert outcome.status == "failed"
    assert outcome.error_code == "AI_EMPTY_RESULT"


def test_schema_version_consistency_across_three_places():
    """Suggestion 3: prompt YAML schema_version == Pydantic SCHEMA_VERSION."""
    assert load_prompt("requirements_analyst")["schema_version"] == SCHEMA_VERSION
    assert load_prompt("test_point_extractor")["schema_version"] == SCHEMA_VERSION
    assert load_prompt("test_case_writer")["schema_version"] == SCHEMA_VERSION
    assert load_prompt("test_case_reviewer")["schema_version"] == SCHEMA_VERSION
    assert load_prompt("script_generator")["schema_version"] == SCHEMA_VERSION
    assert load_prompt("failure_analyzer")["schema_version"] == SCHEMA_VERSION
    assert load_prompt("quality_summarizer")["schema_version"] == SCHEMA_VERSION
    assert load_prompt("api_test_case_generator")["schema_version"] == SCHEMA_VERSION


def test_repair_prompt_includes_original_input():
    """R004 MINOR-002: the repair round still sees the original source context."""
    calls = []

    def llm(system, user):
        calls.append(user)
        if len(calls) == 1:
            return ChatResult("not json at all")
        return ChatResult('{"requirements": [{"title": "登录", "acceptance_criteria": ["a"]}]}')

    outcome = run_with_repair(
        llm, "sys", "原始PRD文本片段", RequirementItem, "requirements", max_repairs=2
    )
    assert outcome.status == "retry"
    assert len(calls) == 2
    assert "原始PRD文本片段" in calls[1]
