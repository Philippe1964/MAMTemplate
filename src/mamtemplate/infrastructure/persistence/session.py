"""Async SQLAlchemy database engine, Cloud-Native pool tuning, and graceful shutdown."""

from collections.abc import AsyncIterator
from functools import lru_cache
from typing import Any

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from mamtemplate.infrastructure.config.settings import get_settings


def create_db_engine(database_url: str | None = None) -> AsyncEngine:
    """Create an async SQLAlchemy engine with Cloud-Native pool resilience settings.

    Args:
        database_url: Optional override URL; defaults to AppSettings.database_url.

    Returns:
        Configured AsyncEngine instance.
    """
    settings = get_settings()
    url = database_url or settings.database_url
    engine_kwargs: dict[str, Any] = {
        "future": True,
        "pool_pre_ping": True,
    }
    if not url.startswith("sqlite"):
        engine_kwargs.update(
            {
                "pool_size": settings.db_pool_size,
                "max_overflow": settings.db_max_overflow,
                "pool_timeout": settings.db_pool_timeout,
                "pool_recycle": settings.db_pool_recycle,
            }
        )
    return create_async_engine(url, **engine_kwargs)


@lru_cache(maxsize=1)
def get_default_engine() -> AsyncEngine:
    """Return the singleton AsyncEngine shared across the Business replica.

    Returns:
        Cached AsyncEngine instance.
    """
    return create_db_engine()


def create_session_factory(
    engine: AsyncEngine | None = None,
) -> async_sessionmaker[AsyncSession]:
    """Create an async sessionmaker bound to the given engine.

    Args:
        engine: Optional AsyncEngine; uses the shared default engine if omitted.

    Returns:
        An async_sessionmaker producing AsyncSession instances.
    """
    bound_engine = engine or get_default_engine()
    return async_sessionmaker(bound_engine, expire_on_commit=False, class_=AsyncSession)


@lru_cache(maxsize=1)
def get_default_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the singleton async_sessionmaker shared by the application and health check.

    Returns:
        Cached async_sessionmaker bound to the shared application AsyncEngine pool.
    """
    return create_session_factory(get_default_engine())


async def dispose_default_engine() -> None:
    """Gracefully dispose the shared AsyncEngine pool on container SIGTERM / shutdown."""
    if get_default_engine.cache_info().currsize > 0:
        engine = get_default_engine()
        await engine.dispose()
        get_default_session_factory.cache_clear()
        get_default_engine.cache_clear()


async def get_async_session() -> AsyncIterator[AsyncSession]:
    """Provide an AsyncSession for dependency injection from the shared connection pool.

    Yields:
        An active AsyncSession instance.
    """
    factory = get_default_session_factory()
    async with factory() as session:
        yield session
