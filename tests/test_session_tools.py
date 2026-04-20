from __future__ import annotations

import pytest

from continuum.tools import session_clear, session_get, session_set


@pytest.mark.asyncio
async def test_mem_session_set_merges_existing_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_update_session_context(
        agent_id: str,
        session_id: str,
        partial_data: dict[str, object],
    ) -> dict[str, object]:
        assert agent_id == "codex"
        assert session_id == "workspace-1"
        assert partial_data == {"branch": "main"}
        return {"repo": "continuum", "branch": "main"}

    monkeypatch.setattr(
        session_set.cache,
        "update_session_context",
        fake_update_session_context,
    )

    result = await session_set.mem_session_set(
        agent_id="codex",
        session_id="workspace-1",
        data={"branch": "main"},
    )

    assert result == {
        "status": "stored",
        "agent_id": "codex",
        "session_id": "workspace-1",
        "context": {"repo": "continuum", "branch": "main"},
    }


@pytest.mark.asyncio
async def test_mem_session_set_can_overwrite_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict[str, object] = {}

    async def fake_set_session_context(
        agent_id: str,
        session_id: str,
        data: dict[str, object],
    ) -> None:
        calls["agent_id"] = agent_id
        calls["session_id"] = session_id
        calls["data"] = data

    monkeypatch.setattr(session_set.cache, "set_session_context", fake_set_session_context)

    result = await session_set.mem_session_set(
        agent_id="cursor",
        session_id="workspace-2",
        data={"repo": "continuum"},
        merge=False,
    )

    assert result == {
        "status": "stored",
        "agent_id": "cursor",
        "session_id": "workspace-2",
        "context": {"repo": "continuum"},
    }
    assert calls == {
        "agent_id": "cursor",
        "session_id": "workspace-2",
        "data": {"repo": "continuum"},
    }


@pytest.mark.asyncio
async def test_mem_session_get_returns_agent_scoped_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_get_session_context(agent_id: str, session_id: str) -> dict[str, object]:
        assert agent_id == "junie"
        assert session_id == "workspace-3"
        return {"repo": "continuum", "task": "tests"}

    monkeypatch.setattr(session_get.cache, "get_session_context", fake_get_session_context)

    result = await session_get.mem_session_get("junie", "workspace-3")

    assert result == {
        "status": "found",
        "agent_id": "junie",
        "session_id": "workspace-3",
        "context": {"repo": "continuum", "task": "tests"},
    }


@pytest.mark.asyncio
async def test_mem_session_clear_deletes_agent_scoped_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict[str, object] = {}

    async def fake_clear_session(agent_id: str, session_id: str) -> None:
        calls["agent_id"] = agent_id
        calls["session_id"] = session_id

    monkeypatch.setattr(session_clear.cache, "clear_session", fake_clear_session)

    result = await session_clear.mem_session_clear("antigravity", "workspace-4")

    assert result == {
        "status": "cleared",
        "agent_id": "antigravity",
        "session_id": "workspace-4",
    }
    assert calls == {
        "agent_id": "antigravity",
        "session_id": "workspace-4",
    }
