"""LIFEPATH API. Start with:  uvicorn app.main:app --reload"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import __version__
from app.api.analyses import router as analyses_router
from app.api.routes import router
from app.core.config import get_settings
from app.db.session import init_db

log = logging.getLogger("lifepath")
NETLIFY_FRONTEND_ORIGIN = "https://lifepath-firstcommit-26.netlify.app"


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()   # creates tables on first start (Alembic migrations come later)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="LIFEPATH API", version=__version__, lifespan=lifespan,
                  description="Document-grounded admission journey API (Phase 2).")
    allowed_origins = list(dict.fromkeys((*settings.cors_origins, NETLIFY_FRONTEND_ORIGIN)))
    app.add_middleware(
        CORSMiddleware, allow_origins=allowed_origins,
        allow_methods=["GET", "POST", "PATCH", "DELETE"], allow_headers=["Content-Type"])
    app.include_router(router)
    app.include_router(analyses_router)

    @app.exception_handler(Exception)
    async def unexpected(_: Request, exc: Exception) -> JSONResponse:
        # Log the error TYPE only: messages can contain document text.
        log.error("Unhandled error: %s", type(exc).__name__)
        return JSONResponse(status_code=500, content={"detail": {
            "code": "internal_error", "message": "Something went wrong on the server."}})

    return app


app = create_app()
