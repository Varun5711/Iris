"""
Pydantic v2 schemas for co-pilot recommendations and their components.

Hierarchy
---------
CopilotResponse          — full structured LLM output
├── SignalAction          — one intersection signal timing change
├── DiversionPlan        — alternative route suggestion
└── AlertDraft           — draft public communications message

RecommendationOut        — database-backed recommendation record (includes
                           the serialised CopilotResponse when available)
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


# ---------------------------------------------------------------------------
# Component schemas
# ---------------------------------------------------------------------------


class SignalAction(BaseModel):
    """
    A proposed change to one traffic-signal intersection's timing plan.
    """

    intersection_id: str = Field(
        ..., description="Unique intersection identifier in the signal controller database"
    )
    action: str = Field(
        ...,
        min_length=1,
        description=(
            "Human-readable action description, e.g. "
            "'Extend green phase on 5th Ave NB by 15 s' or "
            "'Activate pre-emption plan #3'."
        ),
    )
    expected_impact: str = Field(
        ...,
        description="Predicted traffic impact, e.g. 'Reduce queue length by ~30 vehicles'",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Model confidence in this recommendation (0–1)",
    )


class DiversionPlan(BaseModel):
    """
    An alternative routing recommendation to redistribute traffic away from
    the affected corridor.
    """

    route_description: str = Field(
        ...,
        min_length=1,
        description="Plain-language turn-by-turn or corridor-level description of the diversion",
    )
    estimated_extra_minutes: float = Field(
        ...,
        ge=0.0,
        description="Expected additional travel time compared to the normal route",
    )
    traffic_redistribution_pct: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Percentage of affected traffic expected to take the diversion",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Model confidence in the diversion plan (0–1)",
    )
    evidence_refs: list[str] = Field(
        default_factory=list,
        description="References to supporting evidence (SOP chunk IDs, sensor readings, etc.)",
    )


class AlertDraft(BaseModel):
    """
    A draft public-communications message for one output channel.
    The ``char_count`` field is computed automatically from ``message``.
    """

    channel: Literal["vms", "radio", "social"] = Field(
        ...,
        description="Target publication channel: VMS boards, radio broadcast, or social media",
    )
    message: str = Field(
        ...,
        min_length=1,
        description="Draft message text ready for officer review before publishing",
    )
    char_count: int = Field(
        default=0,
        description="Character count of the message (auto-computed, do not set manually)",
    )

    @model_validator(mode="after")
    def _compute_char_count(self) -> "AlertDraft":
        self.char_count = len(self.message)
        return self


# ---------------------------------------------------------------------------
# Top-level co-pilot response
# ---------------------------------------------------------------------------


class CopilotResponse(BaseModel):
    """
    Full structured output from the LLM co-pilot for a single incident.

    ``review_required`` is True whenever the model is uncertain enough that an
    officer must confirm before any action is taken.  When ``blocked_reason``
    is set the response must not be acted upon automatically under any
    circumstances.
    """

    incident_summary: str = Field(
        ..., description="Concise 1–3 sentence summary of the incident and current conditions"
    )
    signal_actions: list[SignalAction] = Field(
        default_factory=list,
        description="Ordered list of recommended signal timing changes (highest priority first)",
    )
    diversion_plan: DiversionPlan | None = Field(
        default=None,
        description="Alternative routing recommendation, or None if diversion is not warranted",
    )
    alert_drafts: list[AlertDraft] = Field(
        default_factory=list,
        description="Draft public communications ready for officer review and approval",
    )
    narrative: str = Field(
        ...,
        description=(
            "Extended markdown narrative explaining the reasoning behind each "
            "recommendation, citing evidence and relevant SOP sections."
        ),
    )
    conversational_answer: str | None = Field(
        default=None,
        description=(
            "Direct answer to an officer's follow-up chat question, "
            "present only when the request was conversational rather than "
            "a new incident analysis."
        ),
    )
    overall_confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Aggregate model confidence across all recommendations (0–1)",
    )
    review_required: bool = Field(
        ...,
        description=(
            "True when the model's confidence is below the threshold or when "
            "the situation contains unusual factors requiring human judgement."
        ),
    )
    blocked_reason: str | None = Field(
        default=None,
        description=(
            "If set, explains why the co-pilot declined to produce actionable "
            "recommendations (e.g. policy violation, insufficient data). "
            "The response must not be acted upon until an officer reviews it."
        ),
    )
    evidence_refs: list[str] = Field(
        default_factory=list,
        description=(
            "Identifiers of SOP chunks, historical incident summaries, sensor "
            "readings, or other documents used to ground the response."
        ),
    )


# ---------------------------------------------------------------------------
# Database-backed recommendation record
# ---------------------------------------------------------------------------


class RecommendationOut(BaseModel):
    """
    Recommendation record as stored in the ``recommendations`` table, returned
    by GET /recommendations/{id} and list endpoints.
    """

    id: UUID
    incident_id: UUID
    rec_type: str = Field(
        ...,
        description="Classification of the recommendation: 'signal', 'diversion', 'alert', 'composite'",
    )
    action: str = Field(..., description="Primary recommended action (human-readable)")
    location: str | None = Field(default=None, description="Free-text location description")
    expected_impact: str | None = Field(default=None, description="Predicted outcome")
    evidence_refs: list = Field(default_factory=list, description="Supporting evidence identifiers")
    confidence: float | None = Field(
        default=None, ge=0.0, le=1.0, description="Model confidence for this specific recommendation"
    )
    blocked_reason: str | None = Field(
        default=None,
        description="Reason the recommendation is blocked from automatic execution",
    )
    review_required: bool = Field(
        ...,
        description="Whether an officer must explicitly approve before action is taken",
    )
    status: str = Field(
        ...,
        description="Lifecycle status: 'pending', 'approved', 'rejected', 'executed', 'expired'",
    )
    created_at: datetime
    copilot_response: CopilotResponse | None = Field(
        default=None,
        description="Full deserialized LLM response, present when the rec was AI-generated",
    )

    model_config = {"from_attributes": True, "populate_by_name": True}
