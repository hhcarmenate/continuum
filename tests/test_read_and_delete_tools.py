from __future__ import annotations

import pytest

from continuum.models import MemoryType
from continuum.tools import forget, get, search
from continuum.tools import list as list_tool
from tests.helpers import make_memory_row


@pytest.mark.asyncio
async def test_mem_get_returns_pending_memory_before_checking_database(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pending = {
        "project_id": "continuum",
        "agent_id": "claude-code",
        "type": "context",
        "title": "Pending context",
        "content": "Need confirmation before persistence.",
        "tags": ["review"],
        "importance": 4,
        "source": "agent",
    }

    async def fake_get_pending_memory(key: str) -> dict[str, object]:
        return pending

    async def fail_fetchrow(*args: object, **kwargs: object) -> None:
        raise AssertionError("database should not be queried when pending exists")

    monkeypatch.setattr(get.cache, "get_pending_memory", fake_get_pending_memory)
    monkeypatch.setattr(get.db, "fetchrow", fail_fetchrow)

    result = await get.mem_get("continuum:claude-code:pending-context:1234abcd")

    assert result == {
        "status": "pending",
        "key": "continuum:claude-code:pending-context:1234abcd",
        **pending,
    }


@pytest.mark.asyncio
async def test_mem_get_returns_saved_memory_from_database_when_pending_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    row = make_memory_row()

    async def fake_get_pending_memory(key: str) -> None:
        return None

    async def fake_fetchrow(query: str, *args: object) -> dict[str, object]:
        return row

    monkeypatch.setattr(get.cache, "get_pending_memory", fake_get_pending_memory)
    monkeypatch.setattr(get.db, "fetchrow", fake_fetchrow)

    result = await get.mem_get(str(row["id"]))

    assert result == {
        "status": "saved",
        "memory": {
            **row,
            "created_at": row["created_at"].isoformat().replace("+00:00", "Z"),
            "updated_at": row["updated_at"].isoformat().replace("+00:00", "Z"),
        },
    }


@pytest.mark.asyncio
async def test_mem_list_includes_project_pending_memories(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict[str, object] = {}
    row = make_memory_row(project_id="continuum", type="pattern")

    async def fake_fetch(query: str, *args: object) -> list[dict[str, object]]:
        calls["query"] = query
        calls["args"] = args
        return [row]

    async def fake_list_pending_memories() -> dict[str, dict[str, object]]:
        return {
            "continuum:cursor:keep-cache-keys-deterministic:abcd1234": {
                "project_id": "continuum",
                "agent_id": "cursor",
                "title": "Keep cache keys deterministic",
            },
            "other:ignore-me": {
                "project_id": "other",
                "title": "Ignore me",
            },
        }

    monkeypatch.setattr(list_tool.db, "fetch", fake_fetch)
    monkeypatch.setattr(list_tool.cache, "list_pending_memories", fake_list_pending_memories)

    result = await list_tool.mem_list(
        project_id="continuum",
        agent_id="cursor",
        type=MemoryType.pattern,
        limit=10,
        offset=5,
    )

    assert result["count"] == 1
    assert result["pending"] == [
        {
            "key": "continuum:cursor:keep-cache-keys-deterministic:abcd1234",
            "project_id": "continuum",
            "agent_id": "cursor",
            "title": "Keep cache keys deterministic",
        }
    ]
    assert calls["args"] == ("continuum", "cursor", "pattern", 10, 5)


@pytest.mark.asyncio
async def test_mem_search_returns_ranked_results_with_filters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict[str, object] = {}
    row = {
        **make_memory_row(project_id="continuum", type="bug", importance=9),
        "rank": 0.42,
    }

    async def fake_fetch(query: str, *args: object) -> list[dict[str, object]]:
        calls["query"] = query
        calls["args"] = args
        return [row]

    monkeypatch.setattr(search.db, "fetch", fake_fetch)

    result = await search.mem_search(
        query="redis bug",
        project_id="continuum",
        agent_id="codex",
        type=MemoryType.bug,
        min_importance=5,
        limit=15,
    )

    assert result["total"] == 1
    assert result["results"][0]["rank"] == 0.42
    assert result["results"][0]["memory"]["project_id"] == "continuum"
    assert calls["args"] == ("redis bug", 5, "continuum", "codex", "bug", 15)


@pytest.mark.asyncio
async def test_mem_forget_deletes_permanent_memory_by_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict[str, object] = {}

    async def fake_execute(query: str, *args: object) -> str:
        calls["query"] = query
        calls["args"] = args
        return "DELETE 1"

    monkeypatch.setattr(forget.db, "execute", fake_execute)

    result = await forget.mem_forget(id="1234")

    assert result == {
        "status": "forgotten",
        "type": "permanent",
        "id": "1234",
    }
    assert calls["args"] == ("1234",)


@pytest.mark.asyncio
async def test_mem_forget_deletes_pending_memory_by_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict[str, object] = {}

    async def fake_get_pending_memory(key: str) -> dict[str, object]:
        calls["read_key"] = key
        return {"project_id": "continuum", "agent_id": "antigravity"}

    async def fake_remove_pending_memory(key: str) -> None:
        calls["removed_key"] = key

    monkeypatch.setattr(forget.cache, "get_pending_memory", fake_get_pending_memory)
    monkeypatch.setattr(forget.cache, "remove_pending_memory", fake_remove_pending_memory)

    result = await forget.mem_forget(key="continuum:antigravity:pending:deadbeef")

    assert result == {
        "status": "forgotten",
        "type": "pending",
        "key": "continuum:antigravity:pending:deadbeef",
    }
    assert calls == {
        "read_key": "continuum:antigravity:pending:deadbeef",
        "removed_key": "continuum:antigravity:pending:deadbeef",
    }


@pytest.mark.asyncio
async def test_mem_forget_requires_exactly_one_identifier() -> None:
    with pytest.raises(ValueError, match="Pass only 'id' or 'key'"):
        await forget.mem_forget(id="1", key="pending-key")
