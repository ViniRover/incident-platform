"""Add tenant identities, revocable sessions and versioned monitors."""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tenants",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("slug", sa.String(63), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("slug", name="uq_tenants_slug"),
        schema="core",
    )
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("core.tenants.id"), nullable=False),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "email", name="uq_users_tenant_email"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_users_tenant_id_id"),
        sa.CheckConstraint(
            "role IN ('owner', 'admin', 'operator', 'viewer')", name=op.f("ck_users_valid_role")
        ),
        schema="core",
    )
    op.create_index("ix_users_tenant_id", "users", ["tenant_id"], schema="core")
    op.create_table(
        "sessions",
        sa.Column("token_hash", sa.String(64), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["tenant_id", "user_id"], ["core.users.tenant_id", "core.users.id"]
        ),
        schema="core",
    )
    op.create_index("ix_sessions_tenant_id", "sessions", ["tenant_id"], schema="core")
    op.create_index("ix_sessions_expires_at", "sessions", ["expires_at"], schema="core")
    op.create_table(
        "monitors",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("core.tenants.id"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("url", sa.String(2048), nullable=False),
        sa.Column("interval_seconds", sa.Integer(), nullable=False),
        sa.Column("timeout_seconds", sa.Integer(), nullable=False),
        sa.Column("expected_status", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("config_version", sa.Integer(), nullable=False),
        sa.Column("next_check_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "interval_seconds BETWEEN 30 AND 86400", name=op.f("ck_monitors_valid_interval")
        ),
        sa.CheckConstraint(
            "timeout_seconds BETWEEN 1 AND 30 AND timeout_seconds < interval_seconds",
            name=op.f("ck_monitors_valid_timeout"),
        ),
        sa.CheckConstraint(
            "expected_status BETWEEN 100 AND 599", name=op.f("ck_monitors_valid_status")
        ),
        sa.CheckConstraint("config_version >= 1", name=op.f("ck_monitors_valid_version")),
        schema="core",
    )
    op.create_index(
        "ix_monitors_tenant_created_id",
        "monitors",
        ["tenant_id", "created_at", "id"],
        schema="core",
    )
    op.create_index(
        "ix_monitors_due",
        "monitors",
        ["next_check_at"],
        schema="core",
        postgresql_where=sa.text("is_active"),
    )


def downgrade() -> None:
    op.drop_table("monitors", schema="core")
    op.drop_table("sessions", schema="core")
    op.drop_table("users", schema="core")
    op.drop_table("tenants", schema="core")
