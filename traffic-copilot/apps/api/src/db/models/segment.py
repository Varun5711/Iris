"""
ORM models for road-network and signal-plan entities:
  - IncidentEvent
  - AffectedSegment
  - DiversionRoute
  - SignalPlanCandidate
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from geoalchemy2 import Geometry
from sqlalchemy import BigInteger, Float, ForeignKey, Integer, String, Text, TIMESTAMP, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.session import Base

if TYPE_CHECKING:
    from src.db.models.incident import Incident


class IncidentEvent(Base):
    __tablename__ = "incident_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    incident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("incidents.id", ondelete="CASCADE"),
        nullable=False,
    )
    source: Mapped[str] = mapped_column(String(20), nullable=False)
    raw_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    event_time: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )

    # relationships
    incident: Mapped[Incident] = relationship("Incident", back_populates="events")


class AffectedSegment(Base):
    __tablename__ = "affected_segments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    incident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("incidents.id", ondelete="CASCADE"),
        nullable=False,
    )
    osm_way_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    geom = mapped_column(Geometry("LINESTRING", srid=4326), nullable=True)
    delay_seconds: Mapped[int] = mapped_column(Integer, default=0)
    congestion_pct: Mapped[float] = mapped_column(Float, default=0.0)

    # relationships
    incident: Mapped[Incident] = relationship("Incident", back_populates="segments")


class DiversionRoute(Base):
    __tablename__ = "diversion_routes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    incident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("incidents.id", ondelete="CASCADE"),
        nullable=False,
    )
    route_geojson: Mapped[dict] = mapped_column(JSONB, default=dict)
    extra_minutes: Mapped[float | None] = mapped_column(Float, nullable=True)
    redistribution_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )

    # relationships
    incident: Mapped[Incident] = relationship("Incident")


class SignalPlanCandidate(Base):
    __tablename__ = "signal_plan_candidates"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    incident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("incidents.id", ondelete="CASCADE"),
        nullable=False,
    )
    intersection_id: Mapped[str] = mapped_column(Text, nullable=False)
    current_plan: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    suggested_plan: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )

    # relationships
    incident: Mapped[Incident] = relationship("Incident")
