from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from pulse.platform.database import Base


class MonitorRow(Base):
    __tablename__ = "monitors"
    __table_args__ = (
        CheckConstraint("interval_seconds BETWEEN 30 AND 86400", name="valid_interval"),
        CheckConstraint(
            "timeout_seconds BETWEEN 1 AND 30 AND timeout_seconds < interval_seconds",
            name="valid_timeout",
        ),
        CheckConstraint("expected_status BETWEEN 100 AND 599", name="valid_status"),
        CheckConstraint("config_version >= 1", name="valid_version"),
        Index("ix_monitors_tenant_created_id", "tenant_id", "created_at", "id"),
        Index("ix_monitors_due", "next_check_at", postgresql_where=text("is_active")),
        {"schema": "core"},
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("core.tenants.id"))
    name: Mapped[str] = mapped_column(String(100))
    url: Mapped[str] = mapped_column(String(2048))
    interval_seconds: Mapped[int] = mapped_column(Integer)
    timeout_seconds: Mapped[int] = mapped_column(Integer)
    expected_status: Mapped[int] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean)
    config_version: Mapped[int] = mapped_column(Integer)
    next_check_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
