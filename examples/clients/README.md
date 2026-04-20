# Client Config Examples

This folder contains example MCP client configurations for connecting different coding agents to `Continuum`.

These examples are intentionally stored in the `Continuum` repo because the server contract lives here. Each client should only need:

- an MCP config that starts this server
- a stable `agent_id` convention
- an instruction snippet telling the agent to always pass that `agent_id`

## Common Startup Command

The helper script below resolves the repo root automatically and starts the server over stdio:

- [run-continuum-stdio.sh](run-continuum-stdio.sh)

If your MCP client supports project-level configs inside this repo, you can usually reference:

```text
examples/clients/run-continuum-stdio.sh
```

If your client stores MCP configs outside the repo, replace it with an absolute path, for example:

```text
/absolute/path/to/continuum/examples/clients/run-continuum-stdio.sh
```

## Agent IDs

Recommended stable values:

- Claude Code: `claude-code`
- Codex: `codex`
- Cursor: `cursor`
- Junie: `junie`
- Antigravity: `antigravity`

## Instruction Snippet

Add a client-specific instruction so the agent always uses its `agent_id` when calling `Continuum` tools.

Example snippet:

```text
When using the continuum MCP server:
- Always pass agent_id="<CLIENT_AGENT_ID>" on mem_save, mem_search, and mem_list.
- Always use agent_id="<CLIENT_AGENT_ID>" together with a stable session_id on mem_session_set, mem_session_get, and mem_session_clear.
- Never omit agent_id unless the user explicitly asks for shared cross-agent memory.
```

Replace `<CLIENT_AGENT_ID>` with one of the recommended values above.

Shared baseline:

- [instructions/common-memory-rules.md](instructions/common-memory-rules.md)

## Files

- [claude-code/.mcp.json.example](claude-code/.mcp.json.example)
- [claude-code/AGENTS.md.example](claude-code/AGENTS.md.example)
- [codex/config.toml.example](codex/config.toml.example)
- [codex/AGENTS.md.example](codex/AGENTS.md.example)
- [cursor/mcp.json.example](cursor/mcp.json.example)
- [cursor/AGENTS.md.example](cursor/AGENTS.md.example)
- [junie/mcp.json.example](junie/mcp.json.example)
- [junie/agent-instructions.md.example](junie/agent-instructions.md.example)
- [antigravity/mcp_config.json.example](antigravity/mcp_config.json.example)
- [antigravity/agent-instructions.md.example](antigravity/agent-instructions.md.example)

## Source Notes

These examples follow the current MCP configuration shapes documented for:

- Claude Code MCP
- Codex MCP
- Cursor MCP
- Junie MCP
- Antigravity MCP custom server configs

The exact install location differs by client, but the server definition remains the same: launch `Continuum` over stdio.
