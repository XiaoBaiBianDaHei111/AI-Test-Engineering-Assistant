"""AI output schema + case business validation tests (P3-002)."""

import pytest
from pydantic import ValidationError

from app.schemas.ai import SCHEMA_VERSION
from app.schemas.ai import TestCaseItem as _TestCaseItem


def _case(**overrides):
    data = {
        "title": "正常登录成功",
        "priority": "P1",
        "type": "functional",
        "precondition": "",
        "steps": [
            {"action": "打开登录页", "expected_result": "显示表单"},
            {"action": "输入有效凭据", "expected_result": "接受输入"},
            {"action": "点击登录", "expected_result": "跳转到任务列表"},
        ],
        "test_data": {"username": "u", "password": "p"},
    }
    data.update(overrides)
    return data


def test_valid_case():
    item = _TestCaseItem.model_validate(_case())
    assert item.title == "正常登录成功"
    assert item.priority == "P1"


def test_invalid_priority():
    with pytest.raises(ValidationError):
        _TestCaseItem.model_validate(_case(priority="P9"))


def test_invalid_type():
    with pytest.raises(ValidationError):
        _TestCaseItem.model_validate(_case(type="nope"))


def test_less_than_3_steps():
    with pytest.raises(ValidationError):
        _TestCaseItem.model_validate(
            _case(steps=[{"action": "a", "expected_result": "b"}])
        )


def test_last_step_empty_expected():
    steps = [
        {"action": "a", "expected_result": "b"},
        {"action": "c", "expected_result": "d"},
        {"action": "e", "expected_result": ""},
    ]
    with pytest.raises(ValidationError):
        _TestCaseItem.model_validate(_case(steps=steps))


def test_missing_title():
    with pytest.raises(ValidationError):
        _TestCaseItem.model_validate(_case(title=""))


def test_schema_version_is_2():
    assert SCHEMA_VERSION == 7
