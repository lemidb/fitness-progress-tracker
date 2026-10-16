from __future__ import annotations

from collections.abc import AsyncGenerator
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from src.core.config import get_settings

class Base(DeclarativeBase):
    pass


engine: AsyncEngine | None = None
session_factory: async_sessionmaker[AsyncSession] | None = None


def normalize_async_database_url(database_url: str) -> URL:
    """Normalize Supabase's generic PostgreSQL URI for SQLAlchemy asyncpg."""
    url = make_url(database_url)
    if url.drivername in {"postgres", "postgresql"}:
        url = url.set(drivername="postgresql+asyncpg")
    elif url.drivername != "postgresql+asyncpg":
        raise ValueError("DATABASE_URL must use PostgreSQL with the asyncpg driver")

    if url.host and ("supabase" in url.host or "pooler" in url.host):
        query = dict(url.query)
        sslmode = query.pop("sslmode", None)
        query.setdefault("ssl", sslmode or "require")
        url = url.set(query=query)
    return url


def get_engine() -> AsyncEngine:
    global engine, session_factory
    if engine is None:
        database_url = get_settings().database_url
        if not database_url:
            raise RuntimeError("DATABASE_URL must point to the Supabase PostgreSQL database")
        try:
            async_url = normalize_async_database_url(database_url)
        except ValueError as exc:
            raise RuntimeError(str(exc)) from exc
        connect_args = (
            {
                "statement_cache_size": 0,
                "prepared_statement_name_func": lambda: f"__asyncpg_{uuid4()}__",
            }
            if async_url.host and ("supabase" in async_url.host or "pooler" in async_url.host)
            else {}
        )
        engine = create_async_engine(
            async_url,
            echo=get_settings().app_debug,
            pool_pre_ping=True,
            connect_args=connect_args,
        )
        session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    return engine


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    try:
        get_engine()
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    assert session_factory is not None
    async with session_factory() as session:
        yield session


async def init_db() -> None:
    from src.data import models  # noqa: F401

    async with get_engine().connect() as conn:
        await conn.execute(text("SELECT 1"))


async def close_db() -> None:
    global engine, session_factory
    if engine is not None:
        await engine.dispose()
        engine = None
        session_factory = None
