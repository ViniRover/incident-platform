from dataclasses import dataclass
from typing import Protocol


class DependencyProbe(Protocol):
    def check(self) -> bool: ...


@dataclass(frozen=True)
class Readiness:
    checks: dict[str, bool]

    @property
    def ready(self) -> bool:
        return all(self.checks.values())


class CheckReadiness:
    def __init__(self, probes: dict[str, DependencyProbe]) -> None:
        self._probes = probes

    def execute(self) -> Readiness:
        return Readiness({name: probe.check() for name, probe in self._probes.items()})
