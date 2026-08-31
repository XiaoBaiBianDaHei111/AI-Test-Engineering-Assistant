"""Test-asset routers (Project / Requirement / TestPoint / TestCase / APITestCase)."""

from fastapi import APIRouter

from app.api.assets import (
    api_test_cases,
    projects,
    requirements,
    test_case_reviews,
    test_cases,
    test_points,
)

assets_router = APIRouter(tags=["assets"])
assets_router.include_router(projects.router)
assets_router.include_router(requirements.router)
assets_router.include_router(test_points.router)
assets_router.include_router(test_cases.router)
assets_router.include_router(test_case_reviews.router)
assets_router.include_router(api_test_cases.router)
