from datetime import UTC, datetime
from typing import Literal

import structlog
from fastapi import APIRouter, Request
from pydantic import BaseModel
from sqlalchemy import text
from starlette.responses import JSONResponse

from src.api.rate_limiter import limiter

logger = structlog.get_logger()

CheckStatus = Literal["ok", "unavailable", "degraded"]


class DependencyChecks(BaseModel):
    database: CheckStatus = "unavailable"
    redis: CheckStatus = "unavailable"
    milvus: CheckStatus = "unavailable"
    celery: CheckStatus = "unavailable"


class HealthResponse(BaseModel):
    status: str
    version: str
    timestamp: str
    checks: DependencyChecks


health_router = APIRouter()


async def _check_database(request: Request) -> CheckStatus:
    """Ping PostgreSQL with a lightweight query."""
    engine = getattr(request.app.state, "db_engine", None)
    if engine is None:
        return "unavailable"
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return "ok"
    except Exception:
        logger.warning("health_check_database_failed", exc_info=True)
        return "unavailable"


async def _run_checks(request: Request) -> DependencyChecks:
    db_status = await _check_database(request)
    return DependencyChecks(database=db_status)


@limiter.exempt  # type: ignore[untyped-decorator]
@health_router.get(
    "/health",
    response_model=HealthResponse,
    summary="Liveness check",
    description=("Returns service health status. Public — no auth required."),
)
async def health(request: Request) -> HealthResponse:
    settings = request.app.state.settings
    checks = await _run_checks(request)
    return HealthResponse(
        status="healthy",
        version=settings.app_version,
        timestamp=datetime.now(UTC).isoformat(),
        checks=checks,
    )


@limiter.exempt  # type: ignore[untyped-decorator]
@health_router.get(
    "/health/ready",
    response_model=HealthResponse,
    responses={503: {"model": HealthResponse}},
    summary="Readiness check",
    description=(
        "Returns 200 when all dependencies are ready."
        " Internal — for k8s readiness probes."
    ),
)
async def readiness(request: Request) -> JSONResponse:
    settings = request.app.state.settings
    checks = await _run_checks(request)
    all_ok = checks.database == "ok"
    response = HealthResponse(
        status="healthy" if all_ok else "unavailable",
        version=settings.app_version,
        timestamp=datetime.now(UTC).isoformat(),
        checks=checks,
    )
    return JSONResponse(
        content=response.model_dump(),
        status_code=200 if all_ok else 503,
    )
