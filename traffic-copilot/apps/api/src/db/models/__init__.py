"""
Re-export all ORM models so consumers can import from a single namespace:

    from src.db.models import (
        Incident,
        IncidentEvent,
        AffectedSegment,
        DiversionRoute,
        SignalPlanCandidate,
        Recommendation,
        Alert,
        Approval,
        AuditLog,
        SopChunk,
        IncidentSummary,
        AlertTemplate,
    )
"""

from src.db.models.incident import Incident
from src.db.models.segment import (
    AffectedSegment,
    DiversionRoute,
    IncidentEvent,
    SignalPlanCandidate,
)
from src.db.models.recommendation import Recommendation
from src.db.models.alert import Alert, Approval
from src.db.models.audit import AuditLog, AlertTemplate, IncidentSummary, SopChunk

__all__ = [
    "Incident",
    "IncidentEvent",
    "AffectedSegment",
    "DiversionRoute",
    "SignalPlanCandidate",
    "Recommendation",
    "Alert",
    "Approval",
    "AuditLog",
    "SopChunk",
    "IncidentSummary",
    "AlertTemplate",
]
