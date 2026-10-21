from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from pulse.features.monitors.domain import Monitor, MonitorConfig
from pulse.features.monitors.models import MonitorRow
from pulse.platform.errors import Conflict, NotFound


def _monitor(row: MonitorRow) -> Monitor:
    # Hydrate the stored snapshot unchanged; evolving input policies belong to create().
    config = MonitorConfig(
        row.name,
        row.url,
        row.interval_seconds,
        row.timeout_seconds,
        row.expected_status,
        row.is_active,
    )
    return Monitor(
        row.id, row.tenant_id, config, row.config_version, row.created_at, row.updated_at
    )


class SqlMonitorRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def _row(self, tenant_id: UUID, monitor_id: UUID, lock: bool = False) -> MonitorRow | None:
        statement = select(MonitorRow).where(
            MonitorRow.tenant_id == tenant_id, MonitorRow.id == monitor_id
        )
        return self._session.scalar(
            statement.with_for_update().execution_options(populate_existing=True)
            if lock
            else statement
        )

    def list(self, tenant_id: UUID, offset: int, limit: int) -> list[Monitor]:
        rows = self._session.scalars(
            select(MonitorRow)
            .where(MonitorRow.tenant_id == tenant_id)
            .order_by(MonitorRow.created_at.desc(), MonitorRow.id)
            .offset(offset)
            .limit(limit)
        )
        return [_monitor(row) for row in rows]

    def get(self, tenant_id: UUID, monitor_id: UUID) -> Monitor | None:
        row = self._row(tenant_id, monitor_id)
        return _monitor(row) if row else None

    def create(self, tenant_id: UUID, config: MonitorConfig) -> Monitor:
        now = datetime.now(UTC)
        row = MonitorRow(
            id=uuid4(),
            tenant_id=tenant_id,
            **config.__dict__,
            config_version=1,
            next_check_at=now,
            created_at=now,
            updated_at=now,
        )
        self._session.add(row)
        self._session.flush()
        return _monitor(row)

    def update(
        self, tenant_id: UUID, monitor_id: UUID, version: int, config: MonitorConfig
    ) -> Monitor:
        row = self._row(tenant_id, monitor_id, lock=True)
        self._check_version(row, version)
        assert row is not None
        for name, value in config.__dict__.items():
            setattr(row, name, value)
        row.config_version += 1
        row.updated_at = row.next_check_at = datetime.now(UTC)
        self._session.flush()
        return _monitor(row)

    def delete(self, tenant_id: UUID, monitor_id: UUID, version: int) -> None:
        row = self._row(tenant_id, monitor_id, lock=True)
        self._check_version(row, version)
        self._session.delete(row)
        self._session.flush()

    @staticmethod
    def _check_version(row: MonitorRow | None, version: int) -> None:
        if row is None:
            raise NotFound("Monitor not found.")
        if row.config_version != version:
            raise Conflict("Monitor changed. Reload it before saving.")
