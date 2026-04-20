"""mem_promote — Promotes a pending memory to permanent storage.

Redis pending → INSERT into PostgreSQL → delete from Redis.
This is the tool the user invokes to confirm what the agent left pending.
"""

from __future__ import annotations

from typing import Any

from continuum.cache import cache
from continuum.database import db
from continuum.models import Memory
from continuum.tools.save import ensure_project

_INSERT_MEMORY = """
    INSERT INTO memories (project_id, agent_id, type, title, content, tags, importance, source)
    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
    RETURNING id, project_id, type, title, content, tags,
              importance, source, agent_id, created_at, updated_at
"""


async def mem_promote(key: str) -> dict[str, Any]:
    """Promotes a pending memory from Redis to permanent PostgreSQL storage.

    1. Reads the pending memory from Redis by key
    2. Creates the project if it doesn't exist
    3. INSERT into PostgreSQL
    4. Deletes from Redis
    """
    # ── 1. Get pending from Redis ───────────────────────────────
    pending = await cache.get_pending_memory(key)
    if pending is None:
        raise ValueError(
            f"No pending memory found with key: '{key}'. "
            "It may have expired (24h TTL) or already been promoted."
        )

    # ── 2. Auto-create project ──────────────────────────────────
    await ensure_project(pending["project_id"])

    # ── 3. INSERT into PostgreSQL ───────────────────────────────
    row = await db.fetchrow(
        _INSERT_MEMORY,
        pending["project_id"],
        pending.get("agent_id"),
        pending["type"],
        pending["title"],
        pending["content"],
        pending.get("tags", []),
        pending["importance"],
        pending.get("source", "agent"),
    )
    assert row is not None

    # ── 4. Clean up from Redis ──────────────────────────────────
    await cache.remove_pending_memory(key)

    memory = Memory.model_validate(dict(row))
    return {
        "status": "promoted",
        "id": str(memory.id),
        "memory": memory.model_dump(mode="json"),
    }
