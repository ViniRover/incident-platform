import pytest

from pulse.features.health.application import CheckReadiness


class StubProbe:
    def __init__(self, healthy: bool) -> None:
        self._healthy = healthy

    def check(self) -> bool:
        return self._healthy


@pytest.mark.parametrize(
    "postgres,redis", [(True, True), (True, False), (False, True), (False, False)]
)
def test_readiness_requires_every_dependency(postgres: bool, redis: bool) -> None:
    service = CheckReadiness({"postgres": StubProbe(postgres), "redis": StubProbe(redis)})
    result = service.execute()
    assert result.ready is (postgres and redis)
    assert result.checks == {"postgres": postgres, "redis": redis}
