from typing import Protocol
from uuid import UUID

from pulse.features.identity import Principal
from pulse.features.monitors.domain import Monitor, MonitorConfig
from pulse.platform.errors import NotFound


class MonitorRepository(Protocol):
    def list(self, tenant_id: UUID, offset: int, limit: int) -> list[Monitor]: ...
    def get(self, tenant_id: UUID, monitor_id: UUID) -> Monitor | None: ...
    def create(self, tenant_id: UUID, config: MonitorConfig) -> Monitor: ...
    def update(
        self, tenant_id: UUID, monitor_id: UUID, version: int, config: MonitorConfig
    ) -> Monitor: ...
    def delete(self, tenant_id: UUID, monitor_id: UUID, version: int) -> None: ...


class MonitorService:
    def __init__(self, repository: MonitorRepository) -> None:
        self._repository = repository

    def list(self, actor: Principal, offset: int, limit: int) -> list[Monitor]:
        return self._repository.list(actor.tenant_id, offset, limit)

    def get(self, actor: Principal, monitor_id: UUID) -> Monitor:
        monitor = self._repository.get(actor.tenant_id, monitor_id)
        if monitor is None:
            raise NotFound("Monitor not found.")
        return monitor

    def create(self, actor: Principal, config: MonitorConfig) -> Monitor:
        actor.require_monitor_write()
        return self._repository.create(actor.tenant_id, config)

    def update(
        self, actor: Principal, monitor_id: UUID, version: int, config: MonitorConfig
    ) -> Monitor:
        actor.require_monitor_write()
        return self._repository.update(actor.tenant_id, monitor_id, version, config)

    def delete(self, actor: Principal, monitor_id: UUID, version: int) -> None:
        actor.require_monitor_write()
        self._repository.delete(actor.tenant_id, monitor_id, version)
