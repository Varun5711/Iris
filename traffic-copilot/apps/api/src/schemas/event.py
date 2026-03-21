"""
Pydantic v2 schemas for raw traffic events ingested from all sources.

Event hierarchy
---------------
TrafficEvent (base)
├── SensorSpeedEvent   — loop / radar detector readings
├── CameraMetaEvent    — vision pipeline metadata
├── RadioTranscriptEvent — officer radio transcript
└── ManualIncidentEvent  — dispatcher / officer manual entry

NormalizedSignal wraps any TrafficEvent with a detection score and type label
produced by the detector module.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Base event
# ---------------------------------------------------------------------------


class TrafficEvent(BaseModel):
    """
    Root schema shared by every event source.  All fields except ``payload``
    are either provided by the originating sensor or defaulted automatically.
    """

    event_id: UUID = Field(default_factory=uuid4, description="Globally unique event identifier")
    source: Literal["sensor", "camera", "radio", "manual"] = Field(
        ..., description="Origin system that produced this event"
    )
    event_time: datetime = Field(
        ..., description="Wall-clock time the event was observed (UTC)"
    )
    corridor_id: str | None = Field(
        default=None,
        description="Traffic management corridor identifier, when known",
    )
    lat: float | None = Field(
        default=None,
        ge=-90.0,
        le=90.0,
        description="WGS-84 latitude of the event origin",
    )
    lon: float | None = Field(
        default=None,
        ge=-180.0,
        le=180.0,
        description="WGS-84 longitude of the event origin",
    )
    payload: dict = Field(
        default_factory=dict,
        description="Full raw payload forwarded from the source system",
    )

    model_config = {"populate_by_name": True}


# ---------------------------------------------------------------------------
# Specialised event types
# ---------------------------------------------------------------------------


class SensorSpeedEvent(TrafficEvent):
    """Loop-detector or radar sensor speed/occupancy reading."""

    source: Literal["sensor"] = "sensor"
    segment_id: str = Field(..., description="Road segment identifier (typically OSM way ID as string)")
    speed_kmh: float = Field(..., ge=0.0, description="Measured mean speed in km/h")
    free_flow_kmh: float = Field(..., gt=0.0, description="Free-flow reference speed for this segment")
    occupancy_pct: float = Field(
        ..., ge=0.0, le=100.0, description="Loop occupancy percentage (0–100)"
    )


class CameraMetaEvent(TrafficEvent):
    """
    Metadata produced by a vision pipeline (object detection, lane analysis).
    The raw frame is never included — only derived metadata travels over Kafka.
    """

    source: Literal["camera"] = "camera"
    camera_id: str = Field(..., description="Unique camera identifier in the CCTV inventory")
    lane_blocked: bool = Field(..., description="True when at least one lane is obstructed")
    vehicle_count: int = Field(..., ge=0, description="Number of vehicles visible in frame")
    incident_detected: bool = Field(
        ..., description="True when the vision model flagged a potential incident"
    )
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Model confidence for incident_detected"
    )


class RadioTranscriptEvent(TrafficEvent):
    """Transcribed officer radio communication (ASR output)."""

    source: Literal["radio"] = "radio"
    transcript: str = Field(..., min_length=1, description="ASR transcript text")
    unit_id: str = Field(..., description="Radio unit / call-sign identifier")


class ManualIncidentEvent(TrafficEvent):
    """Incident manually entered by a dispatcher or field officer."""

    source: Literal["manual"] = "manual"
    severity: Literal["low", "medium", "high", "critical"] = Field(
        ..., description="Officer-assessed incident severity"
    )
    description: str = Field(..., min_length=1, description="Free-text incident description")
    reporter_id: str = Field(..., description="Badge number or user ID of the reporting officer")


# ---------------------------------------------------------------------------
# Normalised signal (output of detector / ingest pipeline)
# ---------------------------------------------------------------------------


class NormalizedSignal(BaseModel):
    """
    Wraps a raw ``TrafficEvent`` with enrichment produced by the detection
    pipeline before the signal is written to the database or forwarded to the
    state engine.
    """

    event: TrafficEvent = Field(..., description="The underlying raw event (any subtype)")
    detection_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description=(
            "Composite anomaly / incident detection score.  "
            "Scores above settings.detection_confidence_threshold "
            "trigger incident creation."
        ),
    )
    signal_type: str = Field(
        ...,
        description=(
            "Semantic label for the signal, e.g. 'speed_drop', "
            "'lane_blockage', 'radio_incident', 'manual_entry'."
        ),
    )

    model_config = {"populate_by_name": True}
