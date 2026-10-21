import os
from uuid import uuid4

import pytest
from sqlalchemy import create_engine

from pulse.platform.config import get_settings
from tests.scenarios import isolation_scenario, lifecycle_scenario, rbac_scenario
from tests.support import workspace_client

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("PULSE_INTEGRATION") != "1", reason="Set PULSE_INTEGRATION=1"),
]


@pytest.mark.parametrize("scenario", [isolation_scenario, lifecycle_scenario, rbac_scenario])
def test_workspace_against_migrated_postgres(scenario):
    settings = get_settings()
    engine = create_engine(settings.database_url.get_secret_value())
    try:
        with engine.connect() as connection:
            transaction = connection.begin()
            try:
                with workspace_client(connection, settings) as client:
                    scenario(client, "test-" + uuid4().hex[:12])
            finally:
                transaction.rollback()
    finally:
        engine.dispose()
