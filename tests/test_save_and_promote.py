from __future__ import annotations

import pytest

from continuum.models import MemorySource, MemoryType
from continuum.tools import promote, save
from tests.helpers import make_memory_row


class FixedUUID:
    hex = "abc12345def67890"


@pytest.mark.asyncio
async def test_mem_save_persists_directly_when_importance_meets_threshold(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict[str, object] = {}
    row = make_memory_row(source="user")

    async def fake_ensure_project(project_id: str) -> None:
        calls["project_id"] = project_id

    async def fake_fetchrow(query: str, *args: object) -> dict[str, object]:
        calls["query"] = query
        calls["args"] = args
        return row

    async def fail_pending(*args: object, **kwargs: object) -> None:
        raise AssertionError("pending storage should not be used")

    monkeypatch.setattr(save, "ensure_project", fake_ensure_project)
    monkeypatch.setattr(save.db, "fetchrow", fake_fetchrow)
    monkeypatch.setattr(save.cache, "set_pending_memory", fail_pending)

    result = await save.mem_save(
        project_id="continuum",
        type=MemoryType.decision,
        title="Store confirmed architectural decision",
        content="Keep Redis for pending memories and PostgreSQL for durable search.",
        agent_id="cursor",
        tags=["architecture", "storage"],
        importance=8,
        source=MemorySource.user,
    )

    assert result["status"] == "saved"
    assert result["id"] == row["id"]
    assert calls["project_id"] == "continuum"
    assert calls["args"] == (
        "continuum",
        "cursor",
        "decision",
        "Store confirmed architectural decision",
        "Keep Redis for pending memories and PostgreSQL for durable search.",
        ["architecture", "storage"],
        8,
        "user",
    )


@pytest.mark.asyncio
async def test_mem_save_stores_pending_memory_below_threshold(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stored: dict[str, object] = {}

    async def fake_set_pending_memory(key: str, memory_data: dict[str, object]) -> None:
        stored["key"] = key
        stored["memory_data"] = memory_data

    async def fail_fetchrow(*args: object, **kwargs: object) -> dict[str, object]:
        raise AssertionError("database should not be used for pending memories")

    monkeypatch.setattr(save.cache, "set_pending_memory", fake_set_pending_memory)
    monkeypatch.setattr(save.db, "fetchrow", fail_fetchrow)
    monkeypatch.setattr(save, "uuid4", lambda: FixedUUID())

    result = await save.mem_save(
        project_id="continuum",
        type=MemoryType.pattern,
        title="Keep cache keys deterministic",
        content="Pending memory keys should remain stable for promotion.",
        agent_id="claude-code",
        tags=["redis"],
        importance=3,
    )

    assert result["status"] == "pending"
    assert result["key"] == "continuum:claude-code:keep-cache-keys-deterministic:abc12345"
    assert stored["key"] == result["key"]
    assert stored["memory_data"] == {
        "project_id": "continuum",
        "agent_id": "claude-code",
        "type": "pattern",
        "title": "Keep cache keys deterministic",
        "content": "Pending memory keys should remain stable for promotion.",
        "tags": ["redis"],
        "importance": 3,
        "source": "agent",
    }


@pytest.mark.asyncio
async def test_mem_promote_moves_pending_memory_to_postgres(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict[str, object] = {}
    pending_memory = {
        "project_id": "continuum",
        "agent_id": "junie",
        "type": "bug",
        "title": "Promotion bug",
        "content": "A promoted memory must be removed from Redis.",
        "tags": ["promotion"],
        "importance": 6,
        "source": "agent",
    }
    row = make_memory_row(
        project_id="continuum",
        agent_id="junie",
        type="bug",
        title="Promotion bug",
        content="A promoted memory must be removed from Redis.",
        tags=["promotion"],
        importance=6,
    )

    async def fake_get_pending_memory(key: str) -> dict[str, object]:
        calls["read_key"] = key
        return pending_memory

    async def fake_ensure_project(project_id: str) -> None:
        calls["project_id"] = project_id

    async def fake_fetchrow(query: str, *args: object) -> dict[str, object]:
        calls["query"] = query
        calls["args"] = args
        return row

    async def fake_remove_pending_memory(key: str) -> None:
        calls["removed_key"] = key

    monkeypatch.setattr(promote.cache, "get_pending_memory", fake_get_pending_memory)
    monkeypatch.setattr(promote, "ensure_project", fake_ensure_project)
    monkeypatch.setattr(promote.db, "fetchrow", fake_fetchrow)
    monkeypatch.setattr(promote.cache, "remove_pending_memory", fake_remove_pending_memory)

    result = await promote.mem_promote("continuum:junie:promotion-bug:deadbeef")

    assert result["status"] == "promoted"
    assert result["id"] == row["id"]
    assert calls["read_key"] == "continuum:junie:promotion-bug:deadbeef"
    assert calls["project_id"] == "continuum"
    assert calls["removed_key"] == "continuum:junie:promotion-bug:deadbeef"
    assert calls["args"] == (
        "continuum",
        "junie",
        "bug",
        "Promotion bug",
        "A promoted memory must be removed from Redis.",
        ["promotion"],
        6,
        "agent",
    )


@pytest.mark.asyncio
async def test_mem_promote_raises_when_pending_memory_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_get_pending_memory(key: str) -> None:
        return None

    monkeypatch.setattr(promote.cache, "get_pending_memory", fake_get_pending_memory)

    with pytest.raises(ValueError, match="No pending memory found"):
        await promote.mem_promote("missing-key")
