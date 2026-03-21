"""
LLM client orchestrator for the TrafficCopilot co-pilot.

Responsibilities:
  - Load prompt templates from disk via prompt_loader.
  - Build the user message by injecting formatted context.
  - Call Groq via call_copilot_safe (never raises).
  - Parse the raw dict into a validated CopilotResponse.
  - Run policy validation on every response.
  - Return a deterministic fallback when the LLM is unavailable.
"""

from __future__ import annotations

import logging
from typing import Any

from src.modules.context_builder.builder import format_context_for_prompt
from src.modules.policies.validator import validate_copilot_response
from src.schemas.recommendation import (
    AlertDraft,
    CopilotResponse,
    DiversionPlan,
    SignalAction,
)

logger = logging.getLogger(__name__)

# Overall confidence below which review is always required.
_MIN_CONFIDENCE = 0.4


# ---------------------------------------------------------------------------
# Parse helpers
# ---------------------------------------------------------------------------


def _parse_signal_actions(raw: Any) -> list[SignalAction]:
    """Safely parse a list of signal action dicts from LLM output."""
    if not isinstance(raw, list):
        return []
    actions = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        try:
            actions.append(
                SignalAction(
                    intersection_id=str(item.get("intersection_id", "unknown")),
                    action=str(item.get("action", "")),
                    expected_impact=str(item.get("expected_impact", "")),
                    confidence=float(item.get("confidence", 0.5)),
                )
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("_parse_signal_actions: skipping malformed item %s — %s", item, exc)
    return actions


def _parse_diversion_plan(raw: Any) -> DiversionPlan | None:
    """Safely parse a diversion plan dict from LLM output."""
    if not isinstance(raw, dict) or not raw:
        return None
    try:
        return DiversionPlan(
            route_description=str(raw.get("route_description", "")),
            estimated_extra_minutes=float(raw.get("estimated_extra_minutes", 0.0)),
            traffic_redistribution_pct=float(raw.get("traffic_redistribution_pct", 0.0)),
            confidence=float(raw.get("confidence", 0.5)),
            evidence_refs=list(raw.get("evidence_refs") or []),
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("_parse_diversion_plan: parse failed — %s", exc)
        return None


def _parse_alert_drafts(raw: Any) -> list[AlertDraft]:
    """Safely parse alert draft dicts from LLM output."""
    if not isinstance(raw, list):
        return []
    drafts = []
    valid_channels = {"vms", "radio", "social"}
    for item in raw:
        if not isinstance(item, dict):
            continue
        channel = str(item.get("channel", "")).lower()
        if channel not in valid_channels:
            continue
        try:
            drafts.append(
                AlertDraft(
                    channel=channel,  # type: ignore[arg-type]
                    message=str(item.get("message", "")),
                )
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("_parse_alert_drafts: skipping item %s — %s", item, exc)
    return drafts


def _parse_copilot_response(raw: dict, incident_id: str) -> CopilotResponse:
    """
    Convert a raw LLM dict into a :class:`CopilotResponse`.

    Falls back to safe defaults for any missing or malformed field.
    """
    return CopilotResponse(
        incident_summary=str(raw.get("incident_summary", f"Incident {incident_id} is active.")),
        signal_actions=_parse_signal_actions(raw.get("signal_actions")),
        diversion_plan=_parse_diversion_plan(raw.get("diversion_plan")),
        alert_drafts=_parse_alert_drafts(raw.get("alert_drafts")),
        narrative=str(raw.get("narrative", "")),
        conversational_answer=raw.get("conversational_answer") or None,
        overall_confidence=float(raw.get("overall_confidence", _MIN_CONFIDENCE)),
        review_required=bool(raw.get("review_required", True)),
        blocked_reason=raw.get("blocked_reason") or None,
        evidence_refs=list(raw.get("evidence_refs") or []),
    )


# ---------------------------------------------------------------------------
# Main public functions
# ---------------------------------------------------------------------------


async def generate_recommendation(
    incident_id: str,
    context: dict,
    groq_client: Any,
    prompt_loader: Any,
) -> CopilotResponse:
    """
    Generate a full incident recommendation from the LLM.

    Steps:
    1. Load ``officer_copilot`` system prompt.
    2. Load task prompts: ``summarize_incident``, ``generate_signal_plan``,
       ``generate_diversion``, ``generate_alert_drafts``.
    3. Build user message from formatted context.
    4. Call Groq with ``json_object`` response format.
    5. Parse raw dict into :class:`CopilotResponse`.
    6. Validate with policy rules.
    7. Return validated response (or deterministic fallback on failure).

    Parameters
    ----------
    incident_id:
        UUID of the incident being analysed.
    context:
        Dict produced by :func:`~src.modules.context_builder.builder.build_recommendation_context`.
    groq_client:
        AsyncGroq client instance.
    prompt_loader:
        Module reference for :mod:`src.modules.copilot.prompt_loader`.

    Returns
    -------
    CopilotResponse
        Validated recommendation, with ``review_required=True`` and
        ``blocked_reason`` set if the LLM was unavailable.
    """
    from src.integrations.groq.client import call_copilot_safe

    # ---- 1. Load prompts ---------------------------------------------------
    try:
        system_prompt = prompt_loader.load_system_prompt("officer_copilot")
    except FileNotFoundError:
        logger.warning("officer_copilot system prompt not found — using inline default")
        system_prompt = (
            "You are an advisory traffic co-pilot. "
            "Respond with valid JSON only. Never issue direct signal commands."
        )

    task_sections: list[str] = []
    for task_name in (
        "summarize_incident",
        "generate_signal_plan",
        "generate_diversion",
        "generate_alert_drafts",
    ):
        try:
            tmpl = prompt_loader.load_task_prompt(task_name)
            task_sections.append(tmpl)
        except FileNotFoundError:
            logger.warning("Task prompt '%s' not found — skipping", task_name)

    # ---- 2. Build user message ---------------------------------------------
    context_str = format_context_for_prompt(context)
    combined_tasks = "\n\n---\n\n".join(task_sections)
    user_message = (
        f"{combined_tasks}\n\n"
        f"=== CONTEXT ===\n{context_str}\n\n"
        f"incident_id: {incident_id}\n\n"
        "Respond with a SINGLE JSON object covering ALL fields of the CopilotResponse schema."
    )

    # ---- 3. Call LLM -------------------------------------------------------
    raw = await call_copilot_safe(system_prompt, user_message)

    if raw is None:
        logger.warning(
            "generate_recommendation: LLM unavailable for incident=%s — using fallback",
            incident_id,
        )
        return build_deterministic_fallback(incident_id, context)

    # ---- 4. Parse & validate -----------------------------------------------
    try:
        response = _parse_copilot_response(raw, incident_id)
    except Exception as exc:  # noqa: BLE001
        logger.error("generate_recommendation: parse error — %s — using fallback", exc)
        return build_deterministic_fallback(incident_id, context)

    validated = validate_copilot_response(response)
    logger.info(
        "generate_recommendation: incident=%s confidence=%.2f review_required=%s",
        incident_id,
        validated.overall_confidence,
        validated.review_required,
    )
    return validated


async def generate_chat_answer(
    incident_id: str,
    question: str,
    context: dict,
    groq_client: Any,
    prompt_loader: Any,
    intent: str = "general",
) -> CopilotResponse:
    """
    Generate a conversational answer to an officer's follow-up question.

    The primary populated field is ``conversational_answer``.
    ``evidence_refs``, ``overall_confidence``, and ``review_required`` are
    also populated as appropriate.

    Parameters
    ----------
    incident_id:
        UUID of the incident in context.
    question:
        Free-text officer question.
    context:
        Dict produced by :func:`~src.modules.context_builder.builder.build_chat_context`.
    groq_client:
        AsyncGroq client instance.
    prompt_loader:
        Module reference for :mod:`src.modules.copilot.prompt_loader`.
    intent:
        Classified question intent (e.g. ``"general"``, ``"signal"``, ``"alert"``).
        Currently used only for logging.

    Returns
    -------
    CopilotResponse
        Response with ``conversational_answer`` populated.
    """
    from src.integrations.groq.client import call_copilot_safe

    # ---- Load prompts -------------------------------------------------------
    try:
        system_prompt = prompt_loader.load_system_prompt("officer_copilot")
    except FileNotFoundError:
        system_prompt = (
            "You are an advisory traffic co-pilot. "
            "Answer the officer's question concisely using the provided context. "
            "Respond with valid JSON only."
        )

    try:
        task_tmpl = prompt_loader.load_task_prompt("answer_question")
        task_prompt = prompt_loader.format_prompt(task_tmpl, question=question, context="")
    except (FileNotFoundError, KeyError):
        task_prompt = f'Answer the officer question: "{question}"'

    # ---- Build user message -------------------------------------------------
    context_str = format_context_for_prompt(context)
    user_message = (
        f"{task_prompt}\n\n"
        f"=== CONTEXT ===\n{context_str}\n\n"
        f"incident_id: {incident_id}\n"
        f"intent: {intent}\n\n"
        "Return a JSON object with at minimum: "
        "conversational_answer, evidence_refs, overall_confidence, review_required. "
        "Also include incident_summary and narrative with brief values."
    )

    # ---- Call LLM -----------------------------------------------------------
    raw = await call_copilot_safe(system_prompt, user_message)

    if raw is None:
        logger.warning(
            "generate_chat_answer: LLM unavailable for incident=%s question=%r",
            incident_id,
            question[:80],
        )
        fallback = build_deterministic_fallback(incident_id, context)
        return CopilotResponse(
            incident_summary=fallback.incident_summary,
            signal_actions=[],
            diversion_plan=None,
            alert_drafts=[],
            narrative=fallback.narrative,
            conversational_answer=(
                "The AI co-pilot is temporarily unavailable. "
                "Please consult current sensor data and SOPs directly."
            ),
            overall_confidence=0.0,
            review_required=True,
            blocked_reason="llm_unavailable",
            evidence_refs=[],
        )

    # ---- Parse & validate ---------------------------------------------------
    try:
        response = _parse_copilot_response(raw, incident_id)
    except Exception as exc:  # noqa: BLE001
        logger.error("generate_chat_answer: parse error — %s", exc)
        return CopilotResponse(
            incident_summary=f"Incident {incident_id} is active.",
            narrative="Unable to parse LLM response.",
            conversational_answer="Unable to parse response from the AI co-pilot.",
            overall_confidence=0.0,
            review_required=True,
            blocked_reason="parse_error",
            evidence_refs=[],
        )

    validated = validate_copilot_response(response)
    logger.info(
        "generate_chat_answer: incident=%s intent=%s confidence=%.2f",
        incident_id,
        intent,
        validated.overall_confidence,
    )
    return validated


# ---------------------------------------------------------------------------
# Deterministic fallback
# ---------------------------------------------------------------------------


def build_deterministic_fallback(incident_id: str, context: dict) -> CopilotResponse:
    """
    Build a :class:`CopilotResponse` from deterministic logic only (no LLM).

    Used when Groq is unavailable.  The fallback extracts what it can from the
    context dict and produces conservative advisory outputs with
    ``review_required=True`` and ``blocked_reason="llm_unavailable"``.

    Parameters
    ----------
    incident_id:
        UUID of the incident.
    context:
        Context dict from the builder module.

    Returns
    -------
    CopilotResponse
        A safe, low-confidence response marked for mandatory officer review.
    """
    incident_state = context.get("incident_state", {})
    incident = incident_state.get("incident", {})

    severity = incident.get("severity", "unknown")
    status = incident.get("status", "unknown")
    corridor = incident.get("corridor_id") or "unknown corridor"
    description = incident.get("description") or "No description available."
    created_at = incident.get("created_at", "unknown time")

    incident_summary = (
        f"Incident {incident_id} is currently {status} with {severity} severity "
        f"on {corridor}. Reported at {created_at}. {description}"
    )

    # ---- Signal actions from cached signal plan ----------------------------
    signal_actions: list[SignalAction] = []
    raw_signal_plan = context.get("signal_plan")
    if isinstance(raw_signal_plan, dict):
        candidates = raw_signal_plan.get("candidates") or raw_signal_plan.get("signal_actions") or []
        for candidate in candidates[:5]:
            if not isinstance(candidate, dict):
                continue
            try:
                signal_actions.append(
                    SignalAction(
                        intersection_id=str(candidate.get("intersection_id", "unknown")),
                        action=(
                            f"Suggest reviewing signal timing at intersection "
                            f"{candidate.get('intersection_id', 'unknown')} "
                            f"— {candidate.get('rationale', 'assess current plan')}"
                        ),
                        expected_impact="Potential queue reduction on affected approach.",
                        confidence=0.4,
                    )
                )
            except Exception:  # noqa: BLE001
                pass

    # ---- Diversion plan from cached routing --------------------------------
    diversion_plan: DiversionPlan | None = None
    raw_diversion = context.get("diversion")
    if isinstance(raw_diversion, dict) and raw_diversion:
        try:
            diversion_plan = DiversionPlan(
                route_description=(
                    raw_diversion.get("route_description")
                    or "Alternative route available — please verify with current data."
                ),
                estimated_extra_minutes=float(raw_diversion.get("extra_minutes", 5.0)),
                traffic_redistribution_pct=float(
                    raw_diversion.get("redistribution_pct", 20.0)
                ),
                confidence=0.4,
                evidence_refs=["routing_cache"],
            )
        except Exception:  # noqa: BLE001
            pass

    # ---- Alert drafts from alert templates ---------------------------------
    alert_drafts: list[AlertDraft] = []
    alert_templates = context.get("alert_templates") or []
    seen_channels: set[str] = set()
    for tmpl in alert_templates:
        channel = (tmpl.get("channel") or "").lower()
        if channel in seen_channels or channel not in {"vms", "radio", "social"}:
            continue
        seen_channels.add(channel)
        try:
            alert_drafts.append(
                AlertDraft(
                    channel=channel,  # type: ignore[arg-type]
                    message=(
                        tmpl.get("template_text")
                        or f"TRAFFIC ADVISORY: Incident on {corridor}. Follow officer instructions."
                    ),
                )
            )
        except Exception:  # noqa: BLE001
            pass

    # Fill missing channels with minimal placeholders.
    for channel in ("vms", "radio", "social"):
        if channel not in seen_channels:
            try:
                if channel == "vms":
                    msg = f"INCIDENT {corridor[:30].upper()}. EXPECT DELAYS. FOLLOW SIGNS."
                elif channel == "radio":
                    msg = (
                        f"Attention drivers: an incident on {corridor} is causing delays. "
                        "Use alternate routes where possible."
                    )
                else:
                    msg = (
                        f"TRAFFIC ADVISORY: Incident reported on {corridor}. "
                        "Delays expected. #TrafficAlert"
                    )
                alert_drafts.append(AlertDraft(channel=channel, message=msg))  # type: ignore[arg-type]
            except Exception:  # noqa: BLE001
                pass

    narrative = (
        f"This response was generated by the deterministic fallback because the "
        f"AI co-pilot (Groq) was unavailable. "
        f"Incident {incident_id} ({severity} severity, {status}) on {corridor}. "
        f"All recommendations require officer verification before any action is taken."
    )

    return CopilotResponse(
        incident_summary=incident_summary,
        signal_actions=signal_actions,
        diversion_plan=diversion_plan,
        alert_drafts=alert_drafts,
        narrative=narrative,
        conversational_answer=None,
        overall_confidence=0.3,
        review_required=True,
        blocked_reason="llm_unavailable",
        evidence_refs=["deterministic_fallback"],
    )
