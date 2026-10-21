from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from time import perf_counter

from fastapi import FastAPI, Request
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Histogram,
    generate_latest,
)
from starlette.responses import Response

from pulse.features.health.router import router as health_router
from pulse.platform.config import Settings, get_settings
from pulse.platform.resources import Resources


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        resources = Resources.create(config)
        app.state.resources = resources
        try:
            yield
        finally:
            resources.close()

    app = FastAPI(title="Pulse API", version="0.1.0", lifespan=lifespan)
    app.include_router(health_router, prefix="/api/v1")
    registry = CollectorRegistry()
    requests = Counter("pulse_http_requests_total", "HTTP responses", ["status"], registry=registry)
    duration = Histogram("pulse_http_duration_seconds", "HTTP duration", registry=registry)

    @app.middleware("http")
    async def metrics(request: Request, call_next):
        started = perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            requests.labels(status="500").inc()
            raise
        else:
            if request.url.path != "/metrics":
                requests.labels(status=str(response.status_code)).inc()
            return response
        finally:
            if request.url.path != "/metrics":
                duration.observe(perf_counter() - started)

    @app.get("/metrics", include_in_schema=False)
    def prometheus_metrics() -> Response:
        return Response(generate_latest(registry), headers={"Content-Type": CONTENT_TYPE_LATEST})

    return app
