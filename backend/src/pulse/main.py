from collections.abc import AsyncGenerator
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
from pulse.features.identity.router import router as identity_router
from pulse.features.monitors.router import router as monitors_router
from pulse.platform.config import Settings, get_settings
from pulse.platform.http_errors import ERROR_RESPONSES, install_error_handlers
from pulse.platform.resources import Resources


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
        resources = Resources.create(config)
        app.state.resources = resources
        try:
            yield
        finally:
            resources.close()

    app = FastAPI(title="Pulse API", version="0.2.0", lifespan=lifespan)
    app.state.settings = config
    install_error_handlers(app)
    app.include_router(health_router, prefix="/api/v1")
    app.include_router(identity_router, prefix="/api/v1", responses=ERROR_RESPONSES)
    app.include_router(monitors_router, prefix="/api/v1", responses=ERROR_RESPONSES)
    registry = CollectorRegistry()
    app.state.monitor_mutations = Counter(
        "pulse_monitor_mutations_total",
        "Monitor mutations flushed to the transaction",
        ["operation"],
        registry=registry,
    )
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
            if request.url.path.startswith("/api/v1/"):
                response.headers["Cache-Control"] = "no-store"
            return response
        finally:
            if request.url.path != "/metrics":
                duration.observe(perf_counter() - started)

    @app.get("/metrics", include_in_schema=False)
    def prometheus_metrics() -> Response:
        return Response(generate_latest(registry), headers={"Content-Type": CONTENT_TYPE_LATEST})

    return app
