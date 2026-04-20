"""mem_list — Memory listing with optional filters.

No full-text search — simple listing ordered by created_at DESC.
If project_id is passed, also includes pending memories from Redis.
"""

from __future__ import annotations

from typing import Any

from continuum.cache import cache
from continuum.database import db
from continuum.models import Memory, MemoryType


async def mem_list(
    project_id: str | None = None,
    agent_id: str | None = None,
    type: MemoryType | None = None,
    limit: int = 20,
    offset: int = 0,
) -> dict[str, Any]:
    """Lists saved memories, ordered by creation date descending.

    If project_id is passed, also includes pending Redis memories
    for that project.
    """
    # ── Build parameterized query ───────────────────────────────
    conditions: list[str] = []
    params: list[Any] = []

    if project_id is not None:
        params.append(project_id)
        conditions.append(f"project_id = ${len(params)}")

    if agent_id is not None:
        params.append(agent_id)
        conditions.append(f"agent_id = ${len(params)}")

    if type is not None:
        params.append(str(type))
        conditions.append(f"type = ${len(params)}")

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    params.append(limit)
    limit_idx = len(params)
    params.append(offset)
    offset_idx = len(params)

    sql = f"""
        SELECT id, project_id, agent_id, type, title, content, tags,
               importance, source, created_at, updated_at
        FROM memories
        {where}
        ORDER BY created_at DESC
        LIMIT ${limit_idx} OFFSET ${offset_idx}
    """

    rows = await db.fetch(sql, *params)
    memories = [
        Memory.model_validate(dict(r)).model_dump(mode="json")
        for r in rows
    ]

    result: dict[str, Any] = {
        "memories": memories,
        "count": len(memories),
    }

    # ── Include Redis pending if project_id is set ──────────────
    if project_id is not None:
        all_pending = await cache.list_pending_memories()
        project_pending = [
            {"key": k, **v}
            for k, v in all_pending.items()
            if v.get("project_id") == project_id
            and (agent_id is None or v.get("agent_id") == agent_id)
        ]
        result["pending"] = project_pending

    return result
