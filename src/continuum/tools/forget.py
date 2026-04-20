"""mem_forget — Deletes a memory (permanent or pending).

If id (uuid) is passed → DELETE from PostgreSQL.
If key (str) is passed → remove from Redis.
Exactly one must be provided.
"""

from __future__ import annotations

from typing import Any

from continuum.cache import cache
from continuum.database import db


async def mem_forget(
    id: str | None = None,
    key: str | None = None,
) -> dict[str, Any]:
    """Forgets a memory — permanently deletes it.

    Pass `id` for PostgreSQL memories (uuid).
    Pass `key` for pending Redis memories.
    """
    if id is not None and key is not None:
        raise ValueError("Pass only 'id' or 'key', not both.")

    # ── PostgreSQL — permanent memory ───────────────────────────
    if id is not None:
        result = await db.execute(
            "DELETE FROM memories WHERE id = $1",
            id,
        )
        if result == "DELETE 0":
            raise ValueError(f"No memory found with id: '{id}'")
        return {
            "status": "forgotten",
            "type": "permanent",
            "id": id,
        }

    # ── Redis — pending memory ──────────────────────────────────
    if key is not None:
        pending = await cache.get_pending_memory(key)
        if pending is None:
            raise ValueError(
                f"No pending memory found with key: '{key}'. "
                "It may have expired (24h TTL)."
            )
        await cache.remove_pending_memory(key)
        return {
            "status": "forgotten",
            "type": "pending",
            "key": key,
        }

    raise ValueError("You must provide either 'id' (uuid) or 'key' (pending key).")
