from fastapi import Request

from pulse.features.health.application import CheckReadiness
from pulse.features.health.infrastructure import PostgresProbe, RedisProbe
from pulse.platform.resources import Resources


def get_readiness(request: Request) -> CheckReadiness:
    resources: Resources = request.app.state.resources
    return CheckReadiness(
        {"postgres": PostgresProbe(resources.engine), "redis": RedisProbe(resources.redis)}
    )
