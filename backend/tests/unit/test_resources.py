from unittest.mock import Mock

from sqlalchemy import event
from sqlalchemy.exc import OperationalError

from pulse.features.health.infrastructure import PostgresProbe
from pulse.platform.config import Settings
from pulse.platform.resources import Resources


def test_postgres_client_receives_transport_deadlines(settings: Settings) -> None:
    resources = Resources.create(settings)
    captured = {}

    @event.listens_for(resources.engine, "do_connect")
    def intercept_connection(dialect, record, args, params):
        captured.update(params)
        # Capture what SQLAlchemy would send to libpq without opening a network socket.
        raise OperationalError(None, None, RuntimeError("connection intercepted"))

    try:
        assert PostgresProbe(resources.engine).check() is False
        assert captured["tcp_user_timeout"] == 3000
        assert captured["keepalives"] == 1
        assert captured["keepalives_idle"] == 5
        assert captured["keepalives_interval"] == 2
        assert captured["keepalives_count"] == 2
        assert captured["connect_timeout"] == 2
        assert captured["options"] == "-c statement_timeout=2000"
    finally:
        resources.close()


def test_postgres_probe_handles_driver_timeout() -> None:
    engine = Mock()
    engine.connect.side_effect = OperationalError(None, None, TimeoutError("TCP timed out"))
    assert PostgresProbe(engine).check() is False
