from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.artifacts import router as artifacts_router
from .api.jobs import router as jobs_router
from .api.uploads import router as uploads_router
from .api.youtube import router as youtube_router
from .api.auth import router as auth_router
from .core.config import settings


def _cors_allow_origins() -> list[str]:
    """CORS origins for browser-based clients (e.g. Streamlit).

    Configure with `CORS_ALLOW_ORIGINS` as a comma-separated list.
    Defaults to local dev Streamlit origins.
    """
    env = os.getenv("CORS_ALLOW_ORIGINS", "").strip()
    if env:
        return [o.strip().rstrip("/") for o in env.split(",") if o.strip()]
    return [
        "http://localhost:8501",
        "http://127.0.0.1:8501",
    ]


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name)

    @app.get("/")
    def root() -> dict:
        return {"ok": True, "docs": "/docs", "health": "/healthz"}

    @app.get("/healthz")
    def healthz() -> dict:
        return {"ok": True}

    # Allow the local Streamlit frontend to talk directly to this API from the browser.
    # In production set CORS_ALLOW_ORIGINS to your Streamlit URL(s).
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_allow_origins(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(auth_router)
    app.include_router(uploads_router)
    app.include_router(jobs_router)
    app.include_router(artifacts_router)
    app.include_router(youtube_router)
    return app


app = create_app()


