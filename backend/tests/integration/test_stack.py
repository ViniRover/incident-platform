import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from pulse.main import create_app
from pulse.platform.config import get_settings

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("PULSE_INTEGRATION") != "1", reason="Set PULSE_INTEGRATION=1"),
]


def test_real_dependencies_and_migration() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/api/v1/health/ready")
        assert response.status_code == 200
        assert response.json()["checks"] == {"postgres": True, "redis": True}
    engine = create_engine(get_settings().database_url.get_secret_value())
    try:
        with engine.connect() as connection:
            schemas = (
                connection.execute(text("SELECT schema_name FROM information_schema.schemata"))
                .scalars()
                .all()
            )
            assert {"core", "telemetry"}.issubset(schemas)
            assert connection.execute(
                text("SELECT extversion FROM pg_extension WHERE extname = 'timescaledb'")
            ).scalar_one()
            assert (
                connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
                == "0001"
            )
    finally:
        engine.dispose()
