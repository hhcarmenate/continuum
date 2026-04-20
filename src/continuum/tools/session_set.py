"""mem_session_set — Stores or merges agent-scoped session context in Redis."""

from __future__ import annotations

from typing import Any

from continuum.cache import cache


async def mem_session_set(
    agent_id: str,
    session_id: str,
    data: dict[str, Any],
    merge: bool = True,
) -> dict[str, Any]:
    """Stores session context for a specific agent and session.

    By default performs a partial merge with any existing context.
    Set `merge=False` to overwrite the session payload completely.
    """
    if merge:
        context = await cache.update_session_context(agent_id, session_id, data)
    else:
        await cache.set_session_context(agent_id, session_id, data)
        context = data

    return {
        "status": "stored",
        "agent_id": agent_id,
        "session_id": session_id,
        "context": context,
    }
