"""
Pydantic v2 models for continuum.

No ORM — Pydantic for validation and serialization only.
asyncpg handles raw queries against PostgreSQL.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

# ── Enums ─────────────────────────────────────────────────────────────────────

class MemoryType(StrEnum):
    decision   = "decision"
    bug        = "bug"
    pattern    = "pattern"
    context    = "context"
    preference = "preference"


class MemorySource(StrEnum):
    agent = "agent"
    user  = "user"


# ── Reusable annotated types ─────────────────────────────────────────────────

ImportanceField = Annotated[int, Field(ge=1, le=10)]
TagList         = Annotated[list[str], Field(default_factory=list)]


# ── Projects ──────────────────────────────────────────────────────────────────

class ProjectCreate(BaseModel):
    name:        str      = Field(..., min_length=1, max_length=100)
    description: str | None = None
    stack:       TagList


class Project(ProjectCreate):
    model_config = ConfigDict(from_attributes=True)

    id:         uuid.UUID
    created_at: datetime


# ── Memories ──────────────────────────────────────────────────────────────────

class MemoryCreate(BaseModel):
    project_id: str         = Field(..., min_length=1, max_length=100)
    agent_id:   str | None  = Field(default=None, min_length=1, max_length=100)
    type:       MemoryType
    title:      str         = Field(..., min_length=1, max_length=300)
    content:    str         = Field(..., min_length=1)
    tags:       TagList
    importance: ImportanceField
    source:     MemorySource = MemorySource.agent


class Memory(MemoryCreate):
    model_config = ConfigDict(from_attributes=True)

    id:         uuid.UUID
    created_at: datetime
    updated_at: datetime


class MemoryUpdate(BaseModel):
    """All fields are optional — only provided fields are updated."""

    agent_id:   str | None        = Field(default=None, min_length=1, max_length=100)
    type:       MemoryType | None = None
    title:      str | None        = Field(default=None, min_length=1, max_length=300)
    content:    str | None        = Field(default=None, min_length=1)
    tags:       list[str] | None  = None
    importance: ImportanceField | None = None

    def non_none_fields(self) -> dict[str, object]:
        """Returns only non-None fields, ready for building an UPDATE query."""
        return {k: v for k, v in self.model_dump().items() if v is not None}


# ── Search ────────────────────────────────────────────────────────────────────

class SearchQuery(BaseModel):
    query:          str              = Field(..., min_length=1)
    project_id:     str | None       = None
    agent_id:       str | None       = Field(default=None, min_length=1, max_length=100)
    type:           MemoryType | None = None
    min_importance: ImportanceField  = 1
    limit:          int              = Field(default=20, ge=1, le=100)


class SearchResult(BaseModel):
    """A full-text search result with its relevance score."""

    memory: Memory
    rank:   float = Field(..., ge=0.0)
