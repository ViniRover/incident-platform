import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from pulse.platform.errors import (
    ApplicationError,
    Conflict,
    DependencyUnavailable,
    Forbidden,
    NotFound,
    RateLimited,
    Unauthenticated,
)
from pulse.platform.http_errors import install_error_handlers


@pytest.mark.parametrize(
    ("base", "status"),
    [
        (Conflict, 409),
        (Forbidden, 403),
        (NotFound, 404),
        (Unauthenticated, 401),
        (RateLimited, 429),
        (DependencyUnavailable, 503),
    ],
)
def test_error_subclasses_inherit_their_http_status(base, status):
    class Specialized(base):
        pass

    class MoreSpecialized(Specialized):
        pass

    app = FastAPI()
    install_error_handlers(app)

    @app.get("/")
    def fail():
        raise MoreSpecialized("Safe public error.")

    with TestClient(app) as client:
        response = client.get("/")
    assert response.status_code == status
    assert response.json() == {"detail": "Safe public error."}
    assert response.headers["cache-control"] == "no-store"
    assert response.headers.get("retry-after") == ("60" if status == 429 else None)


def test_unmapped_application_error_is_sanitized_instead_of_crashing_handler():
    app = FastAPI()
    install_error_handlers(app)

    @app.get("/")
    def fail():
        raise ApplicationError("Internal sensitive details")

    with TestClient(app) as client:
        response = client.get("/")
    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error."}
    assert response.headers["cache-control"] == "no-store"
