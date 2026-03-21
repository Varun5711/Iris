"""
Incident CRUD endpoints.

POST   /incidents/                      Create a new incident manually
POST   /incidents/voice-report          Transcribe audio via AssemblyAI, parse with Groq, create incident
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
from src.schemas.incident import BulkVisionAnalysisOut, IncidentCreate, IncidentOut, IncidentSnapshot, SegmentOut, VisionAnalysisOut

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
# POST /incidents/voice-report
# ---------------------------------------------------------------------------
# Flow:
#   1. Accept audio file upload OR public audio_url
#   2. Upload to AssemblyAI and poll until transcript is ready
#   3. Send transcript to Groq → extract severity, location, corridor_id, lat/lon
#   4. Insert incident into DB + publish to Kafka (same as manual create)
#   5. Return IncidentOut + transcript + parsed fields
# ---------------------------------------------------------------------------

_ASSEMBLYAI_BASE = "https://api.assemblyai.com"
_ASSEMBLYAI_API_KEY = "16c351d64a87482c870b4f49068844d7"

_GROQ_PARSE_SYSTEM = """You are a traffic incident parser.
Given a radio/voice transcript from a traffic officer, extract incident details.
Respond ONLY with a valid JSON object — no explanation, no markdown.
Required fields:
  severity: one of "low", "medium", "high", "critical"
  description: concise incident description (max 200 chars)
  corridor_id: best-guess corridor ID (e.g. AMD-CGR-01 for CG Road Ahmedabad, AMD-SGH-01 for SG Highway, AMD-ASH-01 for Ashram Road, AMD-NHW-08 for NH-48 Narol, AMD-DIN-01 for Drive-In Road, AMD-SPRR-01 for SP Ring Road, or UNKNOWN if unclear)
  lat: decimal latitude (null if not mentioned)
  lon: decimal longitude (null if not mentioned)
  location_name: plain text location name extracted from transcript
"""


async def _assemblyai_transcribe(audio_bytes: bytes | None, audio_url: str | None) -> str:
    """Upload audio to AssemblyAI (if bytes) or use URL directly, poll until done, return transcript text."""
    import asyncio
    import httpx

    headers = {"authorization": _ASSEMBLYAI_API_KEY}

    async with httpx.AsyncClient(timeout=60.0) as client:
        # Step 1: upload file if bytes provided
        if audio_bytes is not None:
            upload_resp = await client.post(
                f"{_ASSEMBLYAI_BASE}/v2/upload",
                headers=headers,
                content=audio_bytes,
            )
            upload_resp.raise_for_status()
            audio_url = upload_resp.json()["upload_url"]

        if not audio_url:
            raise ValueError("No audio source provided")

        # Step 2: submit transcription job
        submit_resp = await client.post(
            f"{_ASSEMBLYAI_BASE}/v2/transcript",
            headers=headers,
            json={
                "audio_url": audio_url,
                "language_detection": True,
                "speech_models": ["universal-3-pro", "universal-2"],
            },
        )
        submit_resp.raise_for_status()
        transcript_id = submit_resp.json()["id"]
        polling_url = f"{_ASSEMBLYAI_BASE}/v2/transcript/{transcript_id}"

        # Step 3: poll until completed (max 90s)
        for _ in range(30):
            await asyncio.sleep(3)
            poll_resp = await client.get(polling_url, headers=headers)
            poll_resp.raise_for_status()
            result = poll_resp.json()
            if result["status"] == "completed":
                return result["text"] or ""
            elif result["status"] == "error":
                raise RuntimeError(f"AssemblyAI transcription failed: {result.get('error')}")

    raise TimeoutError("AssemblyAI transcription timed out after 90s")


async def _groq_parse_transcript(transcript: str) -> dict:
    """Send transcript to Groq, return parsed incident fields."""
    from src.integrations.groq.client import call_copilot_safe

    result = await call_copilot_safe(
        system_prompt=_GROQ_PARSE_SYSTEM,
        user_prompt=f"Transcript: {transcript}",
        timeout=15.0,
    )
    if result is None:
        # Groq unavailable — return safe defaults
        return {
            "severity": "medium",
            "description": transcript[:200],
            "corridor_id": "UNKNOWN",
            "lat": None,
            "lon": None,
            "location_name": "Unknown location",
        }
    return result


@router.post("/voice-report", response_model=dict, status_code=status.HTTP_201_CREATED)
async def voice_report(
    db: AsyncSession = Depends(get_db),
    audio: UploadFile | None = None,
    audio_url: str | None = Form(default=None),
    officer_id: str = Form(default="voice_officer"),
) -> dict:
    """
    Accept a voice/audio report from an officer.

    Supply either:
    - `audio`     — upload an audio file (mp3, wav, m4a, ogg)
    - `audio_url` — public URL to an audio file

    Flow:
    1. Transcribe via AssemblyAI
    2. Parse transcript with Groq → extract severity, corridor, lat/lon
    3. Create incident in DB (same pipeline as POST /incidents/)
    4. Publish to Kafka traffic.events.raw
    5. Return IncidentOut + transcript + parsed details
    """
    from src.integrations.kafka.producer import publish
    from src.integrations.kafka.topics import TRAFFIC_EVENTS_RAW

    if audio is None and not audio_url:
        raise HTTPException(
            status_code=400,
            detail="Provide either 'audio' file upload or 'audio_url' form field",
        )

    # 1. Transcribe
    try:
        audio_bytes = await audio.read() if audio is not None else None
        transcript = await _assemblyai_transcribe(audio_bytes, audio_url)
    except Exception as exc:
        logger.error("voice_report: transcription failed", error=str(exc))
        raise HTTPException(status_code=502, detail=f"Transcription failed: {exc}") from exc

    logger.info("voice_report: transcript ready", transcript=transcript[:120])

    # 2. Parse with Groq
    parsed = await _groq_parse_transcript(transcript)

    severity = str(parsed.get("severity") or "medium").lower()
    if severity not in ("low", "medium", "high", "critical"):
        severity = "medium"
    description = str(parsed.get("description") or transcript[:200])
    corridor_id = str(parsed.get("corridor_id") or "UNKNOWN")
    lat = parsed.get("lat")
    lon = parsed.get("lon")
    location_name = str(parsed.get("location_name") or "")

    # 3. Insert incident
    incident_id = str(uuid4())
    now = datetime.now(tz=timezone.utc)

    if lat is not None and lon is not None:
        location_expr = "ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)"
        geo_params: dict[str, Any] = {"lat": float(lat), "lon": float(lon)}
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
                     :reporter_id, :confidence, {location_expr}, :now, :now)
                """
            ),
            {
                "id": incident_id,
                "severity": severity,
                "description": description,
                "corridor_id": corridor_id if corridor_id != "UNKNOWN" else None,
                "reporter_id": officer_id,
                "confidence": 0.85,
                "now": now,
                **geo_params,
            },
        )
    except Exception as exc:
        await db.rollback()
        logger.error("voice_report: DB insert failed", error=str(exc))
        raise HTTPException(status_code=500, detail="Failed to create incident") from exc

    await _audit(db, incident_id, "INCIDENT_CREATED", officer_id, {
        "severity": severity,
        "source": "voice_report",
        "transcript_length": len(transcript),
    })
    await db.commit()

    # 4. Publish to Kafka
    event = ManualIncidentEvent(
        event_id=uuid4(),
        source="manual",
        event_time=now,
        corridor_id=corridor_id if corridor_id != "UNKNOWN" else None,
        lat=float(lat) if lat is not None else None,
        lon=float(lon) if lon is not None else None,
        severity=severity,
        description=description,
        reporter_id=officer_id,
        payload={
            "incident_id": incident_id,
            "transcript": transcript,
            "location_name": location_name,
        },
    )
    try:
        await publish(TRAFFIC_EVENTS_RAW, event.model_dump(mode="json"), key=incident_id)
    except Exception as exc:
        logger.warning("voice_report: Kafka publish failed (non-fatal)", error=str(exc))

    logger.info("voice_report: incident created", incident_id=incident_id, severity=severity, corridor_id=corridor_id)

    return {
        "incident_id": incident_id,
        "status": "active",
        "severity": severity,
        "description": description,
        "corridor_id": corridor_id,
        "location_name": location_name,
        "lat": float(lat) if lat is not None else None,
        "lon": float(lon) if lon is not None else None,
        "transcript": transcript,
        "parsed_by": "groq",
        "created_at": now.isoformat(),
    }


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
# POST /incidents/{incident_id}/vision/bulk
# ---------------------------------------------------------------------------


@router.post(
    "/{incident_id}/vision/bulk",
    response_model=BulkVisionAnalysisOut,
    status_code=status.HTTP_200_OK,
)
async def analyse_incident_images_bulk(
    incident_id: UUID,
    images: list[UploadFile],
    officer_id: str = Form(..., description="Badge number or user ID of the uploading officer"),
    db: AsyncSession = Depends(get_db),
) -> BulkVisionAnalysisOut:
    """
    Accept up to 10 images and classify each via the HuggingFace ViT model.

    Processing is sequential to avoid HuggingFace Inference API rate limits.
    Each result is cached in Redis at ``vision:{incident_id}:{index}``.
    The image with the highest confidence also overwrites the primary key
    ``vision:{incident_id}`` so the context builder and LLM always see the
    best available signal.

    A CameraMetaEvent is published to Kafka for every image where
    ``incident_detected=True``.
    """
    from src.integrations.huggingface.vision import analyze_image
    from src.integrations.kafka.producer import publish
    from src.integrations.kafka.topics import TRAFFIC_EVENTS_RAW
    from src.schemas.event import CameraMetaEvent
    from src.integrations.redis.client import cache_set, vision_analysis_key

    MAX_IMAGES = 10
    iid = str(incident_id)

    if len(images) > MAX_IMAGES:
        raise HTTPException(
            status_code=400,
            detail=f"Too many images: received {len(images)}, maximum allowed is {MAX_IMAGES}.",
        )

    # Verify incident exists.
    chk = await db.execute(text("SELECT id FROM incidents WHERE id = :id"), {"id": iid})
    if chk.fetchone() is None:
        raise HTTPException(status_code=404, detail=f"Incident {incident_id} not found")

    results: list[VisionAnalysisOut] = []
    kafka_published_count = 0
    best_result: dict | None = None
    best_idx: int = 0

    for idx, image in enumerate(images):
        image_bytes = await image.read()
        if not image_bytes:
            logger.warning("incidents: bulk vision skipping empty image", index=idx, filename=image.filename)
            continue

        try:
            result = await analyze_image(image_bytes, filename=image.filename or f"upload_{idx}")
        except Exception as exc:
            logger.warning("incidents: bulk vision HF call failed", index=idx, error=str(exc))
            continue

        # Cache individual result at vision:{incident_id}:{idx}
        per_image_key = f"{vision_analysis_key(iid)}:{idx}"
        try:
            await cache_set(
                per_image_key,
                {
                    "incident_id": iid,
                    "image_index": idx,
                    "filename": image.filename,
                    "confidence": result["confidence"],
                    "incident_detected": result["incident_detected"],
                    "top_label": result["top_label"],
                    "scores": result["scores"],
                    "model": result.get("model", ""),
                    "source": result.get("source", ""),
                    "officer_id": officer_id,
                    "analysed_at": datetime.now(tz=timezone.utc).isoformat(),
                },
                ttl_seconds=86400,
            )
        except Exception as exc:
            logger.warning("incidents: bulk vision Redis cache failed (non-fatal)", index=idx, error=str(exc))

        # Track highest-confidence result
        if best_result is None or result["confidence"] > best_result["confidence"]:
            best_result = result
            best_idx = idx

        kafka_published = False
        if result["incident_detected"]:
            try:
                camera_event = CameraMetaEvent(
                    event_id=uuid4(),
                    source="camera",
                    event_time=datetime.now(tz=timezone.utc),
                    camera_id=f"bulk_vision_{officer_id}_{idx}",
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
                        "bulk_index": idx,
                    },
                )
                await publish(TRAFFIC_EVENTS_RAW, camera_event.model_dump(mode="json"), key=iid)
                kafka_published = True
                kafka_published_count += 1
                logger.info(
                    "incidents: bulk vision CameraMetaEvent published",
                    incident_id=iid,
                    index=idx,
                    top_label=result["top_label"],
                    confidence=result["confidence"],
                )
            except Exception as exc:
                logger.warning("incidents: bulk vision Kafka publish failed (non-fatal)", index=idx, error=str(exc))

        results.append(
            VisionAnalysisOut(
                incident_id=incident_id,
                incident_detected=result["incident_detected"],
                confidence=result["confidence"],
                top_label=result["top_label"],
                scores=result["scores"],
                model=result["model"],
                source=result["source"],
                kafka_published=kafka_published,
            )
        )

    # Overwrite primary vision key with highest-confidence result
    if best_result is not None:
        try:
            await cache_set(
                vision_analysis_key(iid),
                {
                    "incident_id": iid,
                    "image_index": best_idx,
                    "confidence": best_result["confidence"],
                    "incident_detected": best_result["incident_detected"],
                    "top_label": best_result["top_label"],
                    "scores": best_result["scores"],
                    "model": best_result.get("model", ""),
                    "source": best_result.get("source", ""),
                    "officer_id": officer_id,
                    "analysed_at": datetime.now(tz=timezone.utc).isoformat(),
                    "bulk_total": len(images),
                },
                ttl_seconds=86400,
            )
            logger.info(
                "incidents: bulk vision best result cached",
                incident_id=iid,
                best_confidence=best_result["confidence"],
                best_label=best_result["top_label"],
            )
        except Exception as exc:
            logger.warning("incidents: bulk vision primary cache write failed (non-fatal)", error=str(exc))

    # Single audit log for the entire bulk operation
    await _audit(db, iid, "VISION_BULK_ANALYSIS", officer_id, {
        "total_images": len(images),
        "processed": len(results),
        "kafka_published_count": kafka_published_count,
        "highest_confidence": best_result["confidence"] if best_result else 0.0,
        "best_label": best_result["top_label"] if best_result else None,
    })
    await db.commit()

    return BulkVisionAnalysisOut(
        incident_id=incident_id,
        total_images=len(images),
        processed=len(results),
        results=results,
        kafka_published_count=kafka_published_count,
        highest_confidence=best_result["confidence"] if best_result else 0.0,
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
            ORDER BY
              CASE WHEN jsonb_array_length(copilot_response->'diversion_plan'->'waypoints') > 0
                   THEN 0
                   WHEN copilot_response->'diversion_plan' IS NOT NULL
                        AND copilot_response->>'diversion_plan' != 'null'
                   THEN 1
                   ELSE 2 END,
              confidence DESC NULLS LAST,
              created_at DESC
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

    # 3b. Fall back to LLM waypoints — but snap each to real OSM nodes
    #     and route between them so the line follows actual roads.
    waypoint_osm_routed = False  # tracks actual outcome for meta
    if not diversion_added and diversion_plan:
        waypoints = diversion_plan.get("waypoints") or []
        valid_wps = [wp for wp in waypoints if wp.get("lat") and wp.get("lng")]
        if len(valid_wps) >= 2:
            all_coords: list[list[float]] = []
            road_names_collected: list[str] = []
            total_dist_m = 0.0
            routed_via_osm = False

            if graph is not None:
                try:
                    from src.modules.routing.diversion import compute_diversion_routes
                    # Build blocked edges from affected segments so the
                    # diversion route avoids already-congested roads.
                    wp_blocked: list[tuple[int, int]] = [
                        (int(s["osm_node_u"]), int(s["osm_node_v"]))
                        for s in segments
                        if s.get("osm_node_u") and s.get("osm_node_v")
                    ]

                    # Snap each waypoint to nearest OSM node
                    snapped: list[int] = []
                    for wp in valid_wps:
                        node = await get_node_nearest(float(wp["lat"]), float(wp["lng"]), graph)
                        if node:
                            snapped.append(node)

                    # Route between consecutive snapped nodes using A* (k=1).
                    # A* uses straight-line heuristic → faster than Dijkstra
                    # on 67k-node Ahmedabad graph. Blocked edges exclude
                    # congested segments so the diversion avoids the jam.
                    if len(snapped) >= 2:
                        for i in range(len(snapped) - 1):
                            seg_routes = await compute_diversion_routes(
                                origin_node=snapped[i],
                                destination_node=snapped[i + 1],
                                graph=graph,
                                blocked_edges=wp_blocked,
                                k=1,
                            )
                            if seg_routes:
                                best_seg = seg_routes[0]  # A* already returns optimal
                                seg_coords = best_seg["route_geojson"]["coordinates"]
                                if all_coords:
                                    seg_coords = seg_coords[1:]
                                all_coords.extend(seg_coords)
                                total_dist_m += best_seg["distance_m"]
                                for rn in best_seg.get("road_names", []):
                                    if rn not in road_names_collected:
                                        road_names_collected.append(rn)
                        if len(all_coords) >= 2:
                            routed_via_osm = True
                            waypoint_osm_routed = True
                except Exception as exc:
                    logger.warning("map-data: waypoint OSM routing failed — using straight lines: %s", exc)

            # If OSM routing worked, emit a proper road-following LineString
            if routed_via_osm and len(all_coords) >= 2:
                features.append({
                    "type": "Feature",
                    "geometry": {"type": "LineString", "coordinates": all_coords},
                    "properties": {
                        "feature_type": "diversion_route",
                        "source": "osm_waypoint_routing",
                        "description": diversion_plan.get("route_description", ""),
                        "estimated_extra_minutes": diversion_plan.get("estimated_extra_minutes"),
                        "traffic_redistribution_pct": diversion_plan.get("traffic_redistribution_pct"),
                        "confidence": diversion_plan.get("confidence"),
                        "waypoint_names": [wp.get("name") for wp in valid_wps],
                        "road_names": road_names_collected,
                        "distance_m": round(total_dist_m, 1),
                        "coordinate_count": len(all_coords),
                        "stroke_color": "#3399ff",
                        "stroke_width": 4,
                        "stroke_dash": "8,4",
                    },
                })
            else:
                # Last resort: straight lines between waypoints
                coords = [[wp["lng"], wp["lat"]] for wp in valid_wps]
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
                        "waypoint_names": [wp.get("name") for wp in valid_wps],
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
                else "osm_waypoint_routing" if waypoint_osm_routed
                else "llm_waypoints" if (diversion_plan and diversion_plan.get("waypoints"))
                else "none"
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
