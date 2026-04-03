"""
ResuMax Backend — FastAPI Application Entry Point

Run with:
    uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

Swagger Docs:
    http://localhost:8000/docs
"""

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.logging_config import setup_logging
from app.services.supabase import get_supabase_client

# ── Route Imports ────────────────────────────────────────────────
from app.api.health import router as health_router
from app.api.auth import router as auth_router
from app.api.analysis import router as analysis_router
from app.api.history import router as history_router
from app.api.linkedin import router as linkedin_router

logger = structlog.get_logger(__name__)


# ── Lifespan ─────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup/shutdown lifecycle:
    - On startup: initialize logging, verify Supabase connection
    - On shutdown: cleanup resources
    """
    # ── Startup ──
    setup_logging()
    settings = get_settings()
    logger.info(
        "server_starting",
        app=settings.app_name,
        version=settings.app_version,
        host=settings.host,
        port=settings.port,
    )

    # Verify Supabase connection on boot
    try:
        client = get_supabase_client()
        logger.info("supabase_connected", url=settings.supabase_url[:40] + "...")
    except Exception as e:
        logger.error("supabase_connection_failed", error=str(e))
        raise RuntimeError(f"Failed to connect to Supabase: {e}")

    logger.info("server_ready", docs_url=f"http://{settings.host}:{settings.port}/docs")

    yield  # ── App is running ──

    # ── Shutdown ──
    logger.info("server_shutting_down")


# ── App Factory ──────────────────────────────────────────────────
def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "AI-powered resume optimizer with ATS scoring, "
            "deep analysis, and interactive SHRUTI advisor."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # ── CORS ─────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Register Routers ─────────────────────────────────────
    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(analysis_router)
    app.include_router(history_router)
    app.include_router(linkedin_router)

    # Future routers (uncomment as built):
    # from app.api.shruti import router as shruti_router
    # from app.api.export import router as export_router
    # app.include_router(shruti_router)
    # app.include_router(export_router)

    return app


# ── Create the app instance ──────────────────────────────────────
app = create_app()
