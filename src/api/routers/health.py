import asyncio
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


async def _check_redis(request: Request) -> CheckStatus:
    """Ping Redis — only attempted in celery dispatch mode (INFRA-007)."""
    settings = request.app.state.settings
    if getattr(settings, "task_dispatch", "inprocess") != "celery":
        return "unavailable"
    try:
        import redis.asyncio as aioredis

        client = aioredis.from_url(settings.redis_url)
        try:
            await asyncio.wait_for(client.ping(), timeout=1.0)
        finally:
            await client.aclose()
        return "ok"
    except Exception:
        logger.warning("health_check_redis_failed", exc_info=True)
        return "unavailable"


async def _check_celery(request: Request) -> CheckStatus:
    """Ping a Celery worker — only attempted in celery dispatch mode."""
    settings = request.app.state.settings
    if getattr(settings, "task_dispatch", "inprocess") != "celery":
        return "unavailable"
    try:
        from src.tasks.celery_app import make_celery

        if not hasattr(request.app.state, "_health_celery"):
            request.app.state._health_celery = make_celery(settings)
        celery = request.app.state._health_celery
        # wait_for abandons (does not stop) the inspect thread on timeout;
        # with a down broker and frequent probes, threads linger until
        # kombu's own connection attempts give up. Acceptable at probe
        # rates; revisit with a cached-failure backoff if it shows up.
        replies = await asyncio.wait_for(
            asyncio.to_thread(lambda: celery.control.inspect(timeout=1.0).ping()),
            timeout=2.0,
        )
        return "ok" if replies else "unavailable"
    except Exception:
        logger.warning("health_check_celery_failed", exc_info=True)
        return "unavailable"


async def _run_checks(request: Request) -> DependencyChecks:
    return DependencyChecks(
        database=await _check_database(request),
        redis=await _check_redis(request),
        celery=await _check_celery(request),
    )


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
