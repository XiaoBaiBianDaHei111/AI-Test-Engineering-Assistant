"""POST /api/ai/review-test-cases — AI test-case review (M2, synchronous batch)."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import AppError
from app.models import TestCase
from app.schemas import ReviewTestCasesRequest, ReviewTestCasesResponse
from app.services.ai.agents.test_case_reviewer import review_test_case
from app.services.ai.providers import LLMProvider, get_provider
from app.services.assets.test_case_review_service import create_ai_review

router = APIRouter()


@router.post("/review-test-cases", response_model=ReviewTestCasesResponse)
def review_test_cases(
    payload: ReviewTestCasesRequest,
    db: Session = Depends(get_db),
    provider: LLMProvider = Depends(get_provider),
):
    reviewed = 0
    failed: list[dict] = []
    warnings: list[str] = []

    for case_id in payload.test_case_ids:
        test_case = db.get(TestCase, case_id)
        if test_case is None:
            failed.append(
                {"test_case_id": case_id, "reason": "test case not found", "error_code": "NOT_FOUND"}
            )
            continue
        if test_case.status == "archived":
            warnings.append(f"archived 用例已跳过：TC #{case_id}")
            continue

        try:
            review_item = review_test_case(db, test_case, provider)
            create_ai_review(
                db,
                case_id,
                verdict=review_item["verdict"],
                scores=review_item["scores"],
                issues=review_item["issues"],
                missing_scenarios=review_item["missing_scenarios"],
                suggestions=review_item["suggestions"],
            )
            reviewed += 1
        except AppError as exc:
            failed.append(
                {"test_case_id": case_id, "reason": exc.message, "error_code": exc.code}
            )

    return {"reviewed": reviewed, "failed": failed, "warnings": warnings}
