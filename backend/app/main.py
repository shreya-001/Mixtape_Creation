from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.artifacts import router as artifacts_router
from .api.jobs import router as jobs_router
from .api.uploads import router as uploads_router
from .api.youtube import router as youtube_router
from .api.auth import router as auth_router
from .core.config import settings


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name)

    # Allow the local Streamlit frontend to talk directly to this API from the browser.
    # This is restricted to localhost origins used during development.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:8501",
            "http://127.0.0.1:8501",
        ],
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


