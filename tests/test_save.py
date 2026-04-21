"""Unit tests for mem_save with mocked db/cache."""

from __future__ import annotations

import pytest
from uuid import uuid4

from continuum.models import MemorySource, MemoryType
from continuum.tools import save
from tests.helpers import make_memory_row


class FixedUUID:
    hex = f"{uuid4().hex[:8]}"


@pytest.mark.asyncio
async def test_mem_save_direct_to_db_when_importance_meets_threshold(
    monkeypatch: pytest.MonkeyPatch,
    test_project_id: str,
    test_agent_id: str,
) -> None:
    """Memory with importance >= 7 should be saved directly to PostgreSQL."""
    row = make_memory_row(
        project_id=test_project_id,
        agent_id=test_agent_id,
        type="decision",
        title="Test Decision",
        importance=7,
    )
    calls: dict[str, object] = {}

    async def fake_ensure_project(project_id: str) -> None:
        calls["project_id"] = project_id

    async def fake_fetchrow(query: str, *args: object) -> dict[str, object]:
        calls["query"] = query
        calls["args"] = args
        return row

    async def fail_pending(*args: object, **kwargs: object) -> None:
        raise AssertionError("pending should not be used")

    monkeypatch.setattr(save, "ensure_project", fake_ensure_project)
    monkeypatch.setattr(save.db, "fetchrow", fake_fetchrow)
    monkeypatch.setattr(save.cache, "set_pending_memory", fail_pending)

    result = await save.mem_save(
        project_id=test_project_id,
        type=MemoryType.decision,
        title="Test Decision",
        content="This is a test decision saved directly.",
        agent_id=test_agent_id,
        tags=["test", "decision"],
        importance=7,
        source=MemorySource.agent,
    )

    assert result["status"] == "saved"
    assert result["id"] == row["id"]
    assert calls["project_id"] == test_project_id


@pytest.mark.asyncio
async def test_mem_save_to_redis_pending_when_importance_below_threshold(
    monkeypatch: pytest.MonkeyPatch,
    test_project_id: str,
    test_agent_id: str,
) -> None:
    """Memory with importance < 7 should be stored in Redis as pending."""
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
        project_id=test_project_id,
        type=MemoryType.pattern,
        title="Test Pattern",
        content="This is a test pattern pending confirmation.",
        agent_id=test_agent_id,
        tags=["test", "pattern"],
        importance=3,
        source=MemorySource.user,
    )

    assert result["status"] == "pending"
    assert test_project_id in result["key"]


@pytest.mark.asyncio
async def test_mem_save_auto_creates_project(monkeypatch: pytest.MonkeyPatch, test_project_id: str) -> None:
    """mem_save should auto-create the project."""
    row = make_memory_row(project_id=test_project_id)
    calls: dict[str, object] = {}

    async def fake_ensure_project(project_id: str) -> None:
        calls["ensure_called"] = True
        calls["project_id"] = project_id

    async def fake_fetchrow(query: str, *args: object) -> dict[str, object]:
        return row

    monkeypatch.setattr(save, "ensure_project", fake_ensure_project)
    monkeypatch.setattr(save.db, "fetchrow", fake_fetchrow)

    result = await save.mem_save(
        project_id=test_project_id,
        type=MemoryType.bug,
        title="Auto Project",
        content="This should create the project.",
        importance=8,
    )

    assert result["status"] == "saved"
    assert calls["ensure_called"] is True
    assert calls["project_id"] == test_project_id


@pytest.mark.asyncio
async def test_mem_save_without_agent_id(monkeypatch: pytest.MonkeyPatch, test_project_id: str) -> None:
    """mem_save should work without agent_id (defaults to None)."""
    row = make_memory_row(project_id=test_project_id, agent_id=None)

    async def fake_ensure_project(project_id: str) -> None:
        pass

    async def fake_fetchrow(query: str, *args: object) -> dict[str, object]:
        return row

    monkeypatch.setattr(save, "ensure_project", fake_ensure_project)
    monkeypatch.setattr(save.db, "fetchrow", fake_fetchrow)

    result = await save.mem_save(
        project_id=test_project_id,
        type=MemoryType.context,
        title="Shared Context",
        content="This memory has no specific agent.",
        importance=8,
    )

    assert result["status"] == "saved"
    assert result["memory"]["agent_id"] is None


@pytest.mark.asyncio
async def test_mem_save_without_tags(monkeypatch: pytest.MonkeyPatch, test_project_id: str) -> None:
    """mem_save should work without tags (defaults to empty list)."""
    row = make_memory_row(project_id=test_project_id, tags=[])

    async def fake_ensure_project(project_id: str) -> None:
        pass

    async def fake_fetchrow(query: str, *args: object) -> dict[str, object]:
        return row

    monkeypatch.setattr(save, "ensure_project", fake_ensure_project)
    monkeypatch.setattr(save.db, "fetchrow", fake_fetchrow)

    result = await save.mem_save(
        project_id=test_project_id,
        type=MemoryType.preference,
        title="No Tags",
        content="This memory has no tags.",
        importance=8,
    )

    assert result["status"] == "saved"
    assert result["memory"]["tags"] == []


@pytest.mark.asyncio
async def test_mem_save_importance_boundaries(monkeypatch: pytest.MonkeyPatch, test_project_id: str) -> None:
    """Test importance boundary at threshold (7)."""
    row_pending = make_memory_row(importance=6)
    row_saved = make_memory_row(importance=7)
    stored: dict[str, object] = {}

    async def fake_set_pending_memory(key: str, memory_data: dict[str, object]) -> None:
        stored["pending_key"] = key

    async def fake_ensure_project(project_id: str) -> None:
        pass

    async def fake_fetchrow(query: str, *args: object) -> dict[str, object]:
        importance = args[6] if len(args) > 6 else 7
        return row_saved if importance >= 7 else row_pending

    monkeypatch.setattr(save.cache, "set_pending_memory", fake_set_pending_memory)
    monkeypatch.setattr(save, "ensure_project", fake_ensure_project)
    monkeypatch.setattr(save.db, "fetchrow", fake_fetchrow)

    # Test importance < 7
    result_6 = await save.mem_save(
        project_id=test_project_id,
        type=MemoryType.pattern,
        title="Importance 6",
        content="Below threshold",
        importance=6,
    )
    assert result_6["status"] == "pending"

    # Test importance >= 7
    result_7 = await save.mem_save(
        project_id=test_project_id,
        type=MemoryType.pattern,
        title="Importance 7",
        content="At threshold",
        importance=7,
    )
    assert result_7["status"] == "saved"
