"""
Pydantic v2 schemas for incidents and their associated road segments.

IncidentCreate   — request body for POST /incidents
IncidentOut      — response body for GET /incidents/{id} and list endpoints
SegmentOut       — embedded in IncidentSnapshot
IncidentSnapshot — enriched view combining incident + affected segments + event count
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Shared constants
# ---------------------------------------------------------------------------

SeverityLiteral = Literal["low", "medium", "high", "critical"]
StatusLiteral = Literal["active", "monitoring", "resolved", "false_alarm"]


# ---------------------------------------------------------------------------
# Request schema
# ---------------------------------------------------------------------------


class IncidentCreate(BaseModel):
    """
    Payload accepted by the manual incident creation endpoint.

    Latitude / longitude are optional — an officer may not have coordinates
    at the time of first report.  The corridor_id can be used as a coarse
    location reference instead.
    """

    severity: SeverityLiteral = Field(..., description="Assessed incident severity")
    description: str = Field(
        ..., min_length=1, max_length=2000, description="Free-text incident description"
    )
    lat: float | None = Field(
        default=None, ge=-90.0, le=90.0, description="WGS-84 latitude"
    )
    lon: float | None = Field(
        default=None, ge=-180.0, le=180.0, description="WGS-84 longitude"
    )
    corridor_id: str | None = Field(
        default=None, description="Traffic management corridor, e.g. 'I-95-NB'"
    )
    detection_confidence: float | None = Field(
        default=0.9,
        ge=0.0,
        le=1.0,
        description="Confidence score 0–1 for automated detections; defaults to 0.9 for manual reports",
    )
    reporter_id: str | None = Field(
        default="manual",
        description="Badge number or system ID of the reporter",
    )

    model_config = {"populate_by_name": True}


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class IncidentOut(BaseModel):
    """
    Full incident representation returned by the API.  Maps directly to the
    ``incidents`` database table, with the PostGIS geometry unpacked into
    separate ``location_lat`` / ``location_lon`` float fields.
    """

    id: UUID
    status: StatusLiteral
    severity: SeverityLiteral
    description: str | None
    location_lat: float | None = Field(default=None, description="WGS-84 latitude extracted from PostGIS geometry")
    location_lon: float | None = Field(default=None, description="WGS-84 longitude extracted from PostGIS geometry")
    corridor_id: str | None = None
    reporter_id: str | None = None
    created_at: datetime
    updated_at: datetime
    detection_confidence: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Confidence score produced by the automated detector (0–1)",
    )

    model_config = {"from_attributes": True, "populate_by_name": True}


class SegmentOut(BaseModel):
    """
    Road segment affected by an incident, as stored in ``affected_segments``.
    """

    osm_way_id: int = Field(..., description="OpenStreetMap way ID for this road segment")
    delay_seconds: int = Field(
        ..., ge=0, description="Additional travel delay caused by the incident"
    )
    congestion_pct: float = Field(
        ..., ge=0.0, le=100.0, description="Congestion level as a percentage of capacity"
    )

    model_config = {"from_attributes": True}


class VisionAnalysisOut(BaseModel):
    """
    Result returned by POST /incidents/{incident_id}/vision.
    """

    incident_id: UUID = Field(..., description="Incident the image was analysed against")
    incident_detected: bool = Field(
        ..., description="True when the vision model flagged a likely incident in the image"
    )
    confidence: float = Field(..., ge=0.0, le=1.0, description="Score of the top classification label")
    top_label: str = Field(..., description="Highest-scoring candidate label")
    scores: dict = Field(default_factory=dict, description="Full label→score mapping from the model")
    model: str = Field(..., description="HF model used for classification")
    source: str = Field(..., description="'huggingface' or 'mock'")
    kafka_published: bool = Field(
        default=False,
        description="True when a CameraMetaEvent was published to Kafka for downstream processing",
    )

    model_config = {"populate_by_name": True}


class BulkVisionAnalysisOut(BaseModel):
    """
    Result returned by POST /incidents/{incident_id}/vision/bulk.
    """

    incident_id: UUID = Field(..., description="Incident the images were analysed against")
    total_images: int = Field(..., ge=0, description="Number of images received")
    processed: int = Field(..., ge=0, description="Number of images successfully analysed")
    results: list[VisionAnalysisOut] = Field(default_factory=list, description="Per-image analysis results")
    kafka_published_count: int = Field(
        default=0,
        description="Number of CameraMetaEvents published to Kafka (one per detected incident image)",
    )
    highest_confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Highest confidence score across all analysed images",
    )

    model_config = {"populate_by_name": True}


class IncidentSnapshot(BaseModel):
    """
    Enriched read-model combining an incident with its affected road segments
    and aggregated event statistics.  Used by the dashboard and co-pilot
    context builder.
    """

    incident: IncidentOut = Field(..., description="The core incident record")
    affected_segments: list[SegmentOut] = Field(
        default_factory=list,
        description="Road segments whose delay / congestion is linked to this incident",
    )
    event_count: int = Field(
        ..., ge=0, description="Total number of raw events correlated with this incident"
    )
    last_updated: datetime = Field(
        ..., description="Timestamp of the most recent state change or event correlation"
    )
