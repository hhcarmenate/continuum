# Continuum

Persistent memory system for AI agents, exposed via MCP.

`Continuum` stores durable context such as decisions, bugs, patterns, project context, and user preferences using a two-layer model:

- Hot memory in Redis for short-lived session state and pending memories.
- Cold memory in PostgreSQL for confirmed, searchable, long-term storage.

The current codebase already includes the MCP server, the storage layer, SQL migrations, and 9 memory tools.

## Current Status

This repository is in an early but functional base state.

Implemented:

- MCP server with `FastMCP`
- PostgreSQL connection pool with `asyncpg`
- Redis async cache
- SQL migrations for initial schema and agent-agnostic memory
- Full-text search in Spanish and English with `unaccent`
- Tool set for memory save/search/get/list/promote/forget and session set/get/clear
- Docker Compose for local PostgreSQL and Redis
- Unit and integration tests

Not implemented yet:

- Rich README examples beyond the MCP tool contract
- Migration runner command
- Observability and structured logging
- Authentication, multi-tenant isolation, or HTTP API beyond MCP transport

## Architecture

The system is intentionally split into two persistence layers:

### Redis

Used for volatile or review-pending data:

- `session:{agent_id}:{session_id}`: active agent context
- `pending:{key}`: memories below the auto-save importance threshold

Pending memories expire with a configurable TTL. By default, the TTL is 24 hours.

### PostgreSQL

Used for permanent memories:

- durable storage
- full-text search
- relevance ranking
- filtering by project, type, and importance

### Business Rule

When a memory is saved:

- If `importance >= MIN_IMPORTANCE_AUTO_SAVE`, it is stored directly in PostgreSQL.
- If `importance < MIN_IMPORTANCE_AUTO_SAVE`, it is stored in Redis as pending and must later be confirmed with `mem_promote` or discarded with `mem_forget`.

Default threshold:

```env
MIN_IMPORTANCE_AUTO_SAVE=7
```

## Memory Model

### Memory Types

- `decision`
- `bug`
- `pattern`
- `context`
- `preference`

### Memory Sources

- `agent`
- `user`

### Core Fields

Each memory contains:

- `project_id`
- `agent_id` for the client or coding agent identity
- `type`
- `title`
- `content`
- `tags`
- `importance` from 1 to 10
- `source`
- timestamps

## Project Structure

```text
.
├── docker-compose.yml
├── main.py
├── migrations/
│   ├── 001_initial.sql
│   └── 002_agent_agnostic_memory.sql
├── pyproject.toml
└── src/
    └── continuum/
        ├── __init__.py
        ├── cache.py
        ├── database.py
        ├── models.py
        ├── server.py
        └── tools/
            ├── forget.py
            ├── get.py
            ├── list.py
            ├── promote.py
            ├── save.py
            └── search.py
            ├── session_clear.py
            ├── session_get.py
            └── session_set.py
```

Notes:

- [`src/continuum/server.py`](src/continuum/server.py) is the real application entrypoint.
- [`main.py`](main.py) is currently just a placeholder and is not used by the package script.

## Requirements

- Python 3.12+
- `uv`
- Docker and Docker Compose
- A running PostgreSQL 16+ and Redis 7+ instance, either from Docker Compose or external services

## Installation

### 1. Install dependencies

```bash
uv sync
```

### 2. Copy environment variables

```bash
cp .env.example .env
```

### 3. Start PostgreSQL and Redis

```bash
docker compose up -d
```

### 4. Apply the migrations

This repository includes SQL migrations, but it does not yet include a migration runner command. Apply them manually against the target database in order.

Example with `psql`:

```bash
psql postgresql://memoria:memoria@localhost:5432/memoria -f migrations/001_initial.sql
psql postgresql://memoria:memoria@localhost:5432/memoria -f migrations/002_agent_agnostic_memory.sql
```

### 5. Start the MCP server

Using the package script:

```bash
uv run continuum
```

Or directly:

```bash
uv run python -m continuum.server
```

By default the server uses:

- `stdio` transport if `MCP_TRANSPORT` is not set
- host `0.0.0.0` and port `8000` for non-stdio transports

## Environment Variables

The example file is [`.env.example`](.env.example). The main variables are:

### PostgreSQL

```env
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=memoria
POSTGRES_USER=memoria
POSTGRES_PASSWORD=memoria
```

Optional DSN override:

```env
DATABASE_URL=postgresql://memoria:memoria@localhost:5432/memoria
```

### Redis

```env
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_TTL_SECONDS=86400
```

Optional URL override:

```env
REDIS_URL=redis://localhost:6379/0
```

### MCP Server

```env
MCP_TRANSPORT=stdio
MCP_HOST=0.0.0.0
MCP_PORT=8000
```

### Business Rules

```env
MIN_IMPORTANCE_AUTO_SAVE=7
```

## MCP Tools

The server registers 9 tools.

### `mem_save`

Creates a new memory.

Parameters:

- `project_id: str`
- `type: MemoryType`
- `title: str`
- `content: str`
- `agent_id: str | None = None`
- `tags: list[str] | None = None`
- `importance: int = 5`
- `source: MemorySource = agent`

Behavior:

- Saves directly to PostgreSQL when importance meets the threshold.
- Otherwise stores the memory in Redis as pending.
- Pending keys are agent-scoped and collision-resistant: `{project_id}:{agent_scope}:{slug}:{suffix}`.

### `mem_search`

Searches permanent memories using PostgreSQL full-text search.

Parameters:

- `query: str`
- `project_id: str | None = None`
- `agent_id: str | None = None`
- `type: MemoryType | None = None`
- `min_importance: int = 1`
- `limit: int = 20`

Returns results ordered by relevance.

### `mem_get`

Fetches a memory by ID or pending key.

Behavior:

- Checks Redis pending memories first.
- Falls back to PostgreSQL.

Note:

- The parameter is named `id`, but the current implementation also uses that same value to check Redis pending keys first.

### `mem_list`

Lists permanent memories ordered by `created_at DESC`.

Parameters:

- `project_id: str | None = None`
- `agent_id: str | None = None`
- `type: MemoryType | None = None`
- `limit: int = 20`
- `offset: int = 0`

Behavior:

- If `project_id` is provided, the response also includes pending Redis memories for that project.

### `mem_promote`

Promotes a pending memory from Redis to PostgreSQL.

Behavior:

1. Reads the pending memory from Redis
2. Ensures the project exists
3. Inserts the memory into PostgreSQL
4. Deletes the Redis pending entry

### `mem_forget`

Deletes a memory.

Behavior:

- Permanent memory deletion via PostgreSQL `id`
- Pending memory deletion via Redis `key`

### `mem_session_set`

Stores session context in Redis under an agent-scoped namespace.

Parameters:

- `agent_id: str`
- `session_id: str`
- `data: dict[str, Any]`
- `merge: bool = True`

### `mem_session_get`

Reads session context for a specific `agent_id` and `session_id`.

### `mem_session_clear`

Deletes session context for a specific `agent_id` and `session_id`.

## Client Integration Examples

This repository includes ready-to-adapt MCP client examples in [examples/clients/README.md](examples/clients/README.md).

Included examples:

- Claude Code
- Codex
- Cursor
- Junie
- Antigravity

Each client example now includes two pieces:

- MCP server config for connecting `Continuum`
- instruction snippet so the agent always sends the correct `agent_id` and `session_id`

The client config only connects the MCP server. To keep memory isolated per host, each client should also be instructed to use a stable `agent_id`, for example:

- `claude-code`
- `codex`
- `cursor`
- `junie`
- `antigravity`

The included examples also provide a shared startup script:

- [examples/clients/run-continuum-stdio.sh](examples/clients/run-continuum-stdio.sh)

And a shared baseline memory policy:

- [examples/clients/instructions/common-memory-rules.md](examples/clients/instructions/common-memory-rules.md)

## Search Design

The initial migration sets up:

- `pg_trgm`
- `unaccent`
- Spanish text search configuration
- English text search configuration
- weighted `tsvector` generation

Search vector weights:

- Title: weight `A`
- Content: weight `B`
- Tags: weight `C`

This makes title matches more relevant than content or tag matches.

## Local Development

Install development dependencies:

```bash
uv sync --dev
```

Run lint:

```bash
uv run ruff check .
```

Run tests:

```bash
uv run pytest
```

Current state:

- The repository has unit and integration tests.
- `ruff` and `pytest` are expected to pass on the current tree.

## Example Flow

Typical lifecycle for a low-confidence memory:

1. Agent calls `mem_save` with `importance=4`
2. Memory is stored in Redis under an agent-scoped pending key
3. User reviews it
4. User confirms with `mem_promote`
5. Memory is inserted into PostgreSQL and becomes searchable

Typical lifecycle for a high-confidence memory:

1. Agent calls `mem_save` with `importance=9`
2. Memory is inserted directly into PostgreSQL
3. It becomes available to `mem_search`, `mem_get`, and `mem_list`

## Known Gaps

These are the main gaps visible in the repository today:

- No committed git history yet
- No automated migration workflow
- No CI workflow yet for lint and integration tests

## Entrypoints

Package entrypoint:

```toml
[project.scripts]
continuum = "continuum.server:main"
```

Primary runtime module:

- [`src/continuum/server.py`](src/continuum/server.py)

## License

No license file is present in the repository yet.
