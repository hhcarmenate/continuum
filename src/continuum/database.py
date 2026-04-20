"""
asyncpg pool for PostgreSQL.

ALWAYS use parameterized queries — never string interpolation.
Custom codecs: uuid → str, enums → MemoryType / MemorySource.
"""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator, Sequence
from contextlib import asynccontextmanager
from typing import Any

import asyncpg

from continuum.models import MemorySource, MemoryType


class Database:
    """Async wrapper over an asyncpg connection pool."""

    def __init__(self, dsn: str | None = None, min_size: int = 2, max_size: int = 10) -> None:
        self._dsn = dsn
        self._min_size = min_size
        self._max_size = max_size
        self._pool: asyncpg.Pool | None = None

    # ── Properties ────────────────────────────────────────────

    @property
    def pool(self) -> asyncpg.Pool:
        if self._pool is None:
            raise RuntimeError("Database not connected. Call `await db.connect()` first.")
        return self._pool

    @property
    def is_connected(self) -> bool:
        return self._pool is not None

    # ── Lifecycle ─────────────────────────────────────────────

    async def connect(self, dsn: str | None = None) -> None:
        """Creates the connection pool and registers custom codecs."""
        if self._pool is not None:
            return

        dsn = dsn or self._dsn or self._build_dsn()
        self._pool = await asyncpg.create_pool(
            dsn,
            min_size=self._min_size,
            max_size=self._max_size,
            init=self._init_connection,
        )

    async def disconnect(self) -> None:
        """Closes all connections in the pool."""
        if self._pool is not None:
            await self._pool.close()
            self._pool = None

    # ── Queries ───────────────────────────────────────────────

    async def fetch(self, query: str, *args: Any) -> list[asyncpg.Record]:
        """SELECT returning multiple rows."""
        return await self.pool.fetch(query, *args)

    async def fetchrow(self, query: str, *args: Any) -> asyncpg.Record | None:
        """SELECT returning a single row or None."""
        return await self.pool.fetchrow(query, *args)

    async def fetchval(self, query: str, *args: Any) -> Any:
        """SELECT returning a single scalar value."""
        return await self.pool.fetchval(query, *args)

    async def execute(self, query: str, *args: Any) -> str:
        """INSERT / UPDATE / DELETE — returns status string (e.g., 'INSERT 0 1')."""
        return await self.pool.execute(query, *args)

    async def executemany(self, query: str, args: Sequence[Sequence[Any]]) -> None:
        """Executes the same query with multiple parameter sets."""
        await self.pool.executemany(query, args)

    # ── Transactions ──────────────────────────────────────────

    @asynccontextmanager
    async def acquire(self) -> AsyncGenerator[asyncpg.Connection, None]:
        """Context manager that acquires a connection with an explicit transaction.

        Usage:
            async with db.acquire() as conn:
                await conn.execute("INSERT INTO ...", ...)
                await conn.execute("UPDATE ...", ...)
                # auto-commit on clean exit
                # auto-rollback on exception
        """
        async with self.pool.acquire() as conn, conn.transaction():
            yield conn

    # ── Internals ─────────────────────────────────────────────

    @staticmethod
    def _build_dsn() -> str:
        """Builds DSN from environment variables, or uses DATABASE_URL."""
        if url := os.environ.get("DATABASE_URL"):
            return url
        host = os.environ.get("POSTGRES_HOST", "localhost")
        port = os.environ.get("POSTGRES_PORT", "5432")
        name = os.environ.get("POSTGRES_DB", "memoria")
        user = os.environ.get("POSTGRES_USER", "memoria")
        password = os.environ.get("POSTGRES_PASSWORD", "memoria")
        return f"postgresql://{user}:{password}@{host}:{port}/{name}"

    @staticmethod
    async def _init_connection(conn: asyncpg.Connection) -> None:
        """Registers custom codecs on each new pool connection."""
        # UUID → str (instead of uuid.UUID)
        await conn.set_type_codec(
            "uuid",
            encoder=str,
            decoder=str,
            schema="pg_catalog",
            format="text",
        )
        # PostgreSQL enums → Python StrEnum
        await conn.set_type_codec(
            "memory_type",
            encoder=str,
            decoder=MemoryType,
            schema="public",
            format="text",
        )
        await conn.set_type_codec(
            "memory_source",
            encoder=str,
            decoder=MemorySource,
            schema="public",
            format="text",
        )


# ── Global instance ──────────────────────────────────────────────
db = Database()
