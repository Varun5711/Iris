"""
Context builder — assembles all data sources into a unified dict that can
be serialised and injected into LLM prompts.

Data sources tapped:
  - Postgres  : incident row, incident_events, affected_segments
  - Redis     : live segment speeds, diversion plan, signal plan candidates
  - pgvector  : top-5 SOP chunks, top-3 similar historical incidents
  - pgvector  : alert templates (chat variant only)

All DB and cache calls are best-effort; failures are logged and represented
as empty structures so the LLM can still produce a (lower-confidence) answer.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.integrations.groq.client import get_embedding
from src.integrations.postgres.client import (
    search_alert_templates,
    search_similar_incidents,
    search_similar_sop,
)

logger = logging.getLogger(__name__)

# Redis key prefixes (must match the ingest / state-engine workers).
_REDIS_SEGMENT_PREFIX = "segment:"
_REDIS_DIVERSION_PREFIX = "diversion:"
_REDIS_SIGNAL_PREFIX = "signal_plan:"


# ---------------------------------------------------------------------------
# Postgres helpers
# ---------------------------------------------------------------------------


async def _fetch_incident_state(incident_id: str, session: AsyncSession) -> dict[str, Any]:
    """
    Return a dict with:
      - incident   : core row from incidents
      - events     : list of recent incident_events (last 20)
      - segments   : list of affected_segments rows
    """
    incident: dict[str, Any] = {}
    events: list[dict] = []
    segments: list[dict] = []

    try:
        row = await session.execute(
            text(
                """
                SELECT id::text, status, severity, description, reporter_id,
                       corridor_id, detection_confidence,
                       created_at::text, updated_at::text
                FROM incidents
                WHERE id = CAST(:iid AS uuid)
                """
            ),
            {"iid": incident_id},
        )
        mapping = row.mappings().first()
        if mapping:
            incident = dict(mapping)
    except Exception as exc:  # noqa: BLE001
        logger.warning("_fetch_incident_state: incidents query failed — %s", exc)

    try:
        rows = await session.execute(
            text(
                """
                SELECT id::text, source, raw_payload, event_time::text
                FROM incident_events
                WHERE incident_id = CAST(:iid AS uuid)
                ORDER BY event_time DESC
                LIMIT 20
                """
            ),
            {"iid": incident_id},
        )
        events = [dict(r) for r in rows.mappings().all()]
    except Exception as exc:  # noqa: BLE001
        logger.warning("_fetch_incident_state: incident_events query failed — %s", exc)

    try:
        rows = await session.execute(
            text(
                """
                SELECT id::text, osm_way_id, delay_seconds, congestion_pct
                FROM affected_segments
                WHERE incident_id = CAST(:iid AS uuid)
                """
            ),
            {"iid": incident_id},
        )
        segments = [dict(r) for r in rows.mappings().all()]
    except Exception as exc:  # noqa: BLE001
        logger.warning("_fetch_incident_state: affected_segments query failed — %s", exc)

    return {"incident": incident, "events": events, "segments": segments}


# ---------------------------------------------------------------------------
# Redis helpers
# ---------------------------------------------------------------------------


async def _get_redis_json(redis_client: Any, key: str) -> dict | list | None:
    """Fetch and JSON-decode a Redis value; return None on miss/error."""
    try:
        raw = await redis_client.get(key)
        if raw is None:
            return None
        return json.loads(raw)
    except Exception as exc:  # noqa: BLE001
        logger.warning("_get_redis_json key=%s failed — %s", key, exc)
        return None


async def _fetch_live_segments(
    incident_id: str, redis_client: Any
) -> list[dict]:
    """Return live segment speed objects from Redis for this incident."""
    try:
        pattern = f"{_REDIS_SEGMENT_PREFIX}{incident_id}:*"
        keys = await redis_client.keys(pattern)
        results = []
        for key in keys:
            data = await _get_redis_json(redis_client, key)
            if data:
                results.append(data)
        return results
    except Exception as exc:  # noqa: BLE001
        logger.warning("_fetch_live_segments failed — %s", exc)
        return []


async def _fetch_diversion(incident_id: str, redis_client: Any) -> dict | None:
    """Return the cached diversion plan from Redis."""
    return await _get_redis_json(redis_client, f"{_REDIS_DIVERSION_PREFIX}{incident_id}")


async def _fetch_signal_plan(incident_id: str, redis_client: Any) -> dict | None:
    """Return the cached signal plan from Redis."""
    return await _get_redis_json(redis_client, f"{_REDIS_SIGNAL_PREFIX}{incident_id}")


# ---------------------------------------------------------------------------
# pgvector helpers
# ---------------------------------------------------------------------------


async def _embed_text(text_str: str, groq_client: Any) -> list[float]:
    """Embed text using the shared Groq client (with fallback)."""
    # groq_client param is kept for API symmetry; actual call goes through
    # the module-level get_embedding which handles fallback internally.
    return await get_embedding(text_str)


async def _fetch_sop_chunks(
    query_text: str, session: AsyncSession, top_k: int = 5
) -> list[dict]:
    """Embed query_text and return top-k SOP chunks via pgvector."""
    try:
        embedding = await get_embedding(query_text)
        return await search_similar_sop(embedding, top_k=top_k, session=session)
    except Exception as exc:  # noqa: BLE001
        logger.warning("_fetch_sop_chunks failed — %s", exc)
        return []


async def _fetch_similar_incidents(
    query_text: str, session: AsyncSession, top_k: int = 3
) -> list[dict]:
    """Embed query_text and return top-k similar historical incidents."""
    try:
        embedding = await get_embedding(query_text)
        return await search_similar_incidents(embedding, top_k=top_k, session=session)
    except Exception as exc:  # noqa: BLE001
        logger.warning("_fetch_similar_incidents failed — %s", exc)
        return []


async def _fetch_alert_templates(
    query_text: str, session: AsyncSession
) -> list[dict]:
    """Embed query_text and return top-2 alert templates per channel."""
    templates: list[dict] = []
    for channel in ("vms", "radio", "social"):
        try:
            embedding = await get_embedding(query_text)
            results = await search_alert_templates(
                embedding, channel=channel, top_k=2, session=session
            )
            templates.extend(results)
        except Exception as exc:  # noqa: BLE001
            logger.warning("_fetch_alert_templates channel=%s failed — %s", channel, exc)
    return templates


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def build_recommendation_context(
    incident_id: str,
    session: AsyncSession,
    redis_client: Any,
    groq_client: Any,
) -> dict:
    """
    Assemble the full context dict used when generating a recommendation.

    Keys in the returned dict:
    - ``incident_state``     — Postgres: incident + events + affected segments
    - ``live_segments``      — Redis: real-time segment data
    - ``diversion``          — Redis: current diversion plan (or None)
    - ``signal_plan``        — Redis: current signal plan candidates (or None)
    - ``sop_chunks``         — pgvector: top-5 SOP passages relevant to incident
    - ``similar_incidents``  — pgvector: top-3 historical incidents

    Parameters
    ----------
    incident_id:
        UUID string of the active incident.
    session:
        Active SQLAlchemy async session.
    redis_client:
        aioredis / redis-py async client.
    groq_client:
        AsyncGroq client instance (used for embedding).

    Returns
    -------
    dict
        Structured context ready for :func:`format_context_for_prompt`.
    """
    incident_state = await _fetch_incident_state(incident_id, session)

    # Use incident description as the embedding query.
    description: str = (
        incident_state.get("incident", {}).get("description") or ""
    )
    query_text = description or f"traffic incident {incident_id}"

    live_segments, diversion, signal_plan, sop_chunks, similar_incidents = (
        await _fetch_live_segments(incident_id, redis_client),
        await _fetch_diversion(incident_id, redis_client),
        await _fetch_signal_plan(incident_id, redis_client),
        await _fetch_sop_chunks(query_text, session),
        await _fetch_similar_incidents(query_text, session),
    )

    return {
        "incident_id": incident_id,
        "incident_state": incident_state,
        "live_segments": live_segments,
        "diversion": diversion,
        "signal_plan": signal_plan,
        "sop_chunks": sop_chunks,
        "similar_incidents": similar_incidents,
    }


async def build_chat_context(
    incident_id: str,
    question: str,
    session: AsyncSession,
    redis_client: Any,
    groq_client: Any,
) -> dict:
    """
    Assemble context for a conversational chat question about an incident.

    Identical to :func:`build_recommendation_context` but:
    - Uses the officer's *question* text as the embedding query for SOP search
      so the retrieved passages are relevant to what the officer is asking.
    - Also fetches ``alert_templates`` to support alert-draft questions.

    Parameters
    ----------
    incident_id:
        UUID string of the active incident.
    question:
        Free-text question from the officer.
    session:
        Active SQLAlchemy async session.
    redis_client:
        aioredis / redis-py async client.
    groq_client:
        AsyncGroq client instance.

    Returns
    -------
    dict
        Structured context including ``alert_templates`` key.
    """
    incident_state = await _fetch_incident_state(incident_id, session)

    # SOP search is driven by the question, not the incident description.
    sop_query = question.strip() or "traffic management standard operating procedure"

    # Incident description still drives the historical-incident search.
    description: str = (
        incident_state.get("incident", {}).get("description") or ""
    )
    incident_query = description or f"traffic incident {incident_id}"

    live_segments = await _fetch_live_segments(incident_id, redis_client)
    diversion = await _fetch_diversion(incident_id, redis_client)
    signal_plan = await _fetch_signal_plan(incident_id, redis_client)
    sop_chunks = await _fetch_sop_chunks(sop_query, session)
    similar_incidents = await _fetch_similar_incidents(incident_query, session)
    alert_templates = await _fetch_alert_templates(incident_query, session)

    return {
        "incident_id": incident_id,
        "question": question,
        "incident_state": incident_state,
        "live_segments": live_segments,
        "diversion": diversion,
        "signal_plan": signal_plan,
        "sop_chunks": sop_chunks,
        "similar_incidents": similar_incidents,
        "alert_templates": alert_templates,
    }


# ---------------------------------------------------------------------------
# Prompt string formatter
# ---------------------------------------------------------------------------


def format_context_for_prompt(context: dict) -> str:
    """
    Convert the context dict into a well-structured string for LLM injection.

    Each section is separated by a header line so the LLM can distinguish
    between data sources.

    Parameters
    ----------
    context:
        Dict produced by :func:`build_recommendation_context` or
        :func:`build_chat_context`.

    Returns
    -------
    str
        Multi-section plain-text representation of the context.
    """
    sections: list[str] = []

    # ---- Incident core -------------------------------------------------------
    incident_state = context.get("incident_state", {})
    incident = incident_state.get("incident", {})
    if incident:
        lines = ["=== INCIDENT ==="]
        lines.append(f"ID:          {incident.get('id', 'unknown')}")
        lines.append(f"Status:      {incident.get('status', 'unknown')}")
        lines.append(f"Severity:    {incident.get('severity', 'unknown')}")
        lines.append(f"Corridor:    {incident.get('corridor_id', 'N/A')}")
        lines.append(f"Description: {incident.get('description', 'N/A')}")
        lines.append(f"Created:     {incident.get('created_at', 'N/A')}")
        lines.append(f"Confidence:  {incident.get('detection_confidence', 0.0):.2f}")
        sections.append("\n".join(lines))

    # ---- Recent events -------------------------------------------------------
    events = incident_state.get("events", [])
    if events:
        lines = ["=== RECENT EVENTS (last 20) ==="]
        for ev in events[:20]:
            payload_str = json.dumps(ev.get("raw_payload") or {}, ensure_ascii=False)[:200]
            lines.append(
                f"[{ev.get('event_time', '?')}] source={ev.get('source', '?')} "
                f"payload={payload_str}"
            )
        sections.append("\n".join(lines))

    # ---- Affected segments ---------------------------------------------------
    segments = incident_state.get("segments", [])
    if segments:
        lines = ["=== AFFECTED SEGMENTS ==="]
        for seg in segments:
            lines.append(
                f"osm_way={seg.get('osm_way_id')} "
                f"delay={seg.get('delay_seconds')}s "
                f"congestion={seg.get('congestion_pct', 0.0):.1f}%"
            )
        sections.append("\n".join(lines))

    # ---- Live segment data ---------------------------------------------------
    live = context.get("live_segments", [])
    if live:
        lines = ["=== LIVE SEGMENT DATA ==="]
        for seg in live:
            lines.append(json.dumps(seg, ensure_ascii=False)[:300])
        sections.append("\n".join(lines))

    # ---- Diversion plan ------------------------------------------------------
    diversion = context.get("diversion")
    if diversion:
        lines = ["=== DIVERSION PLAN ==="]
        lines.append(json.dumps(diversion, indent=2, ensure_ascii=False)[:800])
        sections.append("\n".join(lines))

    # ---- Signal plan ---------------------------------------------------------
    signal_plan = context.get("signal_plan")
    if signal_plan:
        lines = ["=== SIGNAL PLAN CANDIDATES ==="]
        lines.append(json.dumps(signal_plan, indent=2, ensure_ascii=False)[:800])
        sections.append("\n".join(lines))

    # ---- SOP chunks ----------------------------------------------------------
    sop_chunks = context.get("sop_chunks", [])
    if sop_chunks:
        lines = ["=== STANDARD OPERATING PROCEDURES (top matches) ==="]
        for i, chunk in enumerate(sop_chunks, 1):
            lines.append(
                f"[SOP-{i}] {chunk.get('title', 'Untitled')} "
                f"(source: {chunk.get('source_file', 'unknown')}, "
                f"distance: {chunk.get('distance', 1.0):.3f})"
            )
            lines.append(chunk.get("content", "")[:400])
        sections.append("\n".join(lines))

    # ---- Similar incidents ---------------------------------------------------
    similar = context.get("similar_incidents", [])
    if similar:
        lines = ["=== SIMILAR HISTORICAL INCIDENTS ==="]
        for i, inc in enumerate(similar, 1):
            lines.append(
                f"[HIST-{i}] incident_id={inc.get('incident_id')} "
                f"outcome={inc.get('outcome', 'unknown')} "
                f"resolved_in={inc.get('resolution_minutes', '?')} min "
                f"distance={inc.get('distance', 1.0):.3f}"
            )
            lines.append(inc.get("summary_text", "")[:300])
        sections.append("\n".join(lines))

    # ---- Alert templates (chat variant) -------------------------------------
    alert_templates = context.get("alert_templates", [])
    if alert_templates:
        lines = ["=== ALERT TEMPLATES (reference) ==="]
        for tmpl in alert_templates:
            lines.append(
                f"channel={tmpl.get('channel')} type={tmpl.get('incident_type', 'generic')} "
                f"→ {tmpl.get('template_text', '')[:200]}"
            )
        sections.append("\n".join(lines))

    # ---- Officer question (chat variant) ------------------------------------
    question = context.get("question")
    if question:
        sections.append(f"=== OFFICER QUESTION ===\n{question}")

    return "\n\n".join(sections) if sections else "(no context available)"
