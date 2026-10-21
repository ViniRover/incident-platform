from sqlalchemy.exc import OperationalError

from pulse.features.identity.dependencies import get_rate_limiter
from pulse.platform.database import get_session
from pulse.platform.errors import RateLimited
from tests.support import PASSWORD


def test_auth_http_limit_returns_retry_after(workspace):
    client, _ = workspace

    class Deny:
        def check(self, key, limit, seconds):
            raise RateLimited("Too many attempts.")

    client.app.dependency_overrides[get_rate_limiter] = Deny
    response = client.post(
        "/api/v1/auth/login",
        json={"tenant_slug": "acme", "email": "owner@example.com", "password": PASSWORD},
    )
    assert response.status_code == 429
    assert response.headers["retry-after"] == "60"


def test_database_failure_does_not_expose_driver_details(workspace):
    client, _ = workspace

    def unavailable():
        raise OperationalError("SELECT secret", {"password": "secret"}, RuntimeError("unavailable"))

    client.app.dependency_overrides[get_session] = unavailable
    client.cookies.set("pulse_session", "test-session")
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 503
    assert response.json() == {"detail": "Database temporarily unavailable."}
    assert "secret" not in response.text
