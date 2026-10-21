import pytest

from pulse.platform.config import Settings


@pytest.fixture
def settings() -> Settings:
    # Unit/HTTP tests never rely on environment defaults or running local services.
    return Settings(
        database_url="postgresql+psycopg://test:test@127.0.0.1:5432/test",
        redis_url="redis://127.0.0.1:6379/0",
    )
