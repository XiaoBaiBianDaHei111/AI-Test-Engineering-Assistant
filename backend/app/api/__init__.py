"""API layer — aggregate router mounting all /api endpoints."""

from fastapi import APIRouter

from app.api import evidence, failure_analysis, health, reports, runs
from app.api.ai import ai_router
from app.api.assets import assets_router
from app.core.config import settings

api_router = APIRouter(prefix=settings.api_prefix)
api_router.include_router(health.router)
api_router.include_router(ai_router)
api_router.include_router(assets_router)
api_router.include_router(runs.router)
api_router.include_router(evidence.router)
api_router.include_router(failure_analysis.router)
api_router.include_router(reports.router)
