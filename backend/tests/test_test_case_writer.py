"""test_case_writer agent tests (P3-004/006; P013 real mode)."""

import pytest

from app.models import TestPoint as _TestPoint
from app.services.ai.agents.test_case_writer import generate_for_test_point


def _load_test_point(db_session, test_point_id: int) -> _TestPoint:
    return db_session.get(_TestPoint, test_point_id)


@pytest.mark.real
def test_writer_valid(require_llm_key, db_session, confirmed_test_point):
    tp = _load_test_point(db_session, confirmed_test_point["id"])
    result = generate_for_test_point(db_session, tp)
    assert result["status"] in ("success", "retry")
    assert len(result["items"]) >= 1
    for item in result["items"]:
        assert len(item["steps"]) >= 3
        assert item["steps"][-1]["expected_result"]
        assert item["priority"] in {"P0", "P1", "P2", "P3"}
        assert "case_id" not in item  # case_id is DB-generated, not AI output
