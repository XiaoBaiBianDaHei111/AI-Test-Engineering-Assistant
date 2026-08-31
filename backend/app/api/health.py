"""Health check endpoint (used by CI, Docker healthcheck and deployments)."""

from fastapi import APIRouter

router = APIRouter(tags=["system"])


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}
