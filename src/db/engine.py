"""Async SQLAlchemy engine and session factory."""

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine as _create_engine,
)


def create_async_engine(database_url: str) -> AsyncEngine:
    """Create an async SQLAlchemy engine."""
    return _create_engine(
        database_url,
        echo=False,
        pool_size=5,
        max_overflow=10,
    )


def get_session_factory(
    engine: AsyncEngine,
) -> async_sessionmaker[AsyncSession]:
    """Create a session factory bound to the engine."""
    return async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
