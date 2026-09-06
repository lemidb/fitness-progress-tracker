"""
Fitness AI — FastAPI application entry point.

Run with:
    uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

Docs:
    http://localhost:8000/docs   (Swagger UI)
    http://localhost:8000/redoc  (ReDoc)
"""
from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime

import structlog
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.api.v1.routes.auth import router as auth_router
from src.api.v1.routes.workout import router as workout_router
from src.core.config import get_settings
from src.data.database import close_db, init_db

settings = get_settings()

# ── Structured logging ────────────────────────────────────────────────────────

structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.dev.ConsoleRenderer() if settings.app_debug else structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
)
logging.basicConfig(level=logging.DEBUG if settings.app_debug else logging.INFO)
log = structlog.get_logger()


# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("Starting Fitness AI API", env=settings.app_env, version=settings.app_version)
    await init_db()
    # Phase 2+: initialise ML models here
    # Phase 2+: warm up LSTM inference engine
    # Phase 3+: load MediaPipe pose detector
    yield
    await close_db()
    log.info("Shutting down Fitness AI API")


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title=settings.app_title,
    version=settings.app_version,
    description=(
        "State-of-the-art AI fitness platform. "
        "Integrates Google Calendar, Google Sheets, pose estimation, "
        "LSTM performance prediction, and LLM coaching."
    ),
    docs_url="/docs" if settings.app_debug else None,
    redoc_url="/redoc" if settings.app_debug else None,
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.app_debug else ["https://your-frontend.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request timing middleware ─────────────────────────────────────────────────

@app.middleware("http")
async def add_process_time(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000
    response.headers["X-Process-Time-Ms"] = f"{duration_ms:.1f}"
    log.debug("request", method=request.method, path=request.url.path, ms=round(duration_ms, 1))
    return response


# ── Global error handler ──────────────────────────────────────────────────────

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    log.error("Unhandled exception", path=request.url.path, error=str(exc), exc_info=exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error. Check server logs."},
    )


# ── Routers ───────────────────────────────────────────────────────────────────

app.include_router(auth_router, prefix="/api/v1")
app.include_router(workout_router, prefix="/api/v1")


# ── Health & root ─────────────────────────────────────────────────────────────

@app.get("/", tags=["meta"])
async def root():
    return {
        "name": settings.app_title,
        "version": settings.app_version,
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health", tags=["meta"])
async def health():
    return {
        "status": "healthy",
        "version": settings.app_version,
        "environment": settings.app_env,
        "timestamp": datetime.utcnow().isoformat(),
    }
