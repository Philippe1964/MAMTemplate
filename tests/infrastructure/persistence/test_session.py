"""Integration tests for async SQLAlchemy session management using in-memory SQLite."""

from sqlalchemy import text

from mamtemplate.infrastructure.persistence.session import (
    create_db_engine,
    create_session_factory,
    get_default_session_factory,
)


async def test_in_memory_sqlite_session() -> None:
    """Verify that an async session can execute a parameterized query against in-memory SQLite."""
    engine = create_db_engine("sqlite+aiosqlite:///:memory:")
    factory = create_session_factory(engine)

    async with factory() as session:
        result = await session.execute(text("SELECT :val"), {"val": 1})
        assert result.scalar_one() == 1

    await engine.dispose()


def test_get_default_session_factory_returns_singleton_pool() -> None:
    """Verify get_default_session_factory reuses the same sessionmaker across requests."""
    get_default_session_factory.cache_clear()
    first = get_default_session_factory()
    second = get_default_session_factory()
    assert first is second
