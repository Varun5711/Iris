"""
Incident lifecycle management for the TrafficCopilot detection pipeline.

Core function: :func:`handle_detection`

The function is called once per normalised signal.  It maintains an in-process
dict of :class:`~src.modules.detector.scorer.IncidentScorer` instances keyed
by corridor/geo-cluster ID, applies the new signal, and then:

1. Creates a new incident in the DB if confidence crosses the threshold and
   no active incident exists for the corridor.
2. Updates the existing incident (stores the correlated event) if confidence
   stays above threshold.
3. Resolves the incident if :meth:`~IncidentScorer.should_resolve` returns
   ``True``.
4. Publishes a ``incident.state.updated`` Kafka message after every
   create / update / resolve.
5. Caches the incident snapshot in Redis.

State is intentionally held in-process (module-level dict).  For a multi-
process deployment this would need an external store, but is appropriate for
the single-process hackathon architecture.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.integrations.kafka.topics import INCIDENT_STATE_UPDATED
from src.integrations.redis.client import cache_set, incident_snapshot_key
from src.modules.detector.rules import score_event
from src.modules.detector.scorer import DetectionState, IncidentScorer
from src.schemas.event import TrafficEvent

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level scorer registry
# ---------------------------------------------------------------------------

_scorers: dict[str, IncidentScorer] = {}

# Decay half-life in seconds for each scorer
_DECAY_SECONDS: int = 300

# Default severity assigned to auto-detected incidents
_DEFAULT_AUTO_SEVERITY: str = "medium"

# Redis TTL for incident snapshots (10 minutes)
_SNAPSHOT_TTL: int = 600


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _corridor_key(event: TrafficEvent) -> str:
    """
    Derive a stable corridor/cluster key from the event.

    Preference order:
    1. ``event.corridor_id``
    2. Geo-cluster derived from lat/lon rounded to 3 decimal places
    3. Fallback: ``"unknown"``
    """
    if event.corridor_id:
        return event.corridor_id
    if event.lat is not None and event.lon is not None:
        return f"geo:{event.lat:.3f},{event.lon:.3f}"
    return "unknown"


def _get_or_create_scorer(corridor_key: str) -> IncidentScorer:
    """Return existing scorer or create a new one for *corridor_key*."""
    if corridor_key not in _scorers:
        _scorers[corridor_key] = IncidentScorer(
            corridor_id=corridor_key,
            decay_seconds=_DECAY_SECONDS,
        )
    return _scorers[corridor_key]


async def _create_incident_in_db(
    event: TrafficEvent,
    state: DetectionState,
    session: AsyncSession,
) -> str:
    """
    Insert a new row into ``incidents`` and return the new UUID as a string.

    Uses raw SQL to stay consistent with the rest of the codebase which avoids
    an ORM layer for the detector path.
    """
    description: str = _build_description(event, state)

    # Derive severity from source type
    severity: str = _default_severity(event)

    # Build PostGIS point expression
    location_expr: str
    params: dict[str, Any] = {
        "status": "active",
        "severity": severity,
        "description": description,
        "reporter_id": _reporter_id(event),
        "corridor_id": event.corridor_id,
        "confidence": state.confidence,
    }

    if event.lat is not None and event.lon is not None:
        location_expr = "ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)"
        params["lat"] = event.lat
        params["lon"] = event.lon
    else:
        location_expr = "NULL"

    sql = text(
        f"""
        INSERT INTO incidents
            (status, severity, description, reporter_id, location,
             corridor_id, detection_confidence)
        VALUES
            (:status, :severity, :description, :reporter_id,
             {location_expr}, :corridor_id, :confidence)
        RETURNING id::text
        """
    )
    result = await session.execute(sql, params)
    await session.commit()
    incident_id: str = result.scalar_one()
    return incident_id


async def _update_incident_in_db(
    incident_id: str,
    state: DetectionState,
    session: AsyncSession,
) -> None:
    """Update ``detection_confidence`` and ``updated_at`` on an existing incident."""
    sql = text(
        """
        UPDATE incidents
        SET detection_confidence = :confidence,
            updated_at           = now()
        WHERE id = CAST(:incident_id AS uuid)
        """
    )
    await session.execute(
        sql, {"confidence": state.confidence, "incident_id": incident_id}
    )
    await session.commit()


async def _resolve_incident_in_db(
    incident_id: str,
    session: AsyncSession,
) -> None:
    """Set incident status to ``'resolved'``."""
    sql = text(
        """
        UPDATE incidents
        SET status     = 'resolved',
            updated_at = now()
        WHERE id = CAST(:incident_id AS uuid)
          AND status NOT IN ('resolved', 'false_alarm')
        """
    )
    await session.execute(sql, {"incident_id": incident_id})
    await session.commit()


async def _store_incident_event(
    incident_id: str,
    event: TrafficEvent,
    session: AsyncSession,
) -> None:
    """Append a correlated raw event to ``incident_events``."""
    sql = text(
        """
        INSERT INTO incident_events (incident_id, source, raw_payload, event_time)
        VALUES (CAST(:incident_id AS uuid), :source, CAST(:payload AS jsonb), :event_time)
        """
    )
    import json

    await session.execute(
        sql,
        {
            "incident_id": incident_id,
            "source": event.source,
            "payload": json.dumps(event.payload, default=str),
            "event_time": event.event_time,
        },
    )
    await session.commit()


async def _cache_snapshot(incident_id: str, state: DetectionState) -> None:
    """Write a lightweight incident state snapshot to Redis."""
    try:
        snapshot: dict[str, Any] = {
            "incident_id": incident_id,
            "confidence": state.confidence,
            "signal_counts": state.signal_counts,
            "last_updated": state.last_updated.isoformat(),
        }
        await cache_set(
            incident_snapshot_key(incident_id),
            snapshot,
            ttl_seconds=_SNAPSHOT_TTL,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to cache incident snapshot %s: %s", incident_id, exc)


async def _publish_state_update(
    incident_id: str,
    status: str,
    state: DetectionState,
    event: TrafficEvent,
    kafka_producer: Any,
) -> None:
    """Publish an ``incident.state.updated`` message to Kafka."""
    try:
        from src.integrations.kafka.producer import publish

        message: dict[str, Any] = {
            "incident_id": incident_id,
            "status": status,
            "confidence": state.confidence,
            "corridor_id": event.corridor_id,
            "lat": event.lat,
            "lon": event.lon,
            "signal_counts": state.signal_counts,
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        }
        await publish(
            topic=INCIDENT_STATE_UPDATED,
            value=message,
            key=incident_id,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Failed to publish state update for incident %s: %s", incident_id, exc
        )


# ---------------------------------------------------------------------------
# Severity / description helpers
# ---------------------------------------------------------------------------


def _default_severity(event: TrafficEvent) -> str:
    """Derive a default severity string from event source."""
    from src.schemas.event import ManualIncidentEvent

    if isinstance(event, ManualIncidentEvent):
        return event.severity
    return _DEFAULT_AUTO_SEVERITY


def _reporter_id(event: TrafficEvent) -> str:
    """Extract reporter ID from event when available."""
    from src.schemas.event import ManualIncidentEvent, RadioTranscriptEvent

    if isinstance(event, ManualIncidentEvent):
        return event.reporter_id
    if isinstance(event, RadioTranscriptEvent):
        return event.unit_id
    return "auto-detector"


def _build_description(event: TrafficEvent, state: DetectionState) -> str:
    """Build a short auto-generated incident description."""
    from src.schemas.event import (
        CameraMetaEvent,
        ManualIncidentEvent,
        RadioTranscriptEvent,
        SensorSpeedEvent,
    )

    if isinstance(event, ManualIncidentEvent):
        return event.description
    if isinstance(event, RadioTranscriptEvent):
        return f"Radio report: {event.transcript[:200]}"
    if isinstance(event, SensorSpeedEvent):
        return (
            f"Speed anomaly on segment {event.segment_id}: "
            f"{event.speed_kmh:.1f} km/h "
            f"(free-flow {event.free_flow_kmh:.1f} km/h). "
            f"Confidence {state.confidence:.0%}."
        )
    if isinstance(event, CameraMetaEvent):
        return (
            f"Camera {event.camera_id} detected incident "
            f"(confidence {event.confidence:.0%}, "
            f"lane_blocked={event.lane_blocked})."
        )
    return f"Auto-detected incident from {event.source} source."


# ---------------------------------------------------------------------------
# Core lifecycle function
# ---------------------------------------------------------------------------


async def handle_detection(
    event: TrafficEvent,
    score: float,
    session: AsyncSession,
    redis_client: Any,  # passed for interface consistency; we use module-level helpers
    kafka_producer: Any,  # passed for interface consistency; we use publish() directly
    confidence_threshold: float = 0.5,
) -> str | None:
    """
    Core detection-loop step — called once per normalised, scored signal.

    Steps
    -----
    1. Resolve the corridor/cluster key for *event*.
    2. Retrieve or create the :class:`IncidentScorer` for that corridor.
    3. Add the signal; obtain the updated :class:`DetectionState`.
    4. Branch on confidence vs. threshold:

       a. **confidence >= threshold, no active incident** → create incident in
          DB, store the triggering event, cache snapshot, publish Kafka message.
       b. **confidence >= threshold, active incident** → update confidence in
          DB, store the correlated event, refresh cache, publish Kafka message.
       c. **should_resolve() → True** → resolve incident in DB, clear scorer's
          incident_id, publish Kafka message.
       d. **below threshold, no active incident** → no-op (monitoring only).

    Parameters
    ----------
    event:
        A normalised :class:`~src.schemas.event.TrafficEvent` subclass.
    score:
        Float confidence contribution from the rules scorer.
    session:
        Active :class:`~sqlalchemy.ext.asyncio.AsyncSession`.
    redis_client:
        Injected Redis client reference (not used directly; module helpers are
        used instead for testability).
    kafka_producer:
        Injected Kafka producer reference (not used directly; ``publish()`` is
        called via the module singleton).
    confidence_threshold:
        Minimum confidence to create or sustain an incident.  Default 0.5.

    Returns
    -------
    str | None
        The active incident UUID string if an incident is active after this
        call, or ``None`` if no incident is active.
    """
    corridor_key: str = _corridor_key(event)
    scorer: IncidentScorer = _get_or_create_scorer(corridor_key)

    state: DetectionState = scorer.add_signal(event, score)
    confidence: float = state.confidence

    logger.debug(
        "Detection signal: corridor=%s source=%s score=%.3f agg_confidence=%.3f",
        corridor_key,
        event.source,
        score,
        confidence,
    )

    # ------------------------------------------------------------------
    # Path A: Confidence >= threshold — create or update incident
    # ------------------------------------------------------------------
    if confidence >= confidence_threshold:
        if state.incident_id is None:
            # --- CREATE ---
            try:
                incident_id: str = await _create_incident_in_db(
                    event, state, session
                )
            except Exception as exc:
                logger.error(
                    "Failed to create incident for corridor %s: %s",
                    corridor_key,
                    exc,
                )
                return None

            scorer.set_incident_id(incident_id)
            state = scorer.get_state()

            await _store_incident_event(incident_id, event, session)
            await _cache_snapshot(incident_id, state)
            await _publish_state_update(
                incident_id, "created", state, event, kafka_producer
            )

            logger.info(
                "Incident CREATED id=%s corridor=%s confidence=%.3f",
                incident_id,
                corridor_key,
                confidence,
            )
            return incident_id

        else:
            # --- UPDATE ---
            incident_id = state.incident_id
            try:
                await _update_incident_in_db(incident_id, state, session)
            except Exception as exc:
                logger.error(
                    "Failed to update incident %s: %s", incident_id, exc
                )
                return incident_id

            await _store_incident_event(incident_id, event, session)
            await _cache_snapshot(incident_id, state)
            await _publish_state_update(
                incident_id, "updated", state, event, kafka_producer
            )

            logger.debug(
                "Incident UPDATED id=%s confidence=%.3f", incident_id, confidence
            )
            return incident_id

    # ------------------------------------------------------------------
    # Path B: Below threshold — check for resolution
    # ------------------------------------------------------------------
    if state.incident_id is not None and scorer.should_resolve():
        incident_id = state.incident_id
        try:
            await _resolve_incident_in_db(incident_id, session)
        except Exception as exc:
            logger.error(
                "Failed to resolve incident %s: %s", incident_id, exc
            )
            return None

        await _publish_state_update(
            incident_id, "resolved", state, event, kafka_producer
        )
        scorer.set_incident_id(None)

        logger.info(
            "Incident RESOLVED id=%s corridor=%s (confidence=%.3f dropped below all-clear)",
            incident_id,
            corridor_key,
            confidence,
        )
        return None

    # Below threshold, no active incident or not yet resolved — monitoring only
    return state.incident_id
