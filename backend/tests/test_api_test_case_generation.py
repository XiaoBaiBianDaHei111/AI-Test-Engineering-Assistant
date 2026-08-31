"""API test-case generation agent tests (P9-004, AC-9-01). Real mode (P013)."""

import pytest

from app.services.ai.agents.api_test_case_generator import generate_api_test_cases


@pytest.mark.real
def test_valid_generation(require_llm_key, db_session):
    result = generate_api_test_cases(
        db_session, "登录接口 POST /api/demo-api/login，成功返回 token"
    )
    items = result["items"]
    assert len(items) >= 1
    for item in items:
        assert item["name"]
        assert item["url"]
        assert item["assertions"]
    statuses = [
        a["expected"]
        for item in items
        for a in item["assertions"]
        if a["type"] == "status"
    ]
    assert statuses
