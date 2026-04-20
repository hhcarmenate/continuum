from __future__ import annotations

import uuid
from datetime import UTC, datetime


def make_memory_row(**overrides: object) -> dict[str, object]:
    now = datetime.now(UTC)
    row: dict[str, object] = {
        "id": str(uuid.uuid4()),
        "project_id": "continuum",
        "agent_id": "codex",
        "type": "decision",
        "title": "Store confirmed architectural decision",
        "content": "Keep Redis for pending memories and PostgreSQL for durable search.",
        "tags": ["architecture", "storage"],
        "importance": 8,
        "source": "agent",
        "created_at": now,
        "updated_at": now,
    }
    row.update(overrides)
    return row
