"""
Raw payload normaliser for the TrafficCopilot ingest pipeline.

Converts untyped dicts arriving from HTTP endpoints (or Kafka replay) into
strongly-typed ``TrafficEvent`` subclasses.  Sensible defaults are applied for
missing fields so downstream modules always receive a complete object:

- ``event_id``  — generated with ``uuid4()`` if absent
- ``event_time`` — set to ``datetime.utcnow()`` if absent or unparseable
- ``corridor_id``, ``lat``, ``lon`` — preserved as ``None`` when not provided

Dispatch
--------
Use :func:`normalize_event` as the single entry-point; it routes to the
correct per-source normaliser based on the ``source`` field.

    from src.modules.ingest.normalizer import normalize_event

    event = normalize_event("sensor", raw_payload)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import UUID, uuid4

from src.schemas.event import (
    CameraMetaEvent,
    ManualIncidentEvent,
    RadioTranscriptEvent,
    SensorSpeedEvent,
    TrafficEvent,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _parse_event_time(raw: object) -> datetime:
    """
    Parse *raw* into a timezone-aware datetime.

    Accepts ISO 8601 strings, Unix timestamps (int/float), or existing
    ``datetime`` objects.  Falls back to ``utcnow()`` if parsing fails.
    """
    if raw is None:
        return datetime.now(tz=timezone.utc)
    if isinstance(raw, datetime):
        return raw if raw.tzinfo is not None else raw.replace(tzinfo=timezone.utc)
    if isinstance(raw, (int, float)):
        try:
            return datetime.fromtimestamp(float(raw), tz=timezone.utc)
        except (OSError, OverflowError, ValueError):
            pass
    if isinstance(raw, str):
        for fmt in (
            "%Y-%m-%dT%H:%M:%S.%f%z",
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
        ):
            try:
                dt = datetime.strptime(raw, fmt)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except ValueError:
                continue
    logger.warning("Could not parse event_time=%r; defaulting to now()", raw)
    return datetime.now(tz=timezone.utc)


def _parse_uuid(raw: object) -> UUID:
    """Return *raw* as UUID, generating a new one if absent or invalid."""
    if raw is None:
        return uuid4()
    if isinstance(raw, UUID):
        return raw
    try:
        return UUID(str(raw))
    except (ValueError, AttributeError):
        return uuid4()


# ---------------------------------------------------------------------------
# Per-source normalisers
# ---------------------------------------------------------------------------


def normalize_sensor(data: dict) -> SensorSpeedEvent:
    """
    Normalise a raw sensor payload into a :class:`SensorSpeedEvent`.

    Expected keys (all others are forwarded to ``payload``):
        ``segment_id``, ``speed_kmh``, ``free_flow_kmh``, ``occupancy_pct``,
        ``event_time`` (optional), ``event_id`` (optional),
        ``corridor_id`` (optional), ``lat`` (optional), ``lon`` (optional).
    """
    return SensorSpeedEvent(
        event_id=_parse_uuid(data.get("event_id")),
        source="sensor",
        event_time=_parse_event_time(data.get("event_time")),
        corridor_id=data.get("corridor_id"),
        lat=_optional_float(data.get("lat")),
        lon=_optional_float(data.get("lon")),
        payload=data,
        segment_id=str(data["segment_id"]),
        speed_kmh=float(data["speed_kmh"]),
        free_flow_kmh=float(data["free_flow_kmh"]),
        occupancy_pct=float(data["occupancy_pct"]),
    )


def normalize_camera(data: dict) -> CameraMetaEvent:
    """
    Normalise a raw camera-pipeline payload into a :class:`CameraMetaEvent`.

    Expected keys:
        ``camera_id``, ``lane_blocked``, ``vehicle_count``,
        ``incident_detected``, ``confidence``.
    """
    return CameraMetaEvent(
        event_id=_parse_uuid(data.get("event_id")),
        source="camera",
        event_time=_parse_event_time(data.get("event_time")),
        corridor_id=data.get("corridor_id"),
        lat=_optional_float(data.get("lat")),
        lon=_optional_float(data.get("lon")),
        payload=data,
        camera_id=str(data["camera_id"]),
        lane_blocked=bool(data["lane_blocked"]),
        vehicle_count=int(data["vehicle_count"]),
        incident_detected=bool(data["incident_detected"]),
        confidence=float(data["confidence"]),
    )


def normalize_radio(data: dict) -> RadioTranscriptEvent:
    """
    Normalise a raw radio-transcript payload into a :class:`RadioTranscriptEvent`.

    Expected keys: ``transcript``, ``unit_id``.
    """
    return RadioTranscriptEvent(
        event_id=_parse_uuid(data.get("event_id")),
        source="radio",
        event_time=_parse_event_time(data.get("event_time")),
        corridor_id=data.get("corridor_id"),
        lat=_optional_float(data.get("lat")),
        lon=_optional_float(data.get("lon")),
        payload=data,
        transcript=str(data["transcript"]),
        unit_id=str(data["unit_id"]),
    )


def normalize_manual(data: dict) -> ManualIncidentEvent:
    """
    Normalise a raw manual-entry payload into a :class:`ManualIncidentEvent`.

    Expected keys: ``severity``, ``description``, ``reporter_id``.
    """
    return ManualIncidentEvent(
        event_id=_parse_uuid(data.get("event_id")),
        source="manual",
        event_time=_parse_event_time(data.get("event_time")),
        corridor_id=data.get("corridor_id"),
        lat=_optional_float(data.get("lat")),
        lon=_optional_float(data.get("lon")),
        payload=data,
        severity=data["severity"],
        description=str(data["description"]),
        reporter_id=str(data["reporter_id"]),
    )


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

_NORMALIZERS = {
    "sensor": normalize_sensor,
    "camera": normalize_camera,
    "radio": normalize_radio,
    "manual": normalize_manual,
}


def normalize_event(source: str, data: dict) -> TrafficEvent:
    """
    Dispatch *data* to the appropriate per-source normaliser and return a
    typed :class:`TrafficEvent` subclass.

    Parameters
    ----------
    source:
        One of ``"sensor"``, ``"camera"``, ``"radio"``, ``"manual"``.
    data:
        Raw payload dict from the HTTP request or Kafka message.

    Raises
    ------
    ValueError
        If *source* is not one of the recognised values.
    KeyError
        If a required field is missing from *data* for the given source.
    """
    normalizer = _NORMALIZERS.get(source)
    if normalizer is None:
        raise ValueError(
            f"Unknown event source {source!r}. "
            f"Expected one of: {list(_NORMALIZERS)}"
        )
    return normalizer(data)


# ---------------------------------------------------------------------------
# Internal float helper
# ---------------------------------------------------------------------------


def _optional_float(value: object) -> float | None:
    """Return *value* as float, or ``None`` if absent / not parseable."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
