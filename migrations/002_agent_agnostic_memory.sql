-- ============================================================
--  continuum — 002_agent_agnostic_memory.sql
--  Add agent identity to durable memories.
-- ============================================================

ALTER TABLE memories
    ADD COLUMN IF NOT EXISTS agent_id VARCHAR(100);

CREATE INDEX IF NOT EXISTS idx_memories_agent_id
    ON memories (agent_id);
