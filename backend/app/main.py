"""FastAPI application entry point.

Creates the app, registers middleware, routes and exception handlers, and
creates database tables on startup (Phase 1 uses ``create_all``; Alembic can
be introduced later if schema evolution needs explicit migrations).
"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app import models  # noqa: F401  (register models before create_all)
from app.api import api_router
from app.core.config import settings
from app.core.database import Base, engine
from app.core.errors import register_exception_handlers
from app.core.logging import logger
from app.core.schema_check import build_guidance, check_schema
from app.demo_api import router as demo_api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    if not settings.skip_schema_check:
        missing = check_schema(engine)
        if missing:
            raise RuntimeError(build_guidance(missing))
    logger.info("Database tables ensured")
    yield
    from app.services.ai.providers import close_all

    close_all()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)

app.include_router(api_router)
app.include_router(demo_api_router)

# Demo target application (static SPA) for Playwright execution (Phase 5).
_demo_dir = Path(__file__).parent / "demo_app"
app.mount("/demo", StaticFiles(directory=str(_demo_dir), html=True), name="demo")
