"""
Async Redis cache — hot memory with 24h TTL.

Two data domains:
  - session:{agent_id}:{session_id} — active session context (JSON)
  - pending:{key}  — memories with importance < 7 awaiting user confirmation
"""

from __future__ import annotations

import json
import os
from typing import Any

import redis.asyncio as aioredis


class Cache:
    """Async wrapper over redis.asyncio with JSON serialization."""

    _DEFAULT_TTL = 86400  # 24 hours in seconds

    def __init__(self, url: str | None = None, ttl: int | None = None) -> None:
        self._url = url
        self._ttl = ttl or int(os.environ.get("REDIS_TTL_SECONDS", str(self._DEFAULT_TTL)))
        self._redis: aioredis.Redis | None = None  # type: ignore[type-arg]

    # ── Properties ────────────────────────────────────────────

    @property
    def client(self) -> aioredis.Redis:  # type: ignore[type-arg]
        if self._redis is None:
            raise RuntimeError("Cache not connected. Call `await cache.connect()` first.")
        return self._redis

    @property
    def is_connected(self) -> bool:
        return self._redis is not None

    # ── Lifecycle ─────────────────────────────────────────────

    async def connect(self, url: str | None = None) -> None:
        """Connects to Redis and verifies with PING."""
        if self._redis is not None:
            return

        url = url or self._url or self._build_url()
        self._redis = aioredis.from_url(url, decode_responses=True)
        await self._redis.ping()

    async def disconnect(self) -> None:
        """Closes the Redis connection."""
        if self._redis is not None:
            await self._redis.aclose()
            self._redis = None

    # ── Key helpers ───────────────────────────────────────────

    @staticmethod
    def _session_key(agent_id: str, session_id: str) -> str:
        return f"session:{agent_id}:{session_id}"

    @staticmethod
    def _pending_key(key: str) -> str:
        return f"pending:{key}"

    # ── Active session ────────────────────────────────────────
    # Each session stores a JSON dict with the agent's context.

    async def set_session_context(
        self, agent_id: str, session_id: str, data: dict[str, Any]
    ) -> None:
        """Saves the complete session context (overwrites)."""
        await self.client.set(
            self._session_key(agent_id, session_id),
            json.dumps(data, ensure_ascii=False, default=str),
            ex=self._ttl,
        )

    async def get_session_context(
        self, agent_id: str, session_id: str
    ) -> dict[str, Any] | None:
        """Reads a session's context. Returns None if missing or expired."""
        raw = await self.client.get(self._session_key(agent_id, session_id))
        if raw is None:
            return None
        return json.loads(raw)  # type: ignore[no-any-return]

    async def update_session_context(
        self, agent_id: str, session_id: str, partial_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Partial merge: updates only provided keys, preserves the rest."""
        existing = await self.get_session_context(agent_id, session_id) or {}
        existing.update(partial_data)
        await self.set_session_context(agent_id, session_id, existing)
        return existing

    async def clear_session(self, agent_id: str, session_id: str) -> None:
        """Deletes a session's context."""
        await self.client.delete(self._session_key(agent_id, session_id))

    # ── Pending memories ──────────────────────────────────────
    # Memories the agent wants to save but have importance < 7.
    # Await explicit user confirmation before moving to PostgreSQL.

    async def set_pending_memory(self, key: str, memory_data: dict[str, Any]) -> None:
        """Stores a memory pending confirmation."""
        await self.client.set(
            self._pending_key(key),
            json.dumps(memory_data, ensure_ascii=False, default=str),
            ex=self._ttl,
        )

    async def get_pending_memory(self, key: str) -> dict[str, Any] | None:
        """Reads a pending memory by its key."""
        raw = await self.client.get(self._pending_key(key))
        if raw is None:
            return None
        return json.loads(raw)  # type: ignore[no-any-return]

    async def list_pending_memories(self) -> dict[str, dict[str, Any]]:
        """Lists all memories pending confirmation.

        Returns {key_without_prefix: data} for each pending:* in Redis.
        Uses SCAN internally (production-safe, non-blocking).
        """
        result: dict[str, dict[str, Any]] = {}
        async for full_key in self.client.scan_iter(match="pending:*"):
            raw = await self.client.get(full_key)
            if raw is not None:
                clean_key = str(full_key).removeprefix("pending:")
                result[clean_key] = json.loads(raw)
        return result

    async def remove_pending_memory(self, key: str) -> None:
        """Removes a pending memory (confirmed or rejected)."""
        await self.client.delete(self._pending_key(key))

    # ── Internals ─────────────────────────────────────────────

    @staticmethod
    def _build_url() -> str:
        """Builds Redis URL from environment variables."""
        if url := os.environ.get("REDIS_URL"):
            return url
        host = os.environ.get("REDIS_HOST", "localhost")
        port = os.environ.get("REDIS_PORT", "6379")
        db = os.environ.get("REDIS_DB", "0")
        return f"redis://{host}:{port}/{db}"


# ── Global instance ──────────────────────────────────────────────
cache = Cache()
