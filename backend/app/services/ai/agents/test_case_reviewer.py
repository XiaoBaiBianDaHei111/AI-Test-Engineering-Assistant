"""Test-case reviewer agent (M2): one test case -> 3-dim review + verdict recompute.

The LLM's self-reported ``verdict`` is never trusted: the system recomputes it
from the scores (any dimension <= 2 -> needs_work, ADOPT ai-nlt _normalize).
"""

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError, NotFoundError
from app.models import Requirement, TestCase, TestCaseReview, TestPoint
from app.schemas.ai import SCHEMA_VERSION, TestCaseReviewItem
from app.services.ai.audit import record_audit
from app.services.ai.prompts import render_prompt
from app.services.ai.providers import LLMProvider, get_provider
from app.services.ai.structured import run_with_repair

AGENT_NAME = "test_case_reviewer"
LIST_KEY = "review"


def normalize_review(item: dict) -> dict:
    """Clamp/recompute the review: verdict is derived from scores (0-5), issues
    are capped at 5. ``scores`` are already 0-5 via the Pydantic schema."""
    scores = item.get("scores", {})
    recomputed = "needs_work" if any(v <= 2 for v in scores.values()) else "approved"
    item["verdict"] = recomputed  # override the LLM's self-reported verdict
    item["issues"] = (item.get("issues") or [])[:5]
    return item


def _context_json(
    test_case: TestCase, requirement: Requirement | None, test_point: TestPoint | None
) -> tuple[str, str, str]:
    test_case_json = json.dumps(
        {
            "title": test_case.title,
            "precondition": test_case.precondition,
            "steps": [
                {"action": s.action, "expected_result": s.expected_result}
                for s in test_case.steps
            ],
            "expected_result": test_case.expected_result,
            "test_data": test_case.test_data,
            "type": test_case.type,
            "priority": test_case.priority,
        },
        ensure_ascii=False,
        indent=2,
    )
    requirement_json = json.dumps(
        {
            "title": requirement.title if requirement else "",
            "description": requirement.description if requirement else "",
            "acceptance_criteria": requirement.acceptance_criteria if requirement else [],
            "risks": requirement.risks if requirement else [],
        },
        ensure_ascii=False,
        indent=2,
    )
    test_point_json = json.dumps(
        {
            "title": test_point.title if test_point else "",
            "technique": test_point.technique if test_point else "",
            "description": test_point.description if test_point else "",
        },
        ensure_ascii=False,
        indent=2,
    )
    return test_case_json, requirement_json, test_point_json


def review_test_case(
    db: Session, test_case: TestCase, provider: LLMProvider | None = None
) -> dict:
    """Review one test case. Returns a normalized review dict (not persisted).

    Raises AppError(422) on failure (empty / invalid / unavailable).
    """
    provider = provider or get_provider()

    requirement = db.get(Requirement, test_case.requirement_id) if test_case.requirement_id else None
    test_point = db.get(TestPoint, test_case.test_point_id) if test_case.test_point_id else None

    system, template, prompt_schema_version = render_prompt(AGENT_NAME)
    test_case_json, requirement_json, test_point_json = _context_json(
        test_case, requirement, test_point
    )
    user = (
        template.replace("{test_case}", test_case_json)
        .replace("{requirement}", requirement_json)
        .replace("{test_point}", test_point_json)
    )

    # RUI-03d: incremental review — attach the previous AI review (if any) so the
    # model only lists new/changed issues and marks repeats as "与上次一致".
    last_review = db.scalar(
        select(TestCaseReview)
        .where(
            TestCaseReview.test_case_id == test_case.id,
            TestCaseReview.reviewer_type == "ai",
        )
        .order_by(TestCaseReview.id.desc())
        .limit(1)
    )
    if last_review is not None:
        previous = json.dumps(
            {
                "verdict": last_review.verdict,
                "scores": last_review.scores,
                "issues": last_review.issues,
                "missing_scenarios": last_review.missing_scenarios,
                "suggestions": last_review.suggestions,
            },
            ensure_ascii=False,
            indent=2,
        )
        user += (
            "\n\n上次 AI 评审结果如下。请仅输出与上次相比新增或变化的问题；"
            "重复问题不再列出，可用'与上次一致'指代：\n" + previous
        )

    outcome = run_with_repair(
        lambda s, u: provider.chat(s, u, json_mode=True, agent=AGENT_NAME),
        system,
        user,
        TestCaseReviewItem,
        LIST_KEY,
        max_repairs=2,
        title_key=None,
    )

    if outcome.status == "failed":
        record_audit(
            db, AGENT_NAME, prompt_schema_version, user,
            f"failed: {outcome.error_code}", outcome.tokens_in, outcome.tokens_out,
            outcome.latency_ms, "failed", failure_excerpt=outcome.raw_output,
        )
        raise AppError(
            422,
            outcome.error_code or "AI_OUTPUT_INVALID",
            "Test case review failed",
            {"test_case_id": test_case.id, "code": outcome.error_code},
        )

    if not outcome.items:
        record_audit(
            db, AGENT_NAME, prompt_schema_version, user,
            "failed: empty review", outcome.tokens_in, outcome.tokens_out,
            outcome.latency_ms, "failed", failure_excerpt=outcome.raw_output,
        )
        raise AppError(
            422, "AI_EMPTY_RESULT", "Test case review returned no result",
            {"test_case_id": test_case.id},
        )

    review_item = normalize_review(outcome.items[0])
    record_audit(
        db, AGENT_NAME, prompt_schema_version, user,
        f"{outcome.status}: verdict={review_item['verdict']}",
        outcome.tokens_in, outcome.tokens_out, outcome.latency_ms, outcome.status,
    )
    return review_item
