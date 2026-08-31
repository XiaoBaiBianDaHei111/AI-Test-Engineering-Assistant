"""AI routers (requirements analysis / test point extraction / case generation / audit)."""

from fastapi import APIRouter

from app.api.ai import (
    api_test_case_generation,
    audit,
    requirements_analysis,
    test_case_generation,
    test_case_review,
    test_points_extraction,
)

ai_router = APIRouter(prefix="/ai", tags=["ai"])
ai_router.include_router(requirements_analysis.router)
ai_router.include_router(test_points_extraction.router)
ai_router.include_router(test_case_generation.router)
ai_router.include_router(test_case_review.router)
ai_router.include_router(api_test_case_generation.router)
ai_router.include_router(audit.router)
