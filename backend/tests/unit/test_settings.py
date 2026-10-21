import pytest
from pydantic import ValidationError

from pulse.main import create_app
from pulse.platform.config import Settings, get_settings


@pytest.fixture(autouse=True)
def clean_settings_environment(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("PULSE_DATABASE_URL", raising=False)
    monkeypatch.delenv("PULSE_REDIS_URL", raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.mark.parametrize("missing", ["PULSE_DATABASE_URL", "PULSE_REDIS_URL"])
def test_application_fails_before_startup_when_configuration_is_missing(
    monkeypatch: pytest.MonkeyPatch, missing: str
) -> None:
    monkeypatch.setenv("PULSE_DATABASE_URL", "postgresql+psycopg://test:test@localhost/test")
    monkeypatch.setenv("PULSE_REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.delenv(missing)
    with pytest.raises(ValidationError) as error:
        create_app()
    assert error.value.errors()[0]["loc"] == (missing.removeprefix("PULSE_").lower(),)


def test_both_connection_urls_are_required() -> None:
    with pytest.raises(ValidationError) as error:
        Settings()
    assert {item["loc"] for item in error.value.errors()} == {("database_url",), ("redis_url",)}


def test_explicit_settings_do_not_require_environment(settings: Settings) -> None:
    assert create_app(settings).title == "Pulse API"
