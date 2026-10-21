from fastapi.testclient import TestClient

from tests.support import PASSWORD, headers, login, monitor_input, register


def isolation_scenario(client: TestClient, prefix: str = "") -> None:
    tenant_a = register(client, prefix + "a")
    created = client.post("/api/v1/monitors", json=monitor_input(), headers=headers(tenant_a))
    assert created.status_code == 201, created.text
    monitor = created.json()
    tenant_b = register(client, prefix + "b")
    assert client.get("/api/v1/monitors").json() == []
    assert client.get(f"/api/v1/monitors/{monitor['id']}").status_code == 404
    assert (
        client.put(
            f"/api/v1/monitors/{monitor['id']}",
            json={**monitor_input(), "config_version": 1},
            headers=headers(tenant_b),
        ).status_code
        == 404
    )
    assert (
        client.delete(
            f"/api/v1/monitors/{monitor['id']}?config_version=1", headers=headers(tenant_b)
        ).status_code
        == 404
    )
    assert (
        client.patch(
            f"/api/v1/members/{tenant_a['user_id']}",
            json={"role": "viewer", "is_active": False},
            headers=headers(tenant_b),
        ).status_code
        == 404
    )
    restored = login(client, prefix + "a", "owner@example.com")
    assert restored["tenant_id"] == tenant_a["tenant_id"]
    assert client.get(f"/api/v1/monitors/{monitor['id']}").json()["config_version"] == 1
    assert len(client.get("/api/v1/monitors").json()) == 1


def lifecycle_scenario(client: TestClient, slug: str = "lifecycle") -> None:
    owner = register(client, slug)
    response = client.post("/api/v1/monitors", json=monitor_input(), headers=headers(owner))
    assert response.status_code == 201, response.text
    monitor = response.json()
    changed = client.put(
        f"/api/v1/monitors/{monitor['id']}",
        json={
            **monitor_input(name="New name", is_active=False),
            "config_version": 1,
        },
        headers=headers(owner),
    )
    assert changed.status_code == 200, changed.text
    assert changed.json()["config_version"] == 2
    assert changed.json()["is_active"] is False
    stale = client.put(
        f"/api/v1/monitors/{monitor['id']}",
        json={
            **monitor_input(name="Lost update"),
            "config_version": 1,
        },
        headers=headers(owner),
    )
    assert stale.status_code == 409
    assert (
        client.delete(
            f"/api/v1/monitors/{monitor['id']}?config_version=1", headers=headers(owner)
        ).status_code
        == 409
    )
    assert client.get(f"/api/v1/monitors/{monitor['id']}").json()["name"] == "New name"
    assert (
        client.delete(
            f"/api/v1/monitors/{monitor['id']}?config_version=2", headers=headers(owner)
        ).status_code
        == 204
    )
    assert client.get(f"/api/v1/monitors/{monitor['id']}").status_code == 404
    assert client.get("/api/v1/monitors").json() == []


def rbac_scenario(client: TestClient, slug: str = "roles") -> None:
    owner = register(client, slug)
    member_ids = {}
    for role in ("admin", "operator", "viewer"):
        response = client.post(
            "/api/v1/members",
            json={
                "name": role,
                "email": f"{role}@example.com",
                "password": PASSWORD,
                "role": role,
            },
            headers=headers(owner),
        )
        assert response.status_code == 201, response.text
        member_ids[role] = response.json()["id"]

    viewer = login(client, slug, "viewer@example.com")
    assert client.get("/api/v1/monitors").status_code == 200
    assert client.get("/api/v1/members").status_code == 403
    assert (
        client.post("/api/v1/monitors", json=monitor_input(), headers=headers(viewer)).status_code
        == 403
    )
    operator = login(client, slug, "operator@example.com")
    created = client.post("/api/v1/monitors", json=monitor_input(), headers=headers(operator))
    assert created.status_code == 201, created.text
    assert client.get("/api/v1/members").status_code == 403
    admin = login(client, slug, "admin@example.com")
    assert client.get("/api/v1/members").status_code == 200
    assert (
        client.post(
            "/api/v1/members",
            json={
                "name": "Escalation",
                "email": "admin2@example.com",
                "password": PASSWORD,
                "role": "admin",
            },
            headers=headers(admin),
        ).status_code
        == 403
    )
    assert (
        client.patch(
            f"/api/v1/members/{owner['user_id']}",
            json={"role": "viewer", "is_active": False},
            headers=headers(admin),
        ).status_code
        == 403
    )
    response = client.patch(
        f"/api/v1/members/{member_ids['operator']}",
        json={"role": "viewer", "is_active": False},
        headers=headers(admin),
    )
    assert response.status_code == 200, response.text
    denied = client.post(
        "/api/v1/auth/login",
        json={"tenant_slug": slug, "email": "operator@example.com", "password": PASSWORD},
    )
    assert denied.status_code == 401
