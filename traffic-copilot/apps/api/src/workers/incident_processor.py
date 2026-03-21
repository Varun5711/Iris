"""
Consumes from traffic.events.raw.
For each message:
1. Deserialize to TrafficEvent
2. Check deduplication (Redis)
3. Normalize via ingest/normalizer
4. Run detector/rules.score_event()
5. Run detector/lifecycle.handle_detection()
6. If incident active: run state_engine pipeline (map_match, queue_estimate, corridor)
7. Update Redis hot cache
8. Produce IncidentSnapshot to incident.state.updated
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from src.core.logging import get_logger

logger = get_logger(__name__)


async def _handle_message(payload: dict[str, Any], topic: str) -> None:
    """Process a single traffic.events.raw message end-to-end."""
    from src.core.config import settings
    from src.db.session import AsyncSessionLocal
    from src.integrations.kafka.producer import publish
    from src.integrations.kafka.topics import INCIDENT_STATE_UPDATED
    from src.integrations.redis.client import (
        cache_set,
        get_redis,
        incident_snapshot_key,
    )
    from src.modules.detector.rules import score_event
    from src.modules.ingest.normalizer import normalize_event
    from src.modules.state_engine.deduper import is_duplicate

    # ------------------------------------------------------------------ #
    # 1. Basic validation                                                  #
    # ------------------------------------------------------------------ #
    source = payload.get("source")
    if not source:
        logger.warning("incident_processor: missing 'source' field, skipping", payload_keys=list(payload.keys()))
        return

    event_id = str(payload.get("event_id", ""))

    # ------------------------------------------------------------------ #
    # 2. Deduplication                                                     #
    # ------------------------------------------------------------------ #
    redis_client = await get_redis()
    if event_id and await is_duplicate(event_id, redis_client):
        logger.debug("incident_processor: duplicate event, skipping", event_id=event_id)
        return

    # ------------------------------------------------------------------ #
    # 3. Normalize                                                         #
    # ------------------------------------------------------------------ #
    try:
        event = normalize_event(source, payload)
    except (ValueError, KeyError) as exc:
        logger.error(
            "incident_processor: normalization failed",
            source=source,
            error=str(exc),
            exc_info=True,
        )
        return

    # ------------------------------------------------------------------ #
    # 4. Score via detector rules                                          #
    # ------------------------------------------------------------------ #
    try:
        detection_score = score_event(event)
    except TypeError as exc:
        logger.error("incident_processor: scoring failed", error=str(exc))
        return

    logger.debug(
        "incident_processor: scored event",
        event_id=str(event.event_id),
        source=source,
        score=detection_score,
    )

    threshold = settings.detection_confidence_threshold

    # ------------------------------------------------------------------ #
    # 5. Lifecycle — create/update incident in DB                          #
    # ------------------------------------------------------------------ #
    async with AsyncSessionLocal() as session:
        incident_id, incident_status = await _handle_detection(
            event=event,
            detection_score=detection_score,
            threshold=threshold,
            session=session,
        )

        if incident_id is None:
            # Score too low — no incident to process.
            return

        # ------------------------------------------------------------------ #
        # 6. State engine pipeline (only when score meets threshold)           #
        # ------------------------------------------------------------------ #
        corridor_segments: list[dict] = []
        queue_data: dict = {}

        if detection_score >= threshold and event.lat is not None and event.lon is not None:
            corridor_segments, queue_data = await _run_state_engine(
                event=event,
                incident_id=incident_id,
                session=session,
            )

        # ------------------------------------------------------------------ #
        # 7. Build snapshot and update Redis hot cache                         #
        # ------------------------------------------------------------------ #
        snapshot = _build_snapshot(
            incident_id=incident_id,
            incident_status=incident_status,
            event=event,
            detection_score=detection_score,
            corridor_segments=corridor_segments,
            queue_data=queue_data,
        )

        await cache_set(
            incident_snapshot_key(incident_id),
            snapshot,
            ttl_seconds=300,
        )

        # ------------------------------------------------------------------ #
        # 8. Publish to incident.state.updated                                 #
        # ------------------------------------------------------------------ #
        await publish(INCIDENT_STATE_UPDATED, snapshot, key=incident_id)
        logger.info(
            "incident_processor: published snapshot",
            incident_id=incident_id,
            status=incident_status,
            score=detection_score,
        )


async def _handle_detection(
    event,
    detection_score: float,
    threshold: float,
    session,
) -> tuple[str | None, str]:
    """
    Create or update an incident record in Postgres based on detection score.

    Returns (incident_id, status) or (None, "") when score is below threshold
    and no existing incident correlates with this event.
    """
    from sqlalchemy import text

    # Manual events always create/update incidents regardless of score.
    is_manual = event.source == "manual"

    if detection_score < threshold and not is_manual:
        return None, ""

    corridor_id = event.corridor_id
    lat = event.lat
    lon = event.lon

    # Determine severity from event type.
    severity = "medium"
    description = f"Auto-detected incident (source={event.source}, score={detection_score:.2f})"
    reporter_id = event.source

    if event.source == "manual":
        severity = getattr(event, "severity", "medium")
        description = getattr(event, "description", description)
        reporter_id = getattr(event, "reporter_id", "manual")

    incident_id = str(uuid4())
    now = datetime.now(tz=timezone.utc)

    # Upsert: look for an active/monitoring incident for the same corridor.
    existing_id = None
    if corridor_id:
        row = await session.execute(
            text(
                """
                SELECT id FROM incidents
                WHERE corridor_id = :corridor_id
                  AND status IN ('active', 'monitoring')
                ORDER BY created_at DESC
                LIMIT 1
                """
            ),
            {"corridor_id": corridor_id},
        )
        existing = row.fetchone()
        if existing:
            existing_id = str(existing[0])

    if existing_id:
        # Update existing incident.
        await session.execute(
            text(
                """
                UPDATE incidents
                SET detection_confidence = GREATEST(detection_confidence, :score),
                    updated_at = :now
                WHERE id = :id
                """
            ),
            {"score": detection_score, "now": now, "id": existing_id},
        )
        await session.commit()
        return existing_id, "active"

    # Create new incident.
    location_expr = "NULL"
    location_params: dict = {}
    if lat is not None and lon is not None:
        location_expr = "ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)"
        location_params = {"lat": lat, "lon": lon}

    await session.execute(
        text(
            f"""
            INSERT INTO incidents
                (id, status, severity, description, corridor_id, reporter_id,
                 detection_confidence, location, created_at, updated_at)
            VALUES
                (:id, 'active', :severity, :description, :corridor_id,
                 :reporter_id, :score, {location_expr}, :now, :now)
            """
        ),
        {
            "id": incident_id,
            "severity": severity,
            "description": description,
            "corridor_id": corridor_id,
            "reporter_id": reporter_id,
            "score": detection_score,
            "now": now,
            **location_params,
        },
    )

    # Link the raw event to this incident.
    await session.execute(
        text(
            """
            INSERT INTO incident_events (incident_id, event_id, source, event_time, payload)
            VALUES (:incident_id, :event_id, :source, :event_time, :payload::jsonb)
            ON CONFLICT DO NOTHING
            """
        ),
        {
            "incident_id": incident_id,
            "event_id": str(event.event_id),
            "source": event.source,
            "event_time": event.event_time,
            "payload": json.dumps(event.payload, default=str),
        },
    )
    await session.commit()

    logger.info(
        "incident_processor: created incident",
        incident_id=incident_id,
        severity=severity,
        score=detection_score,
    )
    return incident_id, "active"


async def _run_state_engine(event, incident_id: str, session) -> tuple[list[dict], dict]:
    """Run map matching, queue estimation, and corridor analysis."""
    from src.integrations.osm.loader import get_graph
    from src.modules.state_engine.corridor import compute_affected_corridor
    from src.modules.state_engine.map_matcher import snap_to_segment
    from src.modules.state_engine.queue_estimator import estimate_delay

    corridor_segments: list[dict] = []
    queue_data: dict = {}

    try:
        graph = await get_graph()
    except RuntimeError:
        logger.debug("incident_processor: OSM graph not loaded, skipping state engine")
        return corridor_segments, queue_data

    # Map match to nearest road segment.
    try:
        snap = await snap_to_segment(event.lat, event.lon, graph)
        logger.debug(
            "incident_processor: map matched",
            incident_id=incident_id,
            osm_way_id=snap["osm_way_id"],
            distance_m=snap["distance_m"],
        )
    except Exception as exc:
        logger.warning("incident_processor: map matching failed", error=str(exc))
        return corridor_segments, queue_data

    # Queue estimation (sensor events have speed data).
    if event.source == "sensor":
        try:
            speed_kmh = getattr(event, "speed_kmh", 0.0)
            free_flow_kmh = getattr(event, "free_flow_kmh", 50.0)
            queue_data = estimate_delay(speed_kmh, free_flow_kmh)
            logger.debug(
                "incident_processor: queue estimated",
                incident_id=incident_id,
                congestion_pct=queue_data.get("congestion_pct"),
                delay_seconds=queue_data.get("delay_seconds"),
            )
        except Exception as exc:
            logger.warning("incident_processor: queue estimation failed", error=str(exc))

    # Corridor analysis using the origin node from the snap result.
    origin_node = snap.get("osm_node_u")
    if origin_node:
        try:
            corridor_segments = await compute_affected_corridor(
                origin_node=int(origin_node),
                graph=graph,
                radius_nodes=5,
                incident_id=incident_id,
                session=session,
            )
        except Exception as exc:
            logger.warning("incident_processor: corridor analysis failed", error=str(exc))

    return corridor_segments, queue_data


def _build_snapshot(
    incident_id: str,
    incident_status: str,
    event,
    detection_score: float,
    corridor_segments: list[dict],
    queue_data: dict,
) -> dict:
    """Build the IncidentSnapshot payload for Kafka and Redis."""
    now = datetime.now(tz=timezone.utc).isoformat()

    affected_segments = [
        {
            "osm_way_id": seg.get("osm_way_id", 0),
            "delay_seconds": seg.get("delay_seconds", 0),
            "congestion_pct": seg.get("congestion_pct", 0.0),
        }
        for seg in corridor_segments
    ]

    return {
        "incident": {
            "id": incident_id,
            "status": incident_status,
            "severity": getattr(event, "severity", "medium") if event.source == "manual" else "medium",
            "description": (
                getattr(event, "description", None)
                if event.source == "manual"
                else f"Auto-detected incident (source={event.source})"
            ),
            "location_lat": event.lat,
            "location_lon": event.lon,
            "corridor_id": event.corridor_id,
            "reporter_id": getattr(event, "reporter_id", event.source),
            "created_at": now,
            "updated_at": now,
            "detection_confidence": detection_score,
        },
        "affected_segments": affected_segments,
        "event_count": 1,
        "last_updated": now,
        "queue_data": queue_data,
    }


async def run_incident_processor() -> None:
    """Main consumer loop. Runs forever."""
    from src.core.config import settings
    from src.integrations.kafka.consumer import create_consumer, consume_messages
    from src.integrations.kafka.topics import TRAFFIC_EVENTS_RAW

    logger.info("incident_processor starting up")

    consumer = await create_consumer(
        topics=[TRAFFIC_EVENTS_RAW],
        group_id=f"{settings.kafka_consumer_group_id}-incident-processor",
        bootstrap_servers=settings.kafka_bootstrap_servers,
        auto_offset_reset="latest",
    )

    await consume_messages(consumer, _handle_message)
    logger.info("incident_processor shut down")
