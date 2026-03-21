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

from fastapi import APIRouter, Depends, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.logging import get_logger
from src.db.session import get_db
from src.schemas.event import ManualIncidentEvent
from src.schemas.incident import IncidentCreate, IncidentOut, IncidentSnapshot, SegmentOut, VisionAnalysisOut

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
                INSERT INTO audit_log (id, event_type, actor, payload, created_at)
                VALUES (:id, :event_type, :actor, CAST(:payload AS jsonb), :now)
                """
            ),
            {
                "id": str(uuid4()),
                "event_type": action,
                "actor": officer_id,
                "payload": json.dumps({"incident_id": incident_id, **details}, default=str),
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
                     :reporter_id, :detection_confidence, {location_expr}, :now, :now)
                """
            ),
            {
                "id": incident_id,
                "severity": body.severity,
                "description": body.description,
                "corridor_id": body.corridor_id,
                "reporter_id": reporter_id,
                "detection_confidence": body.detection_confidence if body.detection_confidence is not None else 0.9,
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
# POST /incidents/{incident_id}/vision
# ---------------------------------------------------------------------------


@router.post("/{incident_id}/vision", response_model=VisionAnalysisOut, status_code=status.HTTP_200_OK)
async def analyse_incident_image(
    incident_id: UUID,
    image: UploadFile,
    officer_id: str = Form(..., description="Badge number or user ID of the uploading officer"),
    db: AsyncSession = Depends(get_db),
) -> VisionAnalysisOut:
    """
    Accept a JPEG/PNG image upload and classify it via the HuggingFace CLIP model.

    If the model detects an incident (confidence >= threshold), a CameraMetaEvent
    is published to Kafka for downstream incident processing.
    """
    from src.integrations.huggingface.vision import analyze_image
    from src.integrations.kafka.producer import publish
    from src.integrations.kafka.topics import TRAFFIC_EVENTS_RAW
    from src.schemas.event import CameraMetaEvent
    from src.integrations.redis.client import cache_set, vision_analysis_key
    from datetime import datetime, timezone
    from uuid import uuid4

    iid = str(incident_id)

    # Verify incident exists.
    chk = await db.execute(text("SELECT id FROM incidents WHERE id = :id"), {"id": iid})
    if chk.fetchone() is None:
        raise HTTPException(status_code=404, detail=f"Incident {incident_id} not found")

    image_bytes = await image.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Uploaded image is empty")

    result = await analyze_image(image_bytes, filename=image.filename or "upload")

    # ------------------------------------------------------------------ #
    # Always cache vision result in Redis so the context builder and LLM  #
    # can incorporate the vision confidence into overall_confidence,       #
    # regardless of whether the detection threshold was crossed.           #
    # ------------------------------------------------------------------ #
    try:
        from datetime import datetime, timezone as tz
        await cache_set(
            vision_analysis_key(iid),
            {
                "incident_id": iid,
                "confidence": result["confidence"],
                "incident_detected": result["incident_detected"],
                "top_label": result["top_label"],
                "scores": result["scores"],
                "model": result.get("model", ""),
                "source": result.get("source", ""),
                "officer_id": officer_id,
                "analysed_at": datetime.now(tz=timezone.utc).isoformat(),
            },
            ttl_seconds=86400,  # 24 h
        )
        logger.info("incidents: vision result cached in Redis", incident_id=iid, confidence=result["confidence"])
    except Exception as exc:
        logger.warning("incidents: vision Redis cache failed (non-fatal)", error=str(exc))

    kafka_published = False
    if result["incident_detected"]:
        try:
            camera_event = CameraMetaEvent(
                event_id=uuid4(),
                source="camera",
                event_time=datetime.now(tz=timezone.utc),
                camera_id=f"vision_upload_{officer_id}",
                lane_blocked=True,
                vehicle_count=0,
                incident_detected=True,
                confidence=result["confidence"],
                payload={
                    "incident_id": iid,
                    "top_label": result["top_label"],
                    "scores": result["scores"],
                    "officer_id": officer_id,
                    "filename": image.filename,
                },
            )
            await publish(TRAFFIC_EVENTS_RAW, camera_event.model_dump(mode="json"), key=iid)
            kafka_published = True
            logger.info(
                "incidents: vision CameraMetaEvent published",
                incident_id=iid,
                top_label=result["top_label"],
                confidence=result["confidence"],
            )
        except Exception as exc:
            logger.warning("incidents: vision Kafka publish failed (non-fatal)", error=str(exc))

    await _audit(db, iid, "VISION_ANALYSIS", officer_id, {
        "top_label": result["top_label"],
        "confidence": result["confidence"],
        "incident_detected": result["incident_detected"],
    })
    await db.commit()

    return VisionAnalysisOut(
        incident_id=incident_id,
        incident_detected=result["incident_detected"],
        confidence=result["confidence"],
        top_label=result["top_label"],
        scores=result["scores"],
        model=result["model"],
        source=result["source"],
        kafka_published=kafka_published,
    )


# ---------------------------------------------------------------------------
# GET /incidents/{incident_id}/map-data
# ---------------------------------------------------------------------------


@router.get("/{incident_id}/map-data", status_code=status.HTTP_200_OK)
async def get_map_data(
    incident_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Return a GeoJSON FeatureCollection for frontend map rendering.

    Features returned:
      - incident_point     : Point marker at the incident location
      - affected_route     : LineString of blocked road segments (from OSM graph)
      - diversion_route    : LineString of the recommended diversion (OSM graph or LLM waypoints)
      - signal_actions     : Point features for each suggested signal intersection
      - nearby_intersections: Point features for intersections near the incident

    The frontend can directly pass this to Leaflet / Mapbox as a GeoJSON layer.
    """
    iid = str(incident_id)

    # ---- Verify incident exists and fetch core data -------------------------
    row = await db.execute(
        text(
            """
            SELECT id::text, status, severity, corridor_id, description,
                   ST_Y(location) AS location_lat,
                   ST_X(location) AS location_lon,
                   detection_confidence
            FROM incidents WHERE id = CAST(:iid AS uuid)
            """
        ),
        {"iid": iid},
    )
    inc = row.mappings().first()
    if inc is None:
        raise HTTPException(status_code=404, detail=f"Incident {incident_id} not found")
    inc = dict(inc)

    # ---- Fetch affected segments (have osm_node_u/v) ------------------------
    seg_rows = await db.execute(
        text(
            """
            SELECT osm_way_id, osm_node_u, osm_node_v, road_name,
                   delay_seconds, congestion_pct
            FROM affected_segments
            WHERE incident_id = CAST(:iid AS uuid)
            ORDER BY congestion_pct DESC
            """
        ),
        {"iid": iid},
    )
    segments = [dict(r) for r in seg_rows.mappings().all()]

    # ---- Fetch latest composite recommendation for diversion plan -----------
    rec_row = await db.execute(
        text(
            """
            SELECT copilot_response
            FROM recommendations
            WHERE incident_id = CAST(:iid AS uuid)
              AND rec_type = 'composite'
              AND copilot_response IS NOT NULL
            ORDER BY created_at DESC
            LIMIT 1
            """
        ),
        {"iid": iid},
    )
    rec = rec_row.mappings().first()
    diversion_plan = None
    signal_actions: list[dict] = []
    if rec:
        try:
            cr = rec["copilot_response"]
            if isinstance(cr, str):
                import json as _json
                cr = _json.loads(cr)
            diversion_plan = cr.get("diversion_plan")
            signal_actions = cr.get("signal_actions") or []
        except Exception:
            pass

    # ---- Load OSM graph (may be None in dev) --------------------------------
    try:
        from src.modules.routing.graph import get_graph, get_node_nearest
        graph = get_graph()
    except Exception:
        graph = None

    features: list[dict] = []

    # ---- 1. Incident point --------------------------------------------------
    inc_lat = inc.get("location_lat")
    inc_lon = inc.get("location_lon")
    if inc_lat and inc_lon:
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [inc_lon, inc_lat]},
            "properties": {
                "feature_type": "incident_point",
                "incident_id": iid,
                "severity": inc.get("severity"),
                "status": inc.get("status"),
                "corridor_id": inc.get("corridor_id"),
                "description": inc.get("description"),
                "detection_confidence": inc.get("detection_confidence"),
                "marker_color": "#ff3333",
                "marker_icon": "warning",
            },
        })

    # ---- 2. Affected route (blocked segments as LineStrings) ----------------
    if segments and graph is not None:
        for seg in segments:
            u_id = seg.get("osm_node_u")
            v_id = seg.get("osm_node_v")
            if not u_id or not v_id:
                continue
            try:
                u_data = graph.nodes.get(int(u_id), {})
                v_data = graph.nodes.get(int(v_id), {})
                if u_data and v_data:
                    features.append({
                        "type": "Feature",
                        "geometry": {
                            "type": "LineString",
                            "coordinates": [
                                [float(u_data.get("x", 0)), float(u_data.get("y", 0))],
                                [float(v_data.get("x", 0)), float(v_data.get("y", 0))],
                            ],
                        },
                        "properties": {
                            "feature_type": "affected_segment",
                            "osm_way_id": seg.get("osm_way_id"),
                            "road_name": seg.get("road_name"),
                            "delay_seconds": seg.get("delay_seconds"),
                            "congestion_pct": seg.get("congestion_pct"),
                            "stroke_color": "#ff6600",
                            "stroke_width": 5,
                        },
                    })
            except Exception:
                pass
    elif segments:
        # Graph unavailable — emit placeholder feature with segment metadata only
        for seg in segments:
            features.append({
                "type": "Feature",
                "geometry": None,
                "properties": {
                    "feature_type": "affected_segment",
                    "osm_way_id": seg.get("osm_way_id"),
                    "road_name": seg.get("road_name"),
                    "note": "geometry unavailable (graph not loaded)",
                },
            })

    # ---- 3. Diversion route -------------------------------------------------
    diversion_added = False

    # 3a. Try to compute real route via OSM graph (blocked edges = affected segs)
    if graph is not None and segments and inc_lat and inc_lon:
        try:
            from src.modules.routing.diversion import compute_diversion_routes

            blocked_edges = [
                (int(s["osm_node_u"]), int(s["osm_node_v"]))
                for s in segments
                if s.get("osm_node_u") and s.get("osm_node_v")
            ]
            origin_node = await get_node_nearest(inc_lat, inc_lon, graph)
            # Use the last affected segment's v-node as destination
            dest_node = int(segments[-1]["osm_node_v"]) if segments else 0

            if origin_node and dest_node and origin_node != dest_node:
                routes = await compute_diversion_routes(
                    origin_node=origin_node,
                    destination_node=dest_node,
                    graph=graph,
                    blocked_edges=blocked_edges,
                    k=1,
                )
                if routes:
                    r = routes[0]
                    features.append({
                        "type": "Feature",
                        "geometry": r["route_geojson"],
                        "properties": {
                            "feature_type": "diversion_route",
                            "source": "osm_graph",
                            "road_names": r["road_names"],
                            "distance_m": r["distance_m"],
                            "estimated_minutes": r["estimated_minutes"],
                            "description": diversion_plan.get("route_description", "") if diversion_plan else "",
                            "stroke_color": "#3399ff",
                            "stroke_width": 4,
                            "stroke_dash": "8,4",
                        },
                    })
                    diversion_added = True
        except Exception as exc:
            logger.warning("map-data: diversion route compute failed (non-fatal)", error=str(exc))

    # 3b. Fall back to LLM waypoints if OSM routing failed/unavailable
    if not diversion_added and diversion_plan:
        waypoints = diversion_plan.get("waypoints") or []
        if len(waypoints) >= 2:
            coords = [[wp["lng"], wp["lat"]] for wp in waypoints if wp.get("lat") and wp.get("lng")]
            if len(coords) >= 2:
                features.append({
                    "type": "Feature",
                    "geometry": {"type": "LineString", "coordinates": coords},
                    "properties": {
                        "feature_type": "diversion_route",
                        "source": "llm_waypoints",
                        "description": diversion_plan.get("route_description", ""),
                        "estimated_extra_minutes": diversion_plan.get("estimated_extra_minutes"),
                        "traffic_redistribution_pct": diversion_plan.get("traffic_redistribution_pct"),
                        "confidence": diversion_plan.get("confidence"),
                        "waypoint_names": [wp.get("name") for wp in waypoints],
                        "stroke_color": "#3399ff",
                        "stroke_width": 4,
                        "stroke_dash": "8,4",
                    },
                })

    # ---- 4. Signal action points -------------------------------------------
    if graph is not None and signal_actions and inc_lat and inc_lon:
        try:
            from src.modules.state_engine.corridor import get_nearby_intersections
            origin_node_for_ix = await get_node_nearest(inc_lat, inc_lon, graph)
            if origin_node_for_ix:
                intersections = await get_nearby_intersections(
                    origin_node_for_ix, graph, count=max(len(signal_actions), 3)
                )
                for i, sa in enumerate(signal_actions):
                    if i < len(intersections):
                        ix = intersections[i]
                        features.append({
                            "type": "Feature",
                            "geometry": {"type": "Point", "coordinates": [ix["lon"], ix["lat"]]},
                            "properties": {
                                "feature_type": "signal_action",
                                "intersection_id": sa.get("intersection_id"),
                                "action": sa.get("action"),
                                "expected_impact": sa.get("expected_impact"),
                                "confidence": sa.get("confidence"),
                                "road_names": ix.get("road_names", []),
                                "osm_node_id": ix.get("node_id"),
                                "marker_color": "#ffdd00",
                                "marker_icon": "traffic-light",
                            },
                        })
        except Exception as exc:
            logger.warning("map-data: signal action points failed (non-fatal)", error=str(exc))

    # ---- Assemble FeatureCollection ----------------------------------------
    payload = {
        "type": "FeatureCollection",
        "incident_id": iid,
        "corridor_id": inc.get("corridor_id"),
        "severity": inc.get("severity"),
        "status": inc.get("status"),
        "graph_loaded": graph is not None,
        "features": features,
        "meta": {
            "incident_point": inc_lat is not None and inc_lon is not None,
            "affected_segments_count": len(segments),
            "diversion_source": (
                "osm_graph" if diversion_added
                else ("llm_waypoints" if (diversion_plan and diversion_plan.get("waypoints")) else "none")
            ),
            "signal_actions_count": len(signal_actions),
        },
    }
    # Use custom serializer to handle numpy int64 / other non-JSON-native types
    import json as _json
    return JSONResponse(content=_json.loads(_json.dumps(payload, default=str)))


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
