"""Opt-in deployment test: real nginx/Uvicorn/Redis and two real TCP source IPs."""

import json
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from redis import Redis
from sqlalchemy import create_engine, delete

from pulse.features.identity.models import TenantRow
from pulse.features.identity.security import token_digest
from pulse.platform.config import get_settings

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("PULSE_PROXY_INTEGRATION") != "1", reason="Set PULSE_PROXY_INTEGRATION=1"
    ),
]
ROOT = Path(__file__).resolve().parents[3]


def docker(*arguments: str, source: str | None = None) -> str:
    result = subprocess.run(
        ["docker", *arguments],
        cwd=ROOT,
        input=source,
        capture_output=True,
        text=True,
        timeout=90,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout.strip()


def test_proxy_rate_limits_use_real_client_ips_and_ignore_spoofed_headers():
    frontend_id = docker("compose", "ps", "-q", "frontend")
    frontend = json.loads(docker("inspect", frontend_id))[0]
    networks = frontend["NetworkSettings"]["Networks"]
    assert len(networks) == 1
    network = next(iter(networks))
    proxy_ip = networks[network]["IPAddress"]
    api_id = docker("compose", "ps", "-q", "api")
    api = json.loads(docker("inspect", api_id))[0]
    image = api["Config"]["Image"]
    tenant_id = uuid4()
    slug = "proxy-test-" + tenant_id.hex
    settings = get_settings()
    engine = create_engine(settings.database_url.get_secret_value())
    redis = Redis.from_url(settings.redis_url.get_secret_value())
    clients = []
    client_ips = []
    try:
        # Conflicting registration attempts exercise the limiter without creating users/sessions.
        with engine.begin() as connection:
            connection.execute(
                TenantRow.__table__.insert().values(
                    id=tenant_id,
                    name="Proxy regression test",
                    slug=slug,
                    created_at=datetime.now(UTC),
                )
            )
        for _ in range(2):
            clients.append(
                docker(
                    "run",
                    "--rm",
                    "-d",
                    "--network",
                    network,
                    "--entrypoint",
                    "python",
                    image,
                    "-c",
                    "import time; time.sleep(300)",
                )
            )
        client_ips = [
            json.loads(docker("inspect", client))[0]["NetworkSettings"]["Networks"][network][
                "IPAddress"
            ]
            for client in clients
        ]
        assert client_ips[0] != client_ips[1]
        # Exercise HTTP, not TestClient or a forged ASGI scope.
        common = f"""
import json
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen
slug = {slug!r}
started = time.monotonic()
def post(path, index, host="frontend:8080", forwarded="198.51.100.77"):
    body = {{"tenant_slug": slug, "email": f"attempt-{{index}}@example.com",
            "password": "invalid-password-for-test"}}
    if path == "register":
        body.update(tenant_name="Proxy regression", name="Test")
    request = Request(f"http://{{host}}/api/v1/auth/{{path}}",
        data=json.dumps(body).encode(), headers={{"Content-Type": "application/json",
        "X-Forwarded-For": forwarded, "X-Real-IP": forwarded,
        "X-Forwarded-Proto": "https"}})
    try:
        with urlopen(request, timeout=10) as response:
            return response.status
    except HTTPError as error:
        return error.code
"""
        first = (
            common
            + f"""
for index in range(60):
    status = post("login", index)
    assert status == 401, (index, status)
assert post("login", 60) == 429
# Changing or chaining forged headers cannot escape this client's exhausted bucket.
assert post("login", 61, forwarded="203.0.113.8, {proxy_ip}") == 429
for index in range(5):
    assert post("register", index) == 409
assert post("register", 5, forwarded="203.0.113.10") == 429
assert time.monotonic() - started < 60, "Test crossed the rate-limit window"
"""
        )
        docker("exec", "-i", clients[0], "python", "-", source=first)
        second = (
            common
            + f"""
# Same forged header as client one, but a distinct real source IP: separate buckets.
assert post("login", 63) == 401
assert post("register", 6) == 409
# A direct untrusted peer cannot impersonate the exhausted first client either.
assert post("login", 64, host="api:8000", forwarded={client_ips[0]!r}) == 401
"""
        )
        docker("exec", "-i", clients[1], "python", "-", source=second)
        direct = (
            common
            + """
# Direct API connections must not trust headers from any peer except nginx.
assert post("login", 62, host="api:8000", forwarded="203.0.113.9") == 429
"""
        )
        docker("exec", "-i", clients[0], "python", "-", source=direct)
    finally:
        for client in clients:
            docker("rm", "-f", client)
        keys = [f"{kind}:{ip}" for ip in client_ips for kind in ("login-ip", "register")]
        keys += [f"login-account:{slug}:attempt-{index}@example.com" for index in range(65)]
        redis.delete(*("pulse:auth:" + token_digest(key) for key in keys))
        redis.close()
        with engine.begin() as connection:
            connection.execute(delete(TenantRow).where(TenantRow.id == tenant_id))
        engine.dispose()
