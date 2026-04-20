"""mem_session_get — Reads agent-scoped session context from Redis."""

from __future__ import annotations

from typing import Any

from continuum.cache import cache


async def mem_session_get(agent_id: str, session_id: str) -> dict[str, Any] | None:
    """Returns session context for a specific agent and session."""
    context = await cache.get_session_context(agent_id, session_id)
    if context is None:
        return None

    return {
        "status": "found",
        "agent_id": agent_id,
        "session_id": session_id,
        "context": context,
    }
