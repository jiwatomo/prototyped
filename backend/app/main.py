"""FastAPI entrypoint for the scholarship recommendation prototype."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import admin, auth, health, profile, scholarships, submissions
from app.core.config import settings
from app.core.database import init_db
from app.services.ai.factory import AIUnavailableError
from app.services.errors import ServiceError

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logger = logging.getLogger("app")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    if settings.ai_provider == "mock":
        logger.info("AI_PROVIDER=mock — tidak ada request jaringan ke LLM.")
    elif not settings.llm_configured:
        logger.warning(
            "Konfigurasi LLM belum lengkap (AI_API_BASE_URL/AI_API_KEY/AI_MODEL). "
            "MockAIProvider akan dipakai."
        )
    yield


app = FastAPI(
    title="Prototipe Platform Rekomendasi Beasiswa",
    version="0.1.0",
    description=(
        "Prototipe demo. Seluruh data beasiswa adalah DATA DEMO SINTETIS, "
        "bukan informasi beasiswa nyata."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api")
app.include_router(health.router, prefix="/api")
app.include_router(profile.router, prefix="/api")
app.include_router(scholarships.router, prefix="/api")
app.include_router(submissions.router, prefix="/api")
app.include_router(admin.router, prefix="/api")


@app.exception_handler(ServiceError)
async def service_error_handler(_request: Request, exc: ServiceError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message, "code": exc.code},
    )


@app.exception_handler(AIUnavailableError)
async def ai_error_handler(_request: Request, exc: AIUnavailableError) -> JSONResponse:
    return JSONResponse(
        status_code=503,
        content={
            "detail": exc.message,
            "code": "ai_unavailable",
            "reason": exc.reason,
        },
    )


@app.exception_handler(Exception)
async def unhandled_error_handler(_request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error: %s", exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "Terjadi kesalahan pada server.", "code": "internal_error"},
    )


@app.get("/")
def root() -> dict:
    return {
        "service": "scholarship-prototype-backend",
        "docs": "/docs",
        "api": "/api",
        "data_label": "DATA DEMO SINTETIS — BUKAN INFORMASI BEASISWA NYATA",
    }
