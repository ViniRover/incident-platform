"""Create shared cluster namespaces and TimescaleDB extension."""

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb")
    op.execute("CREATE SCHEMA core")
    op.execute("CREATE SCHEMA telemetry")


def downgrade() -> None:
    # No CASCADE: refuse to erase future business data accidentally.
    op.execute("DROP SCHEMA telemetry")
    op.execute("DROP SCHEMA core")
    # The shared extension is deliberately preserved.
