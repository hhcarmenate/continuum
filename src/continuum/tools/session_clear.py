"""mem_session_clear — Deletes agent-scoped session context from Redis."""

from __future__ import annotations

from typing import Any

from continuum.cache import cache


async def mem_session_clear(agent_id: str, session_id: str) -> dict[str, Any]:
    """Deletes session context for a specific agent and session."""
    await cache.clear_session(agent_id, session_id)
    return {
        "status": "cleared",
        "agent_id": agent_id,
        "session_id": session_id,
    }
