"""
Policy validator — hard rule enforcement for CopilotResponse objects.

Rules enforced:
  1. Forbidden actuation phrases in any text field trigger a blocked_reason.
  2. overall_confidence < 0.6 → review_required = True.
  3. Empty evidence_refs → review_required = True + note in blocked_reason.
  4. Each SignalAction.action must be advisory (checked against actuation phrases).

This module never raises — it always returns a (possibly modified) CopilotResponse.
"""

from __future__ import annotations

import logging

from src.schemas.recommendation import AlertDraft, CopilotResponse, DiversionPlan, SignalAction

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Forbidden phrase list — any match blocks direct-actuation recommendations.
# ---------------------------------------------------------------------------

FORBIDDEN_ACTUATION_PHRASES: list[str] = [
    "actuate signal",
    "set signal",
    "change phase to",
    "activate signal",
    "turn signal",
    "switch signal",
    "directly control",
    "override signal",
    "set phase",
    "program signal",
    "modify signal timing directly",
]

# Confidence threshold below which review is required.
_MIN_CONFIDENCE_FOR_AUTO = 0.6


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def validate_copilot_response(response: CopilotResponse) -> CopilotResponse:
    """
    Apply all policy rules to *response* and return the (possibly modified) object.

    Modifications are made on a copy of the fields so the original Pydantic
    object is not mutated in-place; a new :class:`CopilotResponse` is returned.

    Rules applied (in order):
    1. Forbidden actuation phrases scan across all free-text fields.
    2. Low overall_confidence (< 0.6) → review_required = True.
    3. Empty evidence_refs → review_required = True + note.
    4. Per-SignalAction advisory language check.

    Parameters
    ----------
    response:
        The raw :class:`CopilotResponse` from the LLM.

    Returns
    -------
    CopilotResponse
        Validated (and possibly flag-modified) response.  Never raises.
    """
    try:
        return _apply_rules(response)
    except Exception as exc:  # noqa: BLE001
        logger.error("validate_copilot_response crashed — returning as-is: %s", exc)
        return response


def _apply_rules(response: CopilotResponse) -> CopilotResponse:
    """Internal implementation of all validation rules."""
    blocked_reasons: list[str] = []

    if response.blocked_reason:
        blocked_reasons.append(response.blocked_reason)

    review_required = response.review_required

    # ------------------------------------------------------------------
    # Rule 1: Forbidden actuation phrase scan across all text fields
    # ------------------------------------------------------------------
    text_fields_to_check: list[tuple[str, str]] = [
        ("incident_summary", response.incident_summary),
        ("narrative", response.narrative),
    ]

    if response.conversational_answer:
        text_fields_to_check.append(("conversational_answer", response.conversational_answer))

    if response.diversion_plan:
        text_fields_to_check.append(
            ("diversion_plan.route_description", response.diversion_plan.route_description)
        )

    for draft in response.alert_drafts:
        text_fields_to_check.append((f"alert_drafts[{draft.channel}]", draft.message))

    for field_name, text in text_fields_to_check:
        if text and check_for_direct_actuation(text):
            msg = (
                f"Policy violation: forbidden actuation language detected in '{field_name}'. "
                "Recommendation must not be acted upon without manual review."
            )
            blocked_reasons.append(msg)
            review_required = True
            logger.warning("Actuation phrase found in field=%s — blocking", field_name)

    # ------------------------------------------------------------------
    # Rule 2: Low confidence → require review
    # ------------------------------------------------------------------
    if response.overall_confidence < _MIN_CONFIDENCE_FOR_AUTO:
        review_required = True
        logger.debug(
            "overall_confidence=%.2f < %.2f — setting review_required=True",
            response.overall_confidence,
            _MIN_CONFIDENCE_FOR_AUTO,
        )

    # ------------------------------------------------------------------
    # Rule 3: Empty evidence_refs → require review + note
    # ------------------------------------------------------------------
    if not response.evidence_refs:
        review_required = True
        blocked_reasons.append(
            "No evidence references provided. Officer should manually verify all "
            "recommendations against current sensor data and SOPs before acting."
        )
        logger.debug("evidence_refs is empty — setting review_required=True")

    # ------------------------------------------------------------------
    # Rule 4: Per-SignalAction advisory language check
    # ------------------------------------------------------------------
    validated_actions: list[SignalAction] = []
    for action in response.signal_actions:
        if check_for_direct_actuation(action.action):
            blocked_reasons.append(
                f"Policy violation: SignalAction for '{action.intersection_id}' contains "
                f"forbidden direct-actuation language: '{action.action}'. "
                "All signal actions must be advisory only."
            )
            review_required = True
            logger.warning(
                "Direct actuation detected in SignalAction intersection_id=%s",
                action.intersection_id,
            )
            # Replace the action text with a sanitised advisory version.
            safe_action = SignalAction(
                intersection_id=action.intersection_id,
                action=f"[ADVISORY REVIEW REQUIRED] {action.action}",
                expected_impact=action.expected_impact,
                confidence=min(action.confidence, 0.4),
            )
            validated_actions.append(safe_action)
        else:
            validated_actions.append(action)

    # ------------------------------------------------------------------
    # Assemble final blocked_reason string
    # ------------------------------------------------------------------
    final_blocked_reason: str | None = None
    if blocked_reasons:
        final_blocked_reason = " | ".join(blocked_reasons)

    # Build a new CopilotResponse with the validated values.
    return CopilotResponse(
        incident_summary=response.incident_summary,
        signal_actions=validated_actions,
        diversion_plan=response.diversion_plan,
        alert_drafts=response.alert_drafts,
        narrative=response.narrative,
        conversational_answer=response.conversational_answer,
        overall_confidence=response.overall_confidence,
        review_required=review_required,
        blocked_reason=final_blocked_reason,
        evidence_refs=response.evidence_refs,
    )


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def check_for_direct_actuation(text: str) -> bool:
    """
    Return ``True`` if *text* contains any forbidden actuation phrase.

    The check is case-insensitive.

    Parameters
    ----------
    text:
        Arbitrary string to scan.

    Returns
    -------
    bool
        ``True`` if a forbidden phrase is found.
    """
    if not text:
        return False
    lower = text.lower()
    return any(phrase in lower for phrase in FORBIDDEN_ACTUATION_PHRASES)


def score_evidence_quality(evidence_refs: list[str]) -> float:
    """
    Score evidence quality on a 0–1 scale based on quantity and source diversity.

    Scoring tiers:
    - 0.0 : no evidence refs
    - 0.5 : exactly one ref
    - 0.8 : 2–3 refs
    - 1.0 : 4 or more refs

    An additional diversity bonus is applied when refs appear to come from
    different source types (identified by prefix or common keywords).

    Parameters
    ----------
    evidence_refs:
        List of evidence reference strings (SOP IDs, sensor IDs, etc.).

    Returns
    -------
    float
        Score in [0.0, 1.0].
    """
    n = len(evidence_refs)
    if n == 0:
        return 0.0
    if n == 1:
        base = 0.5
    elif n <= 3:
        base = 0.8
    else:
        base = 1.0

    # Diversity: count how many distinct source-type prefixes appear.
    # Source types are inferred from common keywords in the ref strings.
    source_types: set[str] = set()
    for ref in evidence_refs:
        ref_lower = ref.lower()
        if any(k in ref_lower for k in ("sop", "procedure", "standard")):
            source_types.add("sop")
        elif any(k in ref_lower for k in ("sensor", "loop", "detector", "speed")):
            source_types.add("sensor")
        elif any(k in ref_lower for k in ("camera", "cctv", "video")):
            source_types.add("camera")
        elif any(k in ref_lower for k in ("hist", "incident", "previous", "prior")):
            source_types.add("historical")
        elif any(k in ref_lower for k in ("radio", "transcript", "report")):
            source_types.add("radio")
        else:
            source_types.add("other")

    # Cap diversity bonus at 0.1 to keep base score dominant.
    diversity_bonus = min(0.1, (len(source_types) - 1) * 0.05)

    return min(1.0, base + diversity_bonus)
