from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, ConfigDict, Field, model_validator

from pulse.features.identity.dependencies import CurrentPrincipal
from pulse.features.monitors.application import MonitorService
from pulse.features.monitors.domain import Monitor, MonitorConfig
from pulse.features.monitors.repository import SqlMonitorRepository
from pulse.platform.database import DatabaseSession

router = APIRouter(prefix="/monitors", tags=["monitors"])


class MonitorInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=100)
    url: str = Field(min_length=1, max_length=2048)
    interval_seconds: int = Field(default=60, ge=30, le=86400)
    timeout_seconds: int = Field(default=10, ge=1, le=30)
    expected_status: int = Field(default=200, ge=100, le=599)
    is_active: bool = True

    @model_validator(mode="after")
    def valid_config(self):
        self.url = self.to_config().url
        return self

    def to_config(self) -> MonitorConfig:
        return MonitorConfig(**self.model_dump(exclude={"config_version"}))


class MonitorUpdate(MonitorInput):
    config_version: int = Field(ge=1)


class MonitorResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    name: str
    url: str
    interval_seconds: int
    timeout_seconds: int
    expected_status: int
    is_active: bool
    config_version: int
    created_at: datetime
    updated_at: datetime


def _response(monitor: Monitor) -> MonitorResponse:
    return MonitorResponse(
        id=monitor.id,
        tenant_id=monitor.tenant_id,
        **monitor.config.__dict__,
        config_version=monitor.config_version,
        created_at=monitor.created_at,
        updated_at=monitor.updated_at,
    )


def get_monitor_service(session: DatabaseSession) -> MonitorService:
    return MonitorService(SqlMonitorRepository(session))


Monitors = Annotated[MonitorService, Depends(get_monitor_service, scope="function")]


@router.get("", response_model=list[MonitorResponse], operation_id="list_monitors")
def list_monitors(
    actor: CurrentPrincipal,
    service: Monitors,
    offset: Annotated[int, Query(ge=0, le=100000)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
):
    return [_response(monitor) for monitor in service.list(actor, offset, limit)]


@router.post("", response_model=MonitorResponse, status_code=201, operation_id="create_monitor")
def create_monitor(
    body: MonitorInput, request: Request, actor: CurrentPrincipal, service: Monitors
):
    monitor = service.create(actor, body.to_config())
    request.app.state.monitor_mutations.labels(operation="create").inc()
    return _response(monitor)


@router.get("/{monitor_id}", response_model=MonitorResponse, operation_id="get_monitor")
def get_monitor(monitor_id: UUID, actor: CurrentPrincipal, service: Monitors):
    return _response(service.get(actor, monitor_id))


@router.put("/{monitor_id}", response_model=MonitorResponse, operation_id="update_monitor")
def update_monitor(
    monitor_id: UUID,
    body: MonitorUpdate,
    request: Request,
    actor: CurrentPrincipal,
    service: Monitors,
):
    monitor = service.update(actor, monitor_id, body.config_version, body.to_config())
    request.app.state.monitor_mutations.labels(operation="update").inc()
    return _response(monitor)


@router.delete("/{monitor_id}", status_code=204, operation_id="delete_monitor")
def delete_monitor(
    monitor_id: UUID,
    request: Request,
    actor: CurrentPrincipal,
    service: Monitors,
    config_version: Annotated[int, Query(ge=1)],
):
    service.delete(actor, monitor_id, config_version)
    request.app.state.monitor_mutations.labels(operation="delete").inc()
