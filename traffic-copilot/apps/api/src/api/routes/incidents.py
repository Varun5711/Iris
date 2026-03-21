"""
Incident CRUD endpoints.

POST   /incidents/                      Create a new incident manually
GET    /incidents/{incident_id}         Get a full IncidentSnapshot
POST   /incidents/{incident_id}/events  Append a raw event to an existing incident
GET    /incidents/                      List incidents filtered by status
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.logging import get_logger
from src.db.session import get_db
from src.schemas.event import ManualIncidentEvent
from src.schemas.incident import IncidentCreate, IncidentOut, IncidentSnapshot, SegmentOut

logger = get_logger(__name__)

router = APIRouter(prefix="/incidents", tags=["incidents"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _audit(
    session: AsyncSession,
    incident_id: str,
    action: str,
    officer_id: str,
    details: dict,
) -> None:
    """Write a single row to audit_log. Non-fatal on error."""
    try:
        await session.execute(
            text(
                """
                INSERT INTO audit_log (id, incident_id, action, officer_id, details, created_at)
                VALUES (:id, :incident_id, :action, :officer_id, :details::jsonb, :now)
                """
            ),
            {
                "id": str(uuid4()),
                "incident_id": incident_id,
                "action": action,
                "officer_id": officer_id,
                "details": json.dumps(details, default=str),
                "now": datetime.now(tz=timezone.utc),
            },
        )
    except Exception as exc:
        logger.warning("incidents: audit log write failed", error=str(exc))


def _row_to_incident_out(row: Any) -> IncidentOut:
    """Convert a DB row (mapping) to IncidentOut."""
    return IncidentOut(
        id=row["id"],
        status=row["status"],
        severity=row["severity"],
        description=row.get("description"),
        location_lat=row.get("location_lat"),
        location_lon=row.get("location_lon"),
        corridor_id=row.get("corridor_id"),
        reporter_id=row.get("reporter_id"),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        detection_confidence=row.get("detection_confidence"),
    )


# ---------------------------------------------------------------------------
# POST /incidents/
# ---------------------------------------------------------------------------


@router.post("/", response_model=IncidentOut, status_code=status.HTTP_201_CREATED)
async def create_incident(
    body: IncidentCreate,
    db: AsyncSession = Depends(get_db),
) -> IncidentOut:
    """
    1. Insert incident into DB with PostGIS location
    2. Normalize to ManualIncidentEvent
    3. Publish to Kafka traffic.events.raw
    4. Log to audit_log (INCIDENT_CREATED)
    5. Return IncidentOut
    """
    from src.integrations.kafka.producer import publish
    from src.integrations.kafka.topics import TRAFFIC_EVENTS_RAW

    incident_id = str(uuid4())
    now = datetime.now(tz=timezone.utc)
    reporter_id = body.reporter_id or "manual"

    # Build the PostGIS point expression conditionally.
    if body.lat is not None and body.lon is not None:
        location_expr = "ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)"
        geo_params: dict[str, Any] = {"lat": body.lat, "lon": body.lon}
    else:
        location_expr = "NULL"
        geo_params = {}

    try:
        await db.execute(
            text(
                f"""
                INSERT INTO incidents
                    (id, status, severity, description, corridor_id, reporter_id,
                     detection_confidence, location, created_at, updated_at)
                VALUES
                    (:id, 'active', :severity, :description, :corridor_id,
                     :reporter_id, NULL, {location_expr}, :now, :now)
                """
            ),
            {
                "id": incident_id,
                "severity": body.severity,
                "description": body.description,
                "corridor_id": body.corridor_id,
                "reporter_id": reporter_id,
                "now": now,
                **geo_params,
            },
        )
    except Exception as exc:
        await db.rollback()
        logger.error("incidents: DB insert failed", error=str(exc), exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to create incident") from exc

    # Audit log (within the same transaction).
    await _audit(db, incident_id, "INCIDENT_CREATED", reporter_id, {"severity": body.severity})
    await db.commit()

    # Normalize and publish to Kafka (best effort — do not fail the HTTP request).
    event = ManualIncidentEvent(
        event_id=uuid4(),
        source="manual",
        event_time=now,
        corridor_id=body.corridor_id,
        lat=body.lat,
        lon=body.lon,
        severity=body.severity,
        description=body.description,
        reporter_id=reporter_id,
        payload={
            "incident_id": incident_id,
            "severity": body.severity,
            "description": body.description,
            "corridor_id": body.corridor_id,
        },
    )
    try:
        await publish(TRAFFIC_EVENTS_RAW, event.model_dump(mode="json"), key=incident_id)
    except Exception as exc:
        logger.warning("incidents: Kafka publish failed (non-fatal)", error=str(exc))

    # Build response — fetch back from DB to get exact timestamps.
    row = await db.execute(
        text(
            """
            SELECT id, status, severity, description, corridor_id, reporter_id,
                   detection_confidence, created_at, updated_at,
                   ST_Y(location::geometry) AS location_lat,
                   ST_X(location::geometry) AS location_lon
            FROM incidents WHERE id = :id
            """
        ),
        {"id": incident_id},
    )
    result = row.mappings().fetchone()
    if result is None:
        raise HTTPException(status_code=500, detail="Incident created but could not be retrieved")

    logger.info("incidents: created", incident_id=incident_id, severity=body.severity)
    return _row_to_incident_out(result)


# ---------------------------------------------------------------------------
# GET /incidents/{incident_id}
# ---------------------------------------------------------------------------


@router.get("/{incident_id}", response_model=IncidentSnapshot)
async def get_incident(
    incident_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> IncidentSnapshot:
    """Return incident + affected_segments + event_count from DB."""
    iid = str(incident_id)

    incident_row = await db.execute(
        text(
            """
            SELECT id, status, severity, description, corridor_id, reporter_id,
                   detection_confidence, created_at, updated_at,
                   ST_Y(location::geometry) AS location_lat,
                   ST_X(location::geometry) AS location_lon
            FROM incidents WHERE id = :id
            """
        ),
        {"id": iid},
    )
    row = incident_row.mappings().fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Incident {incident_id} not found")

    incident_out = _row_to_incident_out(row)

    # Affected segments.
    seg_result = await db.execute(
        text(
            """
            SELECT osm_way_id, delay_seconds, congestion_pct
            FROM affected_segments WHERE incident_id = :id
            """
        ),
        {"id": iid},
    )
    segments = [
        SegmentOut(
            osm_way_id=s["osm_way_id"],
            delay_seconds=s["delay_seconds"],
            congestion_pct=float(s["congestion_pct"]),
        )
        for s in seg_result.mappings().fetchall()
    ]

    # Event count.
    count_result = await db.execute(
        text("SELECT COUNT(*) FROM incident_events WHERE incident_id = :id"),
        {"id": iid},
    )
    event_count = count_result.scalar() or 0

    last_updated = row["updated_at"] or row["created_at"]

    return IncidentSnapshot(
        incident=incident_out,
        affected_segments=segments,
        event_count=event_count,
        last_updated=last_updated,
    )


# ---------------------------------------------------------------------------
# POST /incidents/{incident_id}/events
# ---------------------------------------------------------------------------


@router.post("/{incident_id}/events", status_code=status.HTTP_202_ACCEPTED)
async def add_event(
    incident_id: UUID,
    source: str = Query(..., description="Event source: sensor|camera|radio|manual"),
    body: dict = None,  # type: ignore[assignment]
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Validate source, normalize event, publish to traffic.events.raw."""
    from fastapi import Body
    from src.integrations.kafka.producer import publish
    from src.integrations.kafka.topics import TRAFFIC_EVENTS_RAW
    from src.modules.ingest.normalizer import normalize_event

    iid = str(incident_id)

    valid_sources = {"sensor", "camera", "radio", "manual"}
    if source not in valid_sources:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid source '{source}'. Must be one of {sorted(valid_sources)}",
        )

    # Verify the incident exists.
    chk = await db.execute(text("SELECT id FROM incidents WHERE id = :id"), {"id": iid})
    if chk.fetchone() is None:
        raise HTTPException(status_code=404, detail=f"Incident {incident_id} not found")

    payload = body or {}
    payload.setdefault("source", source)
    payload.setdefault("incident_id", iid)

    # Normalize (raises ValueError/KeyError on bad payload).
    try:
        event = normalize_event(source, payload)
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=422, detail=f"Event normalization failed: {exc}") from exc

    event_dict = event.model_dump(mode="json")

    try:
        await publish(TRAFFIC_EVENTS_RAW, event_dict, key=iid)
    except Exception as exc:
        logger.error("incidents: Kafka publish failed", error=str(exc), exc_info=True)
        raise HTTPException(status_code=503, detail="Failed to publish event to stream") from exc

    logger.info("incidents: event appended", incident_id=iid, source=source)
    return {"status": "accepted", "incident_id": iid, "event_id": str(event.event_id)}


# ---------------------------------------------------------------------------
# GET /incidents/
# ---------------------------------------------------------------------------


@router.get("/", response_model=list[IncidentOut])
async def list_incidents(
    incident_status: str = Query(
        default="active",
        alias="status",
        description="Filter by status: active|monitoring|resolved|false_alarm",
    ),
    limit: int = Query(default=20, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> list[IncidentOut]:
    """List incidents filtered by status."""
    valid_statuses = {"active", "monitoring", "resolved", "false_alarm"}
    if incident_status not in valid_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status '{incident_status}'. Must be one of {sorted(valid_statuses)}",
        )

    result = await db.execute(
        text(
            """
            SELECT id, status, severity, description, corridor_id, reporter_id,
                   detection_confidence, created_at, updated_at,
                   ST_Y(location::geometry) AS location_lat,
                   ST_X(location::geometry) AS location_lon
            FROM incidents
            WHERE status = :status
            ORDER BY created_at DESC
            LIMIT :limit
            """
        ),
        {"status": incident_status, "limit": limit},
    )
    rows = result.mappings().fetchall()
    return [_row_to_incident_out(row) for row in rows]
