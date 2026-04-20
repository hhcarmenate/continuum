-- ============================================================
--  continuum — 001_initial.sql
--  Initial migration. Run ONLY once.
-- ============================================================

-- ── Extensions ───────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";   -- uuid_generate_v4()
CREATE EXTENSION IF NOT EXISTS "pg_trgm";     -- fuzzy similarity in titles
CREATE EXTENSION IF NOT EXISTS "unaccent";    -- search ignoring accents

-- ── Full-text search configurations with unaccent ────────
-- Spanish without accents
CREATE TEXT SEARCH CONFIGURATION es_unaccent ( COPY = spanish );
ALTER TEXT SEARCH CONFIGURATION es_unaccent
    ALTER MAPPING FOR hword, hword_part, word
    WITH unaccent, spanish_stem;

-- English without accents
CREATE TEXT SEARCH CONFIGURATION en_unaccent ( COPY = english );
ALTER TEXT SEARCH CONFIGURATION en_unaccent
    ALTER MAPPING FOR hword, hword_part, word
    WITH unaccent, english_stem;

-- ── Enums ─────────────────────────────────────────────────────
CREATE TYPE memory_type AS ENUM (
    'decision',
    'bug',
    'pattern',
    'context',
    'preference'
);

CREATE TYPE memory_source AS ENUM (
    'agent',
    'user'
);

-- ── Table: projects ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS projects (
    id          UUID         NOT NULL DEFAULT uuid_generate_v4(),
    name        VARCHAR(100) NOT NULL,
    description TEXT,
    stack       TEXT[]       NOT NULL DEFAULT '{}',
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    CONSTRAINT projects_pkey     PRIMARY KEY (id),
    CONSTRAINT projects_name_key UNIQUE (name)
);

-- ── Table: memories ───────────────────────────────────────────
-- project_id is VARCHAR (no FK) to allow cross-project references
-- and projects that don't yet exist in the projects table.
CREATE TABLE IF NOT EXISTS memories (
    id            UUID          NOT NULL DEFAULT uuid_generate_v4(),
    project_id    VARCHAR(100)  NOT NULL,
    agent_id      VARCHAR(100),
    type          memory_type   NOT NULL,
    title         VARCHAR(300)  NOT NULL,
    content       TEXT          NOT NULL,
    tags          TEXT[]        NOT NULL DEFAULT '{}',
    importance    SMALLINT      NOT NULL,
    source        memory_source NOT NULL DEFAULT 'agent',
    created_at    TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    search_vector TSVECTOR,

    CONSTRAINT memories_pkey       PRIMARY KEY (id),
    CONSTRAINT memories_importance CHECK (importance BETWEEN 1 AND 10)
);

-- ── Function + trigger: auto-update updated_at ─────────────────
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER memories_set_updated_at
    BEFORE UPDATE ON memories
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at();

-- ── Function + trigger: auto-generate search_vector ──────────────
-- Weights: title → A (max), content → B, tags → C
-- Indexed in Spanish AND English with unaccent support.
CREATE OR REPLACE FUNCTION memories_update_search_vector()
RETURNS TRIGGER AS $$
BEGIN
    NEW.search_vector :=
        -- title (weight A)
        setweight(to_tsvector('es_unaccent', coalesce(NEW.title,   '')), 'A') ||
        setweight(to_tsvector('en_unaccent', coalesce(NEW.title,   '')), 'A') ||
        -- content (weight B)
        setweight(to_tsvector('es_unaccent', coalesce(NEW.content, '')), 'B') ||
        setweight(to_tsvector('en_unaccent', coalesce(NEW.content, '')), 'B') ||
        -- tags (weight C) — array flattened to string
        setweight(to_tsvector('es_unaccent',
            coalesce(array_to_string(NEW.tags, ' '), '')), 'C') ||
        setweight(to_tsvector('en_unaccent',
            coalesce(array_to_string(NEW.tags, ' '), '')), 'C');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER memories_search_vector_update
    BEFORE INSERT OR UPDATE ON memories
    FOR EACH ROW
    EXECUTE FUNCTION memories_update_search_vector();

-- ── Indexes ───────────────────────────────────────────────────
-- Full-text search
CREATE INDEX IF NOT EXISTS idx_memories_search_vector
    ON memories USING GIN (search_vector);

-- Filter/search by exact tags
CREATE INDEX IF NOT EXISTS idx_memories_tags
    ON memories USING GIN (tags);

-- Filter by project
CREATE INDEX IF NOT EXISTS idx_memories_project_id
    ON memories (project_id);

-- Filter by agent
CREATE INDEX IF NOT EXISTS idx_memories_agent_id
    ON memories (agent_id);

-- Filter by type
CREATE INDEX IF NOT EXISTS idx_memories_type
    ON memories (type);

-- Order by descending importance (most relevant first)
CREATE INDEX IF NOT EXISTS idx_memories_importance
    ON memories (importance DESC);

-- Fuzzy search of titles with pg_trgm (tolerates typos)
CREATE INDEX IF NOT EXISTS idx_memories_title_trgm
    ON memories USING GIN (title gin_trgm_ops);
