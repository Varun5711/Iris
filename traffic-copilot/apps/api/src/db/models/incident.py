"""
ORM model for the `incidents` table.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from geoalchemy2 import Geometry
from sqlalchemy import Float, String, Text, TIMESTAMP, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.session import Base

if TYPE_CHECKING:
    from src.db.models.segment import IncidentEvent, AffectedSegment
    from src.db.models.recommendation import Recommendation


class Incident(Base):
    __tablename__ = "incidents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    status: Mapped[str] = mapped_column(String(20), default="active")
    severity: Mapped[str] = mapped_column(String(20))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    reporter_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    location = mapped_column(Geometry("POINT", srid=4326), nullable=True)
    corridor_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    detection_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )

    # relationships
    events: Mapped[list[IncidentEvent]] = relationship(
        "IncidentEvent", back_populates="incident", lazy="select"
    )
    segments: Mapped[list[AffectedSegment]] = relationship(
        "AffectedSegment", back_populates="incident", lazy="select"
    )
    recommendations: Mapped[list[Recommendation]] = relationship(
        "Recommendation", back_populates="incident", lazy="select"
    )
