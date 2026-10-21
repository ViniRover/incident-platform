from alembic import context
from sqlalchemy import create_engine, pool

from pulse.features.identity import models as identity_models  # noqa: F401
from pulse.features.monitors import models as monitor_models  # noqa: F401
from pulse.platform.config import get_settings
from pulse.platform.database import Base

target_metadata = Base.metadata
database_url = get_settings().database_url.get_secret_value()


def include_name(name, type_, parent_names):
    # Only application schemas belong to this migration history, not Timescale internals.
    return name in {"core", "telemetry"} if type_ == "schema" else True


if context.is_offline_mode():
    context.configure(url=database_url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    engine = create_engine(database_url, poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_schemas=True,
            include_name=include_name,
        )
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()
