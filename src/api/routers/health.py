from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel
from starlette.responses import JSONResponse

from src.api.rate_limiter import limiter

CheckStatus = Literal["ok", "unavailable", "degraded"]


class DependencyChecks(BaseModel):
    database: CheckStatus = "unavailable"
    redis: CheckStatus = "unavailable"
    weaviate: CheckStatus = "unavailable"
    celery: CheckStatus = "unavailable"


class HealthResponse(BaseModel):
    status: str
    version: str
    timestamp: str
    checks: DependencyChecks


health_router = APIRouter()


@limiter.exempt  # type: ignore[untyped-decorator]
@health_router.get(
    "/health",
    response_model=HealthResponse,
    summary="Liveness check",
    description=("Returns service health status. Public — no auth required."),
)
async def health(request: Request) -> HealthResponse:
    settings = request.app.state.settings
    checks = DependencyChecks()
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
    checks = DependencyChecks()
    all_ok = all(v == "ok" for v in checks.model_dump().values())
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
