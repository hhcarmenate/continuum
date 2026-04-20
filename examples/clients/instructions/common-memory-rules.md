# Common Continuum Rules

Use these rules in any MCP-capable coding agent that connects to `continuum`.

```text
When using the continuum MCP server:
- Always pass a stable agent_id that identifies this client.
- Use mem_save with agent_id set to this client identity unless the user explicitly asks for shared cross-agent memory.
- Use mem_search and mem_list with the same agent_id by default so results stay scoped to this client.
- Use mem_session_set, mem_session_get, and mem_session_clear with both agent_id and a stable session_id for the current workspace or task.
- Only omit agent_id when the user explicitly wants shared memory across multiple agents.
- Prefer the same session_id across follow-up turns in the same project or task so hot session context remains coherent.
```
