"""API test-case generation endpoint (Phase 9)."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import NotFoundError
from app.schemas import ApiTestCaseRead
from app.services.ai.agents.api_test_case_generator import generate_api_test_cases
from app.services.assets import api_test_case_service, project_service

router = APIRouter()


class GenerateApiTestCasesRequest(BaseModel):
    project_id: int
    description: str = Field(..., min_length=1, max_length=20_000)
    requirement_id: int | None = None


@router.post("/generate-api-test-cases")
def generate_api_test_cases_endpoint(
    payload: GenerateApiTestCasesRequest, db: Session = Depends(get_db)
):
    if project_service.get_project(db, payload.project_id) is None:
        raise NotFoundError("Project not found", {"id": payload.project_id})

    result = generate_api_test_cases(db, payload.description)
    created, dedup_warnings = api_test_case_service.create_from_generated(
        db, payload.project_id, payload.requirement_id, result["items"]
    )
    return {
        "status": result["status"],
        "api_test_cases": [ApiTestCaseRead.model_validate(c).model_dump(mode="json") for c in created],
        "warnings": result["warnings"] + dedup_warnings,
    }
