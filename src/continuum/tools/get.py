"""mem_get — Gets a memory by ID.

Checks Redis (pending) first, then PostgreSQL.
"""

from __future__ import annotations

from typing import Any

from continuum.cache import cache
from continuum.database import db
from continuum.models import Memory

_SELECT_BY_ID = """
    SELECT id, project_id, agent_id, type, title, content, tags,
           importance, source, created_at, updated_at
    FROM memories
    WHERE id = $1
"""


async def mem_get(id: str) -> dict[str, Any] | None:
    """Gets a memory by its UUID.

    Checks Redis (pending keys) first, then PostgreSQL.
    Returns None if not found in either.
    """
    # ── 1. Check Redis (pending) ────────────────────────────────
    pending = await cache.get_pending_memory(id)
    if pending is not None:
        return {
            "status": "pending",
            "key": id,
            **pending,
        }

    # ── 2. Check PostgreSQL ─────────────────────────────────────
    row = await db.fetchrow(_SELECT_BY_ID, id)
    if row is None:
        return None

    memory = Memory.model_validate(dict(row))
    return {
        "status": "saved",
        "memory": memory.model_dump(mode="json"),
    }
