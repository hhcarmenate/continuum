"""
continuum — Persistent memory system for AI agents.

Hot Redis cache + cold PostgreSQL storage, exposed via MCP.
"""

__version__ = "0.1.0"

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

__all__ = [
    "__version__",
    "cache",
    "db",
    "mem_forget",
    "mem_get",
    "mem_list",
    "mem_promote",
    "mem_save",
    "mem_search",
    "mem_session_set",
    "mem_session_get",
    "mem_session_clear",
]
