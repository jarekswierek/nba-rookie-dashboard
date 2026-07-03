"""Alembic migration environment.

Runs migrations asynchronously using the asyncpg driver — required because
the application uses SQLAlchemy asyncio. The ``run_async_migrations()``
pattern is the standard approach since Alembic 1.9.

The database URL is read from ``Settings`` (pydantic-settings) rather than
``alembic.ini`` so there is one source of truth for connection strings.
"""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

from backend.core.config import get_settings
from backend.data.models import Base

# Alembic Config object — gives access to values in alembic.ini.
config = context.config

# Set up Python logging from the alembic.ini [loggers] section.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Provide the ORM metadata so Alembic can detect schema changes.
target_metadata = Base.metadata


def get_url() -> str:
    """Return the database URL from application settings.

    Using the asyncpg DSN here is correct: Alembic 1.9+ handles asyncio
    connections via ``run_async_migrations()``.
    """
    return get_settings().database_url


def run_migrations_offline() -> None:
    """Emit SQL to stdout without a live database connection.

    Useful for reviewing migration SQL before applying it, or for
    generating SQL scripts for DBA review in production.
    """
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations against a live database using asyncpg.

    Creates a single-use async engine for the migration run. This engine
    is not the application's shared engine — it is discarded after the
    migration completes.
    """
    engine = create_async_engine(get_url())

    async with engine.begin() as connection:
        await connection.run_sync(
            lambda conn: context.configure(
                connection=conn,
                target_metadata=target_metadata,
                compare_type=True,
            )
        )
        await connection.run_sync(lambda conn: context.run_migrations())

    await engine.dispose()


def run_migrations_online() -> None:
    """Entry point for online migrations — delegates to the async runner."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
