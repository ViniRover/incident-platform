import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from redis import Redis
from sqlalchemy import create_engine, delete, text
from sqlalchemy.orm import Session

from pulse.features.identity.domain import Role
from pulse.features.identity.models import SessionRow, TenantRow, UserRow
from pulse.features.identity.rate_limit import RedisRateLimiter
from pulse.features.identity.repository import SqlIdentityRepository
from pulse.features.identity.security import token_digest
from pulse.features.monitors.domain import MonitorConfig
from pulse.features.monitors.models import MonitorRow
from pulse.features.monitors.repository import SqlMonitorRepository
from pulse.main import create_app
from pulse.platform.config import get_settings
from pulse.platform.errors import Conflict, RateLimited
from tests.support import headers, monitor_input, register

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("PULSE_INTEGRATION") != "1", reason="Set PULSE_INTEGRATION=1"),
]


def test_real_request_transaction_and_logout():
    settings = get_settings()
    engine = create_engine(settings.database_url.get_secret_value())
    tenant_id = None
    try:
        with TestClient(
            create_app(settings), client=("integration-" + uuid4().hex, 50000)
        ) as client:
            owner = register(client, "live-" + uuid4().hex[:12])
            tenant_id = UUID(owner["tenant_id"])
            response = client.post("/api/v1/monitors", headers=headers(owner), json=monitor_input())
            assert response.status_code == 201, response.text
            assert len(client.get("/api/v1/monitors").json()) == 1
            monitor_id = UUID(response.json()["id"])
            barrier = Barrier(2)

            def competing_update():
                try:
                    with Session(engine) as db, db.begin():
                        barrier.wait(timeout=5)
                        SqlMonitorRepository(db).update(
                            tenant_id,
                            monitor_id,
                            1,
                            MonitorConfig.create("Concurrent edit", "https://example.com/"),
                        )
                    return "updated"
                except Conflict:
                    return "conflict"

            with ThreadPoolExecutor(max_workers=2) as executor:
                futures = [executor.submit(competing_update) for _ in range(2)]
                assert sorted(future.result(timeout=10) for future in futures) == [
                    "conflict",
                    "updated",
                ]
            assert client.get(f"/api/v1/monitors/{monitor_id}").json()["config_version"] == 2
            with Session(engine) as cached:
                stale_row = cached.get(MonitorRow, monitor_id)
                assert stale_row.config_version == 2
                with Session(engine) as writer, writer.begin():
                    SqlMonitorRepository(writer).update(
                        tenant_id,
                        monitor_id,
                        2,
                        MonitorConfig.create("New version", "https://example.com/"),
                    )
                with pytest.raises(Conflict):
                    SqlMonitorRepository(cached).update(
                        tenant_id,
                        monitor_id,
                        2,
                        MonitorConfig.create("Stale cached edit", "https://example.com/"),
                    )
            assert client.post("/api/v1/auth/logout", headers=headers(owner)).status_code == 204
            assert client.get("/api/v1/monitors").status_code == 401
    finally:
        if tenant_id:
            with engine.begin() as connection:
                for table in (MonitorRow, SessionRow, UserRow):
                    connection.execute(delete(table).where(table.tenant_id == tenant_id))
                connection.execute(delete(TenantRow).where(TenantRow.id == tenant_id))
        engine.dispose()


def test_real_redis_rate_limit_is_atomic_and_expires():
    redis = Redis.from_url(get_settings().redis_url.get_secret_value())
    key = "integration:" + uuid4().hex
    stored_key = "pulse:auth:" + token_digest(key)
    try:
        limiter = RedisRateLimiter(redis)
        limiter.check(key, 1, 60)
        assert 0 < redis.ttl(stored_key) <= 60
        with pytest.raises(RateLimited):
            limiter.check(key, 1, 60)
    finally:
        redis.delete(stored_key)
        redis.close()


def test_session_resolution_is_read_only_and_does_not_block_revocation():
    from datetime import UTC, datetime, timedelta

    settings = get_settings()
    engine = create_engine(settings.database_url.get_secret_value())
    tenant_id = None
    token = uuid4().hex
    try:
        with Session(engine) as setup, setup.begin():
            repository = SqlIdentityRepository(setup)
            user_id = repository.register(
                "Read-only resolution",
                "readonly-" + uuid4().hex,
                "Owner",
                "readonly@example.com",
                "unused-test-hash",
            )
            tenant_id = setup.get(UserRow, user_id).tenant_id
            repository.add_session(user_id, token, datetime.now(UTC) + timedelta(hours=1))
        with Session(engine) as reader, reader.begin():
            reader.execute(text("SET TRANSACTION READ ONLY"))
            repository = SqlIdentityRepository(reader)
            principal = repository.resolve(token)
            assert principal is not None and principal.role == Role.OWNER
            # A second transaction can update/revoke while the first request remains open.
            with Session(engine) as writer, writer.begin():
                writer.execute(text("SET LOCAL lock_timeout = '500ms'"))
                SqlIdentityRepository(writer).update_member(tenant_id, user_id, Role.OWNER, False)
            assert principal.role == Role.OWNER  # Already-resolved requests retain their snapshot.
            assert repository.resolve(token) is None
            assert reader.get(SessionRow, token_digest(token)) is None
        with TestClient(create_app(settings)) as client:
            client.cookies.set("pulse_session", token)
            assert client.get("/api/v1/auth/me").status_code == 401
    finally:
        if tenant_id:
            with engine.begin() as connection:
                for table in (SessionRow, UserRow):
                    connection.execute(delete(table).where(table.tenant_id == tenant_id))
                connection.execute(delete(TenantRow).where(TenantRow.id == tenant_id))
        engine.dispose()
