"""FastAPI application factory.

Middleware order matters and is not arbitrary: security headers are added
outermost so they are present even on error responses, and CORS sits inside them
so a preflight still gets its headers.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.api import analysis as analysis_api
from app.api import auth as auth_api
from app.api import shared as shared_api
from app.config import get_settings
from app.db import init_db
from app.deps import CSP, SECURITY_HEADERS, SlidingWindowLimiter, rate_limit

logger = logging.getLogger("tahqeeq")
settings = get_settings()

STATIC_DIR = Path(__file__).parent / "static"


def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.DEBUG if settings.debug else logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s %(message)s",
    )


@asynccontextmanager
async def lifespan(_app: FastAPI):
    _configure_logging()
    init_db()
    logger.info("Tahqeeq %s starting in %s mode", __version__, settings.environment)
    yield
    logger.info("Tahqeeq shutting down")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Tahqeeq API",
        version=__version__,
        description=(
            "Misinformation detection that shows its evidence. Every score comes with "
            "the signals behind it, the words that triggered them, and how much each "
            "one cost."
        ),
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None,
        openapi_url=None if settings.is_production else "/openapi.json",
        lifespan=lifespan,
    )

    general_limiter = SlidingWindowLimiter(settings.rate_limit_per_minute)
    analyze_limiter = SlidingWindowLimiter(settings.analyze_rate_limit_per_minute)

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        for header, value in SECURITY_HEADERS.items():
            response.headers.setdefault(header, value)
        response.headers.setdefault("Content-Security-Policy", CSP)
        if settings.is_production:
            response.headers.setdefault(
                "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
            )
        return response

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
        max_age=600,
    )

    @app.exception_handler(RequestValidationError)
    async def validation_handler(_request: Request, exc: RequestValidationError):
        """Return a flat, readable message instead of pydantic's nested structure."""
        problems = []
        for error in exc.errors():
            location = ".".join(str(part) for part in error["loc"] if part != "body")
            problems.append(f"{location}: {error['msg']}" if location else error["msg"])
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"detail": "; ".join(problems) or "Invalid request."},
        )

    app.include_router(auth_api.router, dependencies=[Depends(rate_limit(general_limiter))])
    app.include_router(analysis_api.router, dependencies=[Depends(rate_limit(analyze_limiter))])
    app.include_router(shared_api.router)

    @app.get("/api/health", tags=["meta"])
    def health() -> dict:
        return {"status": "ok", "version": __version__, "environment": settings.environment}

    if STATIC_DIR.is_dir():
        app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

        @app.get("/", include_in_schema=False)
        def index() -> FileResponse:
            return FileResponse(STATIC_DIR / "index.html")

        @app.get("/r/{slug}", include_in_schema=False)
        def shared_page(slug: str) -> FileResponse:  # noqa: ARG001
            """The slug is read by the page's own JavaScript from the URL."""
            return FileResponse(STATIC_DIR / "shared.html")

    return app


app = create_app()
