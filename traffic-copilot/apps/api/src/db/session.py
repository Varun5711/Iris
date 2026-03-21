"""
Async SQLAlchemy engine and session factory for TrafficCopilot.

Usage (FastAPI dependency injection)
-------------------------------------
    from src.db.session import get_db
    from sqlalchemy.ext.asyncio import AsyncSession
    from fastapi import Depends

    @router.get("/incidents/{id}")
    async def get_incident(id: UUID, db: AsyncSession = Depends(get_db)):
        result = await db.execute(select(Incident).where(Incident.id == id))
        ...

Usage (background workers / scripts)
--------------------------------------
    from src.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        async with session.begin():
            ...

Notes
-----
- The DSN must use the ``postgresql+asyncpg://`` scheme.
- ``pool_pre_ping=True`` keeps connections healthy after PostgreSQL restarts.
- ``echo=False`` in production; set DATABASE_ECHO=true locally for SQL logging.
"""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from src.core.config import settings

# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

_echo_sql: bool = os.getenv("DATABASE_ECHO", "false").lower() in {"1", "true", "yes"}

engine = create_async_engine(
    settings.database_url,
    # Connection pool sizing — tune via DATABASE_POOL_SIZE / DATABASE_MAX_OVERFLOW
    # env vars if the defaults are too large for the deployment target.
    pool_size=int(os.getenv("DATABASE_POOL_SIZE", "10")),
    max_overflow=int(os.getenv("DATABASE_MAX_OVERFLOW", "20")),
    # Emit a lightweight SELECT 1 before returning a connection from the pool
    # so stale connections are detected and replaced automatically.
    pool_pre_ping=True,
    # Connection idle timeout — return connections that have been idle for
    # more than 30 minutes.
    pool_recycle=1800,
    echo=_echo_sql,
    # Enable asyncpg-specific JSON serialisation hooks if needed downstream.
    json_serializer=None,
    json_deserializer=None,
)


# ---------------------------------------------------------------------------
# Session factory
# ---------------------------------------------------------------------------

AsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


# ---------------------------------------------------------------------------
# ORM base
# ---------------------------------------------------------------------------


class Base(DeclarativeBase):
    """
    Declarative base class for all SQLAlchemy ORM models.

    Import this in each model module:

        from src.db.session import Base

        class Incident(Base):
            __tablename__ = "incidents"
            ...
    """


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Async generator that yields a database session and ensures it is closed
    after the request completes (whether normally or via an exception).

    The session is *not* wrapped in an automatic transaction here — endpoints
    that need atomicity should call ``await session.begin()`` or use
    ``async with session.begin():``.

    Yields
    ------
    AsyncSession
        An open async SQLAlchemy session bound to the shared engine.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
