"""mem_search — Full-text search with optional filters.

Searches against the bilingual `search_vector` using both Spanish and English
text search configurations, then ranks by the best match.
"""

from __future__ import annotations

from typing import Any

from continuum.database import db
from continuum.models import Memory, MemoryType, SearchQuery, SearchResult


async def mem_search(
    query: str,
    project_id: str | None = None,
    agent_id: str | None = None,
    type: MemoryType | None = None,
    min_importance: int = 1,
    limit: int = 20,
) -> dict[str, Any]:
    """Searches memories using full-text search with optional filters.

    Returns results ordered by relevance (rank DESC).
    """
    # Validate with Pydantic
    sq = SearchQuery(
        query=query,
        project_id=project_id,
        agent_id=agent_id,
        type=type,
        min_importance=min_importance,
        limit=limit,
    )

    # ── Build parameterized query dynamically ───────────────────
    conditions = [
        "("
        "m.search_vector @@ plainto_tsquery('es_unaccent', unaccent($1)) "
        "OR m.search_vector @@ plainto_tsquery('en_unaccent', unaccent($1))"
        ")",
        "m.importance >= $2",
    ]
    params: list[Any] = [sq.query, sq.min_importance]

    if sq.project_id is not None:
        params.append(sq.project_id)
        conditions.append(f"m.project_id = ${len(params)}")

    if sq.agent_id is not None:
        params.append(sq.agent_id)
        conditions.append(f"m.agent_id = ${len(params)}")

    if sq.type is not None:
        params.append(str(sq.type))
        conditions.append(f"m.type = ${len(params)}")

    params.append(sq.limit)

    sql = f"""
        SELECT m.id, m.project_id, m.agent_id, m.type, m.title, m.content, m.tags,
               m.importance, m.source, m.created_at, m.updated_at,
               GREATEST(
                   ts_rank(
                       m.search_vector,
                       plainto_tsquery('es_unaccent', unaccent($1))
                   ),
                   ts_rank(
                       m.search_vector,
                       plainto_tsquery('en_unaccent', unaccent($1))
                   )
               ) AS rank
        FROM memories m
        WHERE {' AND '.join(conditions)}
        ORDER BY rank DESC
        LIMIT ${len(params)}
    """

    rows = await db.fetch(sql, *params)

    results = []
    for row in rows:
        memory = Memory.model_validate(dict(row))
        result = SearchResult(memory=memory, rank=row["rank"])
        results.append(result.model_dump(mode="json"))

    return {"results": results, "total": len(results)}
