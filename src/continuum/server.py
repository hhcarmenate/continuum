"""
MCP server for continuum.

Registers 9 tools and manages PostgreSQL + Redis lifecycle.
Entrypoint: `continuum` (defined in pyproject.toml).
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from typing import Any

from dotenv import load_dotenv
from fastmcp import FastMCP
from fastmcp.server.lifespan import lifespan

from continuum.cache import cache
from continuum.database import db
from continuum.tools import (
    mem_forget,
    mem_get,
    mem_list,
    mem_promote,
    mem_save,
    mem_search,
    mem_session_clear,
    mem_session_get,
    mem_session_set,
)

# ── Lifespan ──────────────────────────────────────────────────────────────────

@lifespan
async def app_lifespan(server: Any) -> AsyncIterator[dict[str, Any]]:
    """Connects PostgreSQL and Redis on startup; disconnects on shutdown."""
    await db.connect()
    await cache.connect()
    try:
        yield {}
    finally:
        await cache.disconnect()
        await db.disconnect()


# ── MCP Server ────────────────────────────────────────────────────────────────

mcp = FastMCP(
    "continuum",
    instructions=(
        "Persistent memory system for AI agents. "
        "Stores decisions, bugs, patterns, context and preferences "
        "across projects using hot Redis cache + cold PostgreSQL storage."
    ),
    lifespan=app_lifespan,
)

# ── Register all 9 tools ─────────────────────────────────────────────────────
# FastMCP uses the function name as tool name and the docstring as LLM description.

mcp.tool(mem_save)
mcp.tool(mem_search)
mcp.tool(mem_get)
mcp.tool(mem_list)
mcp.tool(mem_promote)
mcp.tool(mem_forget)
mcp.tool(mem_session_set)
mcp.tool(mem_session_get)
mcp.tool(mem_session_clear)


# ── Entrypoint ────────────────────────────────────────────────────────────────

def main() -> None:
    """Starts the MCP server. Entrypoint from pyproject.toml [project.scripts]."""
    load_dotenv()

    transport = os.environ.get("MCP_TRANSPORT", "stdio")
    kwargs: dict[str, Any] = {}

    if transport != "stdio":
        kwargs["host"] = os.environ.get("MCP_HOST", "0.0.0.0")
        kwargs["port"] = int(os.environ.get("MCP_PORT", "8000"))

    mcp.run(transport=transport, **kwargs)


if __name__ == "__main__":
    main()
