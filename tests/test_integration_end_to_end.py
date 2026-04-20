from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
import pytest_asyncio

from continuum.cache import cache
from continuum.database import db
from continuum.models import MemoryType
from continuum.tools.forget import mem_forget
from continuum.tools.get import mem_get
from continuum.tools.list import mem_list
from continuum.tools.promote import mem_promote
from continuum.tools.save import mem_save
from continuum.tools.search import mem_search
from continuum.tools.session_clear import mem_session_clear
from continuum.tools.session_get import mem_session_get
from continuum.tools.session_set import mem_session_set


@pytest_asyncio.fixture
async def integration_services() -> None:
    try:
        if db.is_connected:
            await db.disconnect()
        if cache.is_connected:
            await cache.disconnect()

        await db.connect()
        await cache.connect()
        await _ensure_schema()
    except Exception as exc:  # pragma: no cover - exercised only in unavailable envs
        if cache.is_connected:
            await cache.disconnect()
        if db.is_connected:
            await db.disconnect()
        pytest.skip(f"integration services unavailable: {exc}")

    yield

    await cache.disconnect()
    await db.disconnect()


@pytest_asyncio.fixture(autouse=True)
async def integration_cleanup(integration_services: None) -> None:
    await _cleanup_integration_data()
    yield
    await _cleanup_integration_data()


@pytest.fixture
def project_id() -> str:
    return f"it-{uuid4().hex[:8]}"


async def _ensure_schema() -> None:
    migrations_dir = Path(__file__).resolve().parents[1] / "migrations"
    memories_exists = await db.fetchval("SELECT to_regclass('public.memories')")
    migration_paths = sorted(migrations_dir.glob("*.sql"))

    if memories_exists is not None:
        migration_paths = [path for path in migration_paths if path.name != "001_initial.sql"]

    for migration_path in migration_paths:
        await db.execute(migration_path.read_text())


async def _cleanup_integration_data() -> None:
    await db.execute("DELETE FROM memories WHERE project_id LIKE 'it-%'")
    await db.execute("DELETE FROM projects WHERE name LIKE 'it-%'")

    keys = [key async for key in cache.client.scan_iter(match="pending:it-*")]
    if keys:
        await cache.client.delete(*keys)

    session_keys = [key async for key in cache.client.scan_iter(match="session:*")]
    it_session_keys = [key for key in session_keys if ":it-" in key]
    if it_session_keys:
        await cache.client.delete(*it_session_keys)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_pending_memory_lifecycle_end_to_end(project_id: str) -> None:
    pending = await mem_save(
        project_id=project_id,
        type=MemoryType.context,
        title="Need review before persistence",
        content="Store this context only after user confirmation.",
        agent_id="claude-code",
        tags=["review"],
        importance=3,
    )

    assert pending["status"] == "pending"

    cached = await cache.get_pending_memory(pending["key"])
    assert cached is not None
    assert cached["project_id"] == project_id
    assert cached["agent_id"] == "claude-code"

    promoted = await mem_promote(pending["key"])
    assert promoted["status"] == "promoted"

    fetched = await mem_get(promoted["id"])
    assert fetched is not None
    assert fetched["status"] == "saved"
    assert fetched["memory"]["project_id"] == project_id
    assert fetched["memory"]["agent_id"] == "claude-code"

    forgotten = await mem_forget(id=promoted["id"])
    assert forgotten["status"] == "forgotten"

    assert await mem_get(promoted["id"]) is None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_list_and_search_reflect_saved_and_pending_memories(project_id: str) -> None:
    saved = await mem_save(
        project_id=project_id,
        type=MemoryType.decision,
        title="Persist architecture choice",
        content="Use PostgreSQL for durable memory search.",
        agent_id="codex",
        tags=["architecture"],
        importance=9,
    )
    pending = await mem_save(
        project_id=project_id,
        type=MemoryType.pattern,
        title="Review naming convention",
        content="Keep pending memory names deterministic.",
        agent_id="codex",
        tags=["redis"],
        importance=2,
    )

    listed = await mem_list(project_id=project_id, agent_id="codex")

    assert listed["count"] == 1
    assert listed["memories"][0]["id"] == saved["id"]
    assert listed["pending"][0]["key"] == pending["key"]

    searched = await mem_search(
        query="durable memory search",
        project_id=project_id,
        agent_id="codex",
        type=MemoryType.decision,
    )

    assert searched["total"] == 1
    assert searched["results"][0]["memory"]["id"] == saved["id"]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_updated_at_trigger_and_search_vector_refresh(project_id: str) -> None:
    saved = await mem_save(
        project_id=project_id,
        type=MemoryType.bug,
        title="Search refresh bug",
        content="Old content that should be replaced.",
        agent_id="cursor",
        tags=["search"],
        importance=8,
    )

    before = await db.fetchrow(
        """
        SELECT updated_at
        FROM memories
        WHERE id = $1
        """,
        saved["id"],
    )
    assert before is not None

    await db.execute("SELECT pg_sleep(0.01)")
    await db.execute(
        """
        UPDATE memories
        SET content = $2
        WHERE id = $1
        """,
        saved["id"],
        "Updated content now mentions synchronization and refresh.",
    )

    after = await db.fetchrow(
        """
        SELECT updated_at
        FROM memories
        WHERE id = $1
        """,
        saved["id"],
    )
    assert after is not None
    assert after["updated_at"] > before["updated_at"]

    searched = await mem_search(
        query="synchronization refresh",
        project_id=project_id,
        agent_id="cursor",
        type=MemoryType.bug,
    )

    assert searched["total"] == 1
    assert searched["results"][0]["memory"]["id"] == saved["id"]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_required_extensions_and_triggers_exist(integration_services: None) -> None:
    extensions = await db.fetch(
        """
        SELECT extname
        FROM pg_extension
        WHERE extname IN ('unaccent', 'pg_trgm')
        ORDER BY extname
        """
    )
    triggers = await db.fetch(
        """
        SELECT tgname
        FROM pg_trigger
        WHERE tgname IN ('memories_set_updated_at', 'memories_search_vector_update')
        ORDER BY tgname
        """
    )

    assert [row["extname"] for row in extensions] == ["pg_trgm", "unaccent"]
    assert [row["tgname"] for row in triggers] == [
        "memories_search_vector_update",
        "memories_set_updated_at",
    ]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_session_context_is_namespaced_by_agent(project_id: str) -> None:
    session_id = f"{project_id}-workspace"

    await mem_session_set(
        agent_id="claude-code",
        session_id=session_id,
        data={"repo": "continuum", "branch": "main"},
    )
    await mem_session_set(
        agent_id="codex",
        session_id=session_id,
        data={"repo": "continuum", "branch": "feature/tests"},
    )

    claude_context = await mem_session_get("claude-code", session_id)
    codex_context = await mem_session_get("codex", session_id)

    assert claude_context is not None
    assert codex_context is not None
    assert claude_context["context"]["branch"] == "main"
    assert codex_context["context"]["branch"] == "feature/tests"

    cleared = await mem_session_clear("claude-code", session_id)
    assert cleared["status"] == "cleared"
    assert await mem_session_get("claude-code", session_id) is None
    assert await mem_session_get("codex", session_id) is not None
