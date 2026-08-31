"""POST /api/ai/extract-test-points — AI test point extraction (Gate 2)."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas import ExtractTestPointsRequest, ExtractTestPointsResponse
from app.services.ai.agents.test_point_extractor import extract_test_points
from app.services.ai.providers import LLMProvider, get_provider

router = APIRouter()


@router.post("/extract-test-points", response_model=ExtractTestPointsResponse)
def extract_test_points_endpoint(
    payload: ExtractTestPointsRequest,
    db: Session = Depends(get_db),
    provider: LLMProvider = Depends(get_provider),
):
    return extract_test_points(db, payload.requirement_id, provider=provider)
