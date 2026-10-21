from typing import Annotated

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel

from pulse.features.health.application import CheckReadiness
from pulse.features.health.dependencies import get_readiness

router = APIRouter(prefix="/health", tags=["health"])


class HealthResponse(BaseModel):
    status: str
    checks: dict[str, bool]


@router.get("/live", response_model=HealthResponse)
def live() -> HealthResponse:
    return HealthResponse(status="ok", checks={})


@router.get("/ready", response_model=HealthResponse, responses={503: {"model": HealthResponse}})
def ready(
    response: Response, service: Annotated[CheckReadiness, Depends(get_readiness)]
) -> HealthResponse:
    result = service.execute()
    response.status_code = 200 if result.ready else 503
    return HealthResponse(status="ok" if result.ready else "unavailable", checks=result.checks)
