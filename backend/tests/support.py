from collections.abc import Iterator
from contextlib import contextmanager

from fastapi.testclient import TestClient
from sqlalchemy import Connection, Engine
from sqlalchemy.orm import Session

from pulse.features.identity.dependencies import get_rate_limiter
from pulse.main import create_app
from pulse.platform.config import Settings
from pulse.platform.database import get_session

PASSWORD = "a long test passphrase 123!"


class AllowAttempts:
    def check(self, key: str, limit: int, seconds: int) -> None:
        pass


@contextmanager
def workspace_client(bind: Engine | Connection, settings: Settings) -> Iterator[TestClient]:
    def session_dependency():
        with Session(
            bind, expire_on_commit=False, join_transaction_mode="create_savepoint"
        ) as session:
            with session.begin():
                yield session

    app = create_app(settings)
    app.dependency_overrides[get_session] = session_dependency
    app.dependency_overrides[get_rate_limiter] = AllowAttempts
    with TestClient(app) as client:
        yield client


def register(client: TestClient, slug: str = "acme", email: str = "owner@example.com") -> dict:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "tenant_name": f"Company {slug}",
            "tenant_slug": slug,
            "name": "Owner",
            "email": email,
            "password": PASSWORD,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def login(client: TestClient, slug: str, email: str) -> dict:
    response = client.post(
        "/api/v1/auth/login",
        json={
            "tenant_slug": slug,
            "email": email,
            "password": PASSWORD,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def headers(session: dict) -> dict:
    return {"X-CSRF-Token": session["csrf_token"], "Origin": "http://localhost:8080"}


def monitor_input(**overrides) -> dict:
    return {
        "name": "Store",
        "url": "https://example.com/",
        "interval_seconds": 60,
        "timeout_seconds": 10,
        "expected_status": 200,
        "is_active": True,
        **overrides,
    }
