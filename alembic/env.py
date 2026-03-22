"""Alembic async migration environment."""

import asyncio
import os

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

# Import all models so metadata is populated
from src.db.base import Base
from src.db import tables  # noqa: F401

target_metadata = Base.metadata


def get_url() -> str:
    return os.environ.get(
        "COGNIFY_DATABASE_URL",
        "postgresql+asyncpg://cognify:cognify@localhost:5432/cognify",
    )


def run_migrations_offline() -> None:
    context.configure(
        url=get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:  # type: ignore[no-untyped-def]
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    engine = create_async_engine(get_url())
    async with engine.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await engine.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
