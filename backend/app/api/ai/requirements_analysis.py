"""POST /api/ai/analyze-requirement — AI requirements analysis."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas import AnalyzeRequirementRequest, AnalyzeRequirementResponse
from app.services.ai.agents.requirements_analyst import analyze_requirements
from app.services.ai.providers import LLMProvider, get_provider

router = APIRouter()


@router.post("/analyze-requirement", response_model=AnalyzeRequirementResponse)
def analyze_requirement(
    payload: AnalyzeRequirementRequest,
    db: Session = Depends(get_db),
    provider: LLMProvider = Depends(get_provider),
):
    return analyze_requirements(db, payload.project_id, payload.prd_text, provider=provider)
