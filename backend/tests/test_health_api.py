from fastapi.testclient import TestClient

from pulse.features.health.application import CheckReadiness
from pulse.features.health.dependencies import get_readiness
from pulse.main import create_app


class FailedProbe:
    def check(self) -> bool:
        return False


def test_liveness_is_independent_of_external_services() -> None:
    with TestClient(create_app()) as client:
        assert client.get("/api/v1/health/live").json() == {"status": "ok", "checks": {}}


def test_readiness_dependency_can_be_replaced_and_returns_503() -> None:
    app = create_app()
    app.dependency_overrides[get_readiness] = lambda: CheckReadiness({"redis": FailedProbe()})
    with TestClient(app) as client:
        response = client.get("/api/v1/health/ready")
        assert response.status_code == 503
        assert response.json() == {"status": "unavailable", "checks": {"redis": False}}
        metrics = client.get("/metrics")
        assert 'pulse_http_requests_total{status="503"} 1.0' in metrics.text


def test_openapi_exposes_versioned_health_contract() -> None:
    schema = create_app().openapi()
    assert "/api/v1/health/ready" in schema["paths"]
    assert "503" in schema["paths"]["/api/v1/health/ready"]["get"]["responses"]
