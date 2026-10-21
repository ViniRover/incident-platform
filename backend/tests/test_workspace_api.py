from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from pulse.features.identity.models import SessionRow, TenantRow, UserRow
from pulse.features.identity.security import token_digest
from tests.scenarios import isolation_scenario, lifecycle_scenario, rbac_scenario
from tests.support import PASSWORD, headers, login, monitor_input, register


def test_tenants_cannot_read_update_delete_or_manage_each_other(workspace):
    isolation_scenario(workspace[0])


def test_monitor_lifecycle_and_stale_version_protection(workspace):
    lifecycle_scenario(workspace[0])


def test_all_four_roles_and_privilege_escalation(workspace):
    rbac_scenario(workspace[0])


def test_session_is_hashed_revoked_and_cannot_be_replayed(workspace):
    client, engine = workspace
    owner = register(client)
    token = client.cookies.get("pulse_session")
    assert token and len(token) >= 43
    with Session(engine) as db:
        stored = db.scalar(select(SessionRow))
        assert stored.token_hash == token_digest(token)
        user = db.scalar(select(UserRow))
        assert user.password_hash.startswith("$argon2id$")
        assert PASSWORD not in user.password_hash
    response = client.get("/api/v1/auth/me")
    assert response.json()["tenant_id"] == owner["tenant_id"]
    assert response.headers["cache-control"] == "no-store"
    assert client.post("/api/v1/auth/logout", headers=headers(owner)).status_code == 204
    assert client.get("/api/v1/auth/me").status_code == 401
    client.cookies.set("pulse_session", token)
    assert client.get("/api/v1/auth/me").status_code == 401


def test_cookie_flags_login_rotation_and_expiration(workspace):
    client, engine = workspace
    response = client.post(
        "/api/v1/auth/register",
        json={
            "tenant_name": "Acme",
            "tenant_slug": "acme",
            "name": "Owner",
            "email": "OWNER@example.com",
            "password": PASSWORD,
        },
    )
    assert response.status_code == 201
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=strict" in cookie and "path=/" in cookie
    old = client.cookies.get("pulse_session")
    current = login(client, "acme", "owner@example.com")
    assert client.cookies.get("pulse_session") != old
    with Session(engine) as db:
        assert db.get(SessionRow, token_digest(old)) is None
        db.execute(update(SessionRow).values(expires_at=datetime.now(UTC) - timedelta(seconds=1)))
        db.commit()
    assert client.get("/api/v1/auth/me").status_code == 401
    assert current["email"] == "owner@example.com"


def test_role_change_invalidates_existing_session(workspace):
    client, engine = workspace
    owner = register(client)
    member = client.post(
        "/api/v1/members",
        headers=headers(owner),
        json={
            "name": "Operator",
            "email": "operator@example.com",
            "password": PASSWORD,
            "role": "operator",
        },
    ).json()
    login(client, "acme", "operator@example.com")
    token = client.cookies.get("pulse_session")
    client.cookies.clear()
    owner = login(client, "acme", "owner@example.com")
    assert (
        client.patch(
            f"/api/v1/members/{member['id']}",
            json={"role": "viewer", "is_active": True},
            headers=headers(owner),
        ).status_code
        == 200
    )
    client.cookies.clear()
    client.cookies.set("pulse_session", token)
    assert client.get("/api/v1/auth/me").status_code == 401


def test_csrf_origin_and_tenant_injection(workspace):
    client, _ = workspace
    owner = register(client)
    assert client.post("/api/v1/monitors", json=monitor_input()).status_code == 403
    assert (
        client.post(
            "/api/v1/monitors", json=monitor_input(), headers={"X-CSRF-Token": "wrong"}
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/v1/monitors",
            json=monitor_input(),
            headers={**headers(owner), "Origin": "https://evil.example"},
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/v1/monitors",
            json={**monitor_input(), "tenant_id": str(uuid4())},
            headers=headers(owner),
        ).status_code
        == 422
    )
    client.cookies.clear()
    assert client.get("/api/v1/monitors").status_code == 401
    assert (
        client.post(
            "/api/v1/auth/login",
            json={"tenant_slug": "acme", "email": "owner@example.com", "password": PASSWORD},
            headers={"Origin": "https://evil.example"},
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/v1/auth/login",
            json={"tenant_slug": "acme", "email": "owner@example.com", "password": PASSWORD},
            headers={"Sec-Fetch-Site": "cross-site"},
        ).status_code
        == 403
    )


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost/",
        "http://127.0.0.1",
        "http://169.254.169.254/latest",
        "ftp://example.com",
        "https://user:pass@example.com",
        "https://example.com/#secret",
    ],
)
def test_invalid_targets_are_rejected(workspace, url):
    client, _ = workspace
    owner = register(client)
    assert (
        client.post(
            "/api/v1/monitors", json=monitor_input(url=url), headers=headers(owner)
        ).status_code
        == 422
    )
    assert client.get("/api/v1/monitors").json() == []


def test_conflicts_rollback_and_do_not_reflect_credentials(workspace):
    client, engine = workspace
    owner = register(client)
    duplicate = client.post(
        "/api/v1/auth/register",
        json={
            "tenant_name": "Duplicate",
            "tenant_slug": "acme",
            "name": "Owner",
            "email": "owner2@example.com",
            "password": PASSWORD,
        },
    )
    assert duplicate.status_code == 409
    assert PASSWORD not in duplicate.text and "INSERT" not in duplicate.text
    invalid = client.post(
        "/api/v1/members",
        json={
            "name": "Bad",
            "email": "bad@example.com",
            "password": "tiny-secret",
            "role": "viewer",
        },
        headers=headers(owner),
    )
    assert (
        invalid.status_code == 422
        and '"input"' not in invalid.text
        and "tiny-secret" not in invalid.text
    )
    with Session(engine) as db:
        assert len(db.scalars(select(TenantRow)).all()) == 1
        assert len(db.scalars(select(UserRow)).all()) == 1


def test_wrong_credentials_and_invalid_session_are_generic(workspace):
    client, _ = workspace
    register(client)
    for slug, email, password in [
        ("acme", "owner@example.com", "wrong"),
        ("unknown", "owner@example.com", PASSWORD),
        ("acme", "missing@example.com", PASSWORD),
    ]:
        response = client.post(
            "/api/v1/auth/login", json={"tenant_slug": slug, "email": email, "password": password}
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid tenant, email or password."
    client.cookies.clear()
    client.cookies.set("pulse_session", "x" * 129)
    assert client.get("/api/v1/auth/me").status_code == 401


def test_pagination_and_mutation_metrics(workspace):
    client, _ = workspace
    owner = register(client)
    for name in ("One", "Two", "Three"):
        assert (
            client.post(
                "/api/v1/monitors", json=monitor_input(name=name), headers=headers(owner)
            ).status_code
            == 201
        )
    assert len(client.get("/api/v1/monitors?limit=2").json()) == 2
    assert len(client.get("/api/v1/monitors?offset=2&limit=2").json()) == 1
    assert client.get("/api/v1/monitors?limit=101").status_code == 422
    assert 'pulse_monitor_mutations_total{operation="create"} 3.0' in client.get("/metrics").text


def test_session_cannot_reference_a_user_from_a_different_tenant(workspace):
    client, engine = workspace
    first = register(client, "first")
    second = register(client, "second")
    with Session(engine) as db:
        db.add(
            SessionRow(
                token_hash="x" * 64,
                tenant_id=UUID(second["tenant_id"]),
                user_id=UUID(first["user_id"]),
                expires_at=datetime.now(UTC) + timedelta(hours=1),
            )
        )
        with pytest.raises(IntegrityError):
            db.flush()


def test_registration_rejects_passwords_below_fifteen_characters(workspace):
    client, _ = workspace
    response = client.post(
        "/api/v1/auth/register",
        json={
            "tenant_name": "Acme",
            "tenant_slug": "acme",
            "name": "Owner",
            "email": "owner@example.com",
            "password": "x" * 14,
        },
    )
    assert response.status_code == 422


def test_stored_monitor_remains_readable_and_editable_after_url_policy_changes(
    workspace, monkeypatch
):
    from pulse.features.monitors import domain

    client, _ = workspace
    owner = register(client)
    old_input = monitor_input(url="https://service.corp/")
    created = client.post("/api/v1/monitors", json=old_input, headers=headers(owner))
    assert created.status_code == 201
    monitor = created.json()
    path = f"/api/v1/monitors/{monitor['id']}"
    # Compare persisted responses; SQLite does not preserve timezone offsets on hydration.
    stored = client.get(path).json()
    original_validator = domain.validate_url

    def tightened_policy(url):
        if ".corp" in url:
            raise ValueError("Corporate domains are no longer accepted.")
        return original_validator(url)

    monkeypatch.setattr(domain, "validate_url", tightened_policy)
    listing = client.get("/api/v1/monitors")
    assert listing.status_code == 200
    assert listing.json() == [stored]
    detail = client.get(path)
    assert detail.status_code == 200
    assert detail.json() == stored
    assert (
        client.post("/api/v1/monitors", json=old_input, headers=headers(owner)).status_code == 422
    )
    assert (
        client.put(
            path, json={**old_input, "config_version": 1}, headers=headers(owner)
        ).status_code
        == 422
    )
    repaired = client.put(
        path, json={**monitor_input(), "config_version": 1}, headers=headers(owner)
    )
    assert repaired.status_code == 200
    assert repaired.json()["url"] == "https://example.com/"
    assert repaired.json()["config_version"] == 2
