"""mem_save — Saves a new memory.

importance >= MIN_IMPORTANCE_AUTO_SAVE → direct INSERT into PostgreSQL.
importance < MIN → Redis pending, awaiting user confirmation.
"""

from __future__ import annotations

import os
import re
import unicodedata
from typing import Any
from uuid import uuid4

from continuum.cache import cache
from continuum.database import db
from continuum.models import Memory, MemorySource, MemoryType

_MIN_IMPORTANCE = int(os.environ.get("MIN_IMPORTANCE_AUTO_SAVE", "7"))

_INSERT_MEMORY = """
    INSERT INTO memories (project_id, agent_id, type, title, content, tags, importance, source)
    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
    RETURNING id, project_id, type, title, content, tags,
              importance, source, agent_id, created_at, updated_at
"""

_ENSURE_PROJECT = """
    INSERT INTO projects (name) VALUES ($1)
    ON CONFLICT (name) DO NOTHING
"""


def _slugify(text: str) -> str:
    """Converts text to an ASCII slug for use as a Redis key."""
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii").lower()
    text = re.sub(r"[^\w\s-]", "", text)
    return re.sub(r"[-\s]+", "-", text).strip("-")[:80]


async def ensure_project(project_id: str) -> None:
    """Creates the project if it doesn't exist — idempotent."""
    await db.execute(_ENSURE_PROJECT, project_id)


async def mem_save(
    project_id: str,
    type: MemoryType,
    title: str,
    content: str,
    agent_id: str | None = None,
    tags: list[str] | None = None,
    importance: int = 5,
    source: MemorySource = MemorySource.agent,
) -> dict[str, Any]:
    """Saves a memory. Auto-creates the project if it doesn't exist.

    If importance >= threshold → direct PostgreSQL save.
    If importance < threshold  → Redis pending (awaits confirmation).
    """
    tags = tags or []

    if importance >= _MIN_IMPORTANCE:
        # ── Save directly to PostgreSQL ─────────────────────────
        await ensure_project(project_id)
        row = await db.fetchrow(
            _INSERT_MEMORY,
            project_id,
            agent_id,
            str(type),
            title,
            content,
            tags,
            importance,
            str(source),
        )
        assert row is not None
        memory = Memory.model_validate(dict(row))
        return {
            "status": "saved",
            "id": str(memory.id),
            "memory": memory.model_dump(mode="json"),
        }

    # ── Pending in Redis — awaiting confirmation ────────────────
    agent_scope = _slugify(agent_id or "shared")
    pending_key = f"{project_id}:{agent_scope}:{_slugify(title)}:{uuid4().hex[:8]}"
    memory_data = {
        "project_id": project_id,
        "agent_id": agent_id,
        "type": str(type),
        "title": title,
        "content": content,
        "tags": tags,
        "importance": importance,
        "source": str(source),
    }
    await cache.set_pending_memory(pending_key, memory_data)
    return {
        "status": "pending",
        "key": pending_key,
        "message": (
            f"Importance {importance} < threshold {_MIN_IMPORTANCE}. "
            "Awaiting user confirmation. "
            "Use mem_promote to confirm or mem_forget to discard."
        ),
    }
