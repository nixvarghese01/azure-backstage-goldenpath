from __future__ import annotations

from alembic import context
from provisioning_orchestrator.config import Settings
from provisioning_orchestrator.db import make_engine
from provisioning_orchestrator.models import Base

settings = Settings.from_env()
target_metadata = Base.metadata


def run_migrations_online() -> None:
    engine = make_engine(settings.database_url, entra_auth=settings.database_entra_auth)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


def run_migrations_offline() -> None:
    context.configure(url=settings.database_url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
