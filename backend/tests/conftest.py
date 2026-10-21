import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.pool import StaticPool

from pulse.platform.config import Settings
from pulse.platform.database import Base
from tests.support import workspace_client


@pytest.fixture
def settings() -> Settings:
    # Unit/HTTP tests never rely on environment defaults or running local services.
    return Settings(
        database_url="postgresql+psycopg://test:test@127.0.0.1:5432/test",
        redis_url="redis://127.0.0.1:6379/0",
    )


@pytest.fixture
def workspace(settings: Settings):
    engine = create_engine(
        "sqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
        execution_options={"schema_translate_map": {"core": None}},
    )

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, record):
        connection.execute("PRAGMA foreign_keys=ON")

    # Test-only schema. Production and real integration always use Alembic/PostgreSQL.
    Base.metadata.create_all(engine)
    try:
        with workspace_client(engine, settings) as client:
            yield client, engine
    finally:
        engine.dispose()
