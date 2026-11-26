from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

import app.models_registry  # noqa: F401
from app.api.v1.router import api_v1_router
from app.cli import ensure_superadmin
from app.core.config import get_settings
from app.core.database import AsyncSessionLocal
from app.core.exceptions import register_exception_handlers


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    if (
        settings.AUTO_SEED_SUPERADMIN
        and settings.SUPERADMIN_EMAIL
        and settings.SUPERADMIN_PASSWORD
        and settings.APP_ENV != "test"
    ):
        async with AsyncSessionLocal() as session:
            await ensure_superadmin(
                session,
                email=settings.SUPERADMIN_EMAIL,
                password=settings.SUPERADMIN_PASSWORD,
                name=settings.SUPERADMIN_NAME,
            )
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.APP_NAME,
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Accept"],
    )

    @app.middleware("http")
    async def security_headers_middleware(request: Request, call_next) -> Response:
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        if settings.APP_ENV == "production":
            response.headers["Strict-Transport-Security"] = (
                "max-age=63072000; includeSubDomains; preload"
            )
        return response

    register_exception_handlers(app)
    app.include_router(api_v1_router, prefix=settings.API_V1_PREFIX)

    @app.get("/health", tags=["Health"])
    async def healthcheck() -> dict[str, str]:
        return {"status": "ok", "environment": settings.APP_ENV}

    return app


app = create_app()
