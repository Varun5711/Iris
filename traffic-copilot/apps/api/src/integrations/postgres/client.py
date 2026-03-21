"""
pgvector + PostGIS query helpers for TrafficCopilot.

All functions accept a SQLAlchemy ``AsyncSession`` so they compose naturally
with the existing session/transaction management in ``src.db.session``.

Vector operations use raw SQL via ``sqlalchemy.text`` because the pgvector
SQLAlchemy dialect may not be available or may need specific casting; raw SQL
is always portable and explicit.

Embedding dimension: 1024 — matches the schema defined in
``src/db/migrations/001_initial.sql`` and ``002_pgvector_extended.sql``.

Usage
-----
    from src.integrations.postgres.client import search_similar_sop
    from src.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        chunks = await search_similar_sop(embedding, top_k=5, session=session)
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Vector similarity search — SOP chunks
# ---------------------------------------------------------------------------


async def search_similar_sop(
    embedding: list[float],
    top_k: int = 5,
    *,
    session: AsyncSession,
) -> list[dict[str, Any]]:
    """
    Return the *top_k* SOP chunks most semantically similar to *embedding*.

    Uses cosine distance (``<=>`` operator) with an IVFFlat index.

    Parameters
    ----------
    embedding:
        Query embedding vector (1024 floats).
    top_k:
        Maximum number of results.
    session:
        Active ``AsyncSession``.

    Returns
    -------
    list[dict]
        Each dict has keys: ``id``, ``title``, ``content``, ``source_file``,
        ``distance`` (cosine distance; lower is more similar).
    """
    vector_literal = _format_vector(embedding)
    sql = text(
        f"""
        SELECT
            id::text,
            title,
            content,
            source_file,
            (embedding <=> '{vector_literal}'::vector) AS distance
        FROM sop_chunks
        WHERE embedding IS NOT NULL
        ORDER BY embedding <=> '{vector_literal}'::vector
        LIMIT :top_k
        """
    )
    result = await session.execute(sql, {"top_k": top_k})
    rows = result.mappings().all()
    return [dict(row) for row in rows]


# ---------------------------------------------------------------------------
# Vector similarity search — incident summaries
# ---------------------------------------------------------------------------


async def search_similar_incidents(
    embedding: list[float],
    top_k: int = 3,
    *,
    session: AsyncSession,
) -> list[dict[str, Any]]:
    """
    Return the *top_k* historical incident summaries most similar to *embedding*.

    Parameters
    ----------
    embedding:
        Query embedding vector (1024 floats).
    top_k:
        Maximum number of results.
    session:
        Active ``AsyncSession``.

    Returns
    -------
    list[dict]
        Each dict has keys: ``id``, ``incident_id``, ``summary_text``,
        ``outcome``, ``resolution_minutes``, ``distance``.
    """
    vector_literal = _format_vector(embedding)
    sql = text(
        f"""
        SELECT
            id::text,
            incident_id::text,
            summary_text,
            outcome,
            resolution_minutes,
            (embedding <=> '{vector_literal}'::vector) AS distance
        FROM incident_summaries
        WHERE embedding IS NOT NULL
        ORDER BY embedding <=> '{vector_literal}'::vector
        LIMIT :top_k
        """
    )
    result = await session.execute(sql, {"top_k": top_k})
    rows = result.mappings().all()
    return [dict(row) for row in rows]


# ---------------------------------------------------------------------------
# Vector similarity search — alert templates
# ---------------------------------------------------------------------------


async def search_alert_templates(
    embedding: list[float],
    channel: str,
    top_k: int = 2,
    *,
    session: AsyncSession,
) -> list[dict[str, Any]]:
    """
    Return the *top_k* alert templates for *channel* most similar to *embedding*.

    Parameters
    ----------
    embedding:
        Query embedding vector (1024 floats).
    channel:
        One of ``'vms'``, ``'radio'``, ``'social'``.
    top_k:
        Maximum number of results.
    session:
        Active ``AsyncSession``.

    Returns
    -------
    list[dict]
        Each dict has keys: ``id``, ``channel``, ``template_text``,
        ``incident_type``, ``distance``.
    """
    vector_literal = _format_vector(embedding)
    sql = text(
        f"""
        SELECT
            id::text,
            channel,
            template_text,
            incident_type,
            (embedding <=> '{vector_literal}'::vector) AS distance
        FROM alert_templates
        WHERE embedding IS NOT NULL
          AND channel = :channel
        ORDER BY embedding <=> '{vector_literal}'::vector
        LIMIT :top_k
        """
    )
    result = await session.execute(sql, {"channel": channel, "top_k": top_k})
    rows = result.mappings().all()
    return [dict(row) for row in rows]


# ---------------------------------------------------------------------------
# Upsert helpers
# ---------------------------------------------------------------------------


async def upsert_sop_chunk(
    title: str,
    content: str,
    embedding: list[float],
    source_file: str,
    *,
    session: AsyncSession,
) -> None:
    """
    Insert or update a SOP chunk identified by *(source_file, title)*.

    If a row with the same ``source_file`` and ``title`` already exists its
    ``content`` and ``embedding`` are updated.  Otherwise a new row is inserted.
    """
    vector_literal = _format_vector(embedding)
    sql = text(
        f"""
        INSERT INTO sop_chunks (title, content, embedding, source_file)
        VALUES (:title, :content, '{vector_literal}'::vector, :source_file)
        ON CONFLICT DO NOTHING
        """
    )
    await session.execute(
        sql,
        {
            "title": title,
            "content": content,
            "source_file": source_file,
        },
    )
    await session.commit()
    logger.debug("Upserted SOP chunk title=%r source_file=%r", title, source_file)


async def upsert_incident_summary(
    incident_id: str,
    summary_text: str,
    embedding: list[float],
    outcome: str,
    resolution_minutes: int,
    *,
    session: AsyncSession,
) -> None:
    """
    Insert or update an incident summary for *incident_id*.

    On conflict the summary, embedding, outcome and resolution_minutes are
    refreshed.
    """
    vector_literal = _format_vector(embedding)
    sql = text(
        f"""
        INSERT INTO incident_summaries
            (incident_id, summary_text, embedding, outcome, resolution_minutes)
        VALUES
            (:incident_id::uuid, :summary_text, '{vector_literal}'::vector,
             :outcome, :resolution_minutes)
        ON CONFLICT (incident_id)
        DO UPDATE SET
            summary_text       = EXCLUDED.summary_text,
            embedding          = EXCLUDED.embedding,
            outcome            = EXCLUDED.outcome,
            resolution_minutes = EXCLUDED.resolution_minutes
        """
    )
    await session.execute(
        sql,
        {
            "incident_id": incident_id,
            "summary_text": summary_text,
            "outcome": outcome,
            "resolution_minutes": resolution_minutes,
        },
    )
    await session.commit()
    logger.debug("Upserted incident summary incident_id=%s", incident_id)


async def upsert_alert_template(
    channel: str,
    template_text: str,
    incident_type: str,
    embedding: list[float],
    *,
    session: AsyncSession,
) -> None:
    """
    Insert an alert template row.

    Alert templates are generally immutable reference data loaded by the seed
    script so this performs a plain INSERT with ``ON CONFLICT DO NOTHING`` to
    avoid accidental overwrites.
    """
    vector_literal = _format_vector(embedding)
    sql = text(
        f"""
        INSERT INTO alert_templates (channel, template_text, incident_type, embedding)
        VALUES (:channel, :template_text, :incident_type, '{vector_literal}'::vector)
        ON CONFLICT DO NOTHING
        """
    )
    await session.execute(
        sql,
        {
            "channel": channel,
            "template_text": template_text,
            "incident_type": incident_type,
        },
    )
    await session.commit()
    logger.debug(
        "Upserted alert template channel=%s incident_type=%s", channel, incident_type
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _format_vector(embedding: list[float]) -> str:
    """
    Format a Python list of floats as a pgvector literal string.

    Example: ``[0.1, 0.2, 0.3]`` → ``'[0.1,0.2,0.3]'``
    """
    inner = ",".join(str(float(v)) for v in embedding)
    return f"[{inner}]"
