import logging

from fastapi import APIRouter, Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.container import get_db
from app.contexts.alerts.api.router import router as alerts_router
from app.contexts.analytics.api.router import collections_router, insights_router
from app.contexts.analytics.api.router import router as analytics_router
from app.contexts.identity.api.router import router as identity_router
from app.contexts.ledger.api.router import router as ledger_router
from app.contexts.simulation.api.router import router as simulation_router
from app.shared.api.errors import register_error_handlers
from app.shared.api.observability import RequestContextMiddleware, configure_logging

_LOG = logging.getLogger("merchant_pay.health")


def create_app() -> FastAPI:
    settings = get_settings()
    settings.validate_runtime()
    configure_logging(logging.DEBUG if not settings.is_production else logging.INFO)

    app = FastAPI(
        title="Merchant Pay API",
        version="1.0.0",
        docs_url="/api/docs",
        redoc_url=None,
        openapi_url="/api/openapi.json",
    )

    # Inner first, CORS last so preflight and CORS headers wrap every response.
    app.add_middleware(RequestContextMiddleware, allowed_origins=settings.cors_origins,
                       https_only=settings.is_production)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "HEAD", "POST", "PATCH", "OPTIONS"],
        allow_headers=["Content-Type", "X-Merchant-Id", "X-Request-ID"],
        expose_headers=["X-Request-ID"],
        max_age=600,
    )
    register_error_handlers(app)

    api = APIRouter(prefix="/api/v1")
    api.include_router(identity_router)
    api.include_router(ledger_router)
    api.include_router(analytics_router)
    api.include_router(collections_router)
    api.include_router(insights_router)
    api.include_router(alerts_router)
    api.include_router(simulation_router)
    app.include_router(api)

    @app.get("/health", tags=["ops"])
    def health() -> dict[str, str]:
        """Liveness: the process is up. Cheap, no dependencies."""
        return {"status": "ok"}

    @app.get("/ready", tags=["ops"])
    def ready(db: Session = Depends(get_db)) -> JSONResponse:
        """Readiness: the process can actually serve traffic (database reachable)."""
        try:
            db.execute(text("SELECT 1"))
        except SQLAlchemyError:
            _LOG.exception("readiness_check_failed")
            return JSONResponse(status_code=503,
                                content={"status": "not_ready", "checks": {"database": "unavailable"}})
        return JSONResponse(status_code=200,
                            content={"status": "ready", "checks": {"database": "ok"}})

    return app


app = create_app()
