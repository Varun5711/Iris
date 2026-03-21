"""
Consumes from incident.state.updated.
For each message (IncidentSnapshot):
1. Build context via context_builder.build_recommendation_context()
2. Call copilot/llm_client.generate_recommendation()
3. Validate via policies/validator
4. Write recommendation to Postgres recommendations table
5. Write alert drafts to alerts table
6. Produce CopilotResponse JSON to recommendation.ready
7. Log to audit_log (LLM_CALLED or LLM_FALLBACK_USED)
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from src.core.logging import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Context builder (may be a stub — we call it defensively)
# ---------------------------------------------------------------------------


async def _build_context(incident_id: str, snapshot: dict, session, redis_client, groq_client) -> dict:
    """Call build_recommendation_context with correct args; fall back to snapshot."""
    try:
        from src.modules.context_builder.builder import build_recommendation_context
        return await build_recommendation_context(
            incident_id=incident_id,
            session=session,
            redis_client=redis_client,
            groq_client=groq_client,
        )
    except Exception as exc:
        logger.debug("copilot_trigger: context_builder failed, using snapshot fallback", error=str(exc))
        return snapshot


# ---------------------------------------------------------------------------
# LLM client (may be a stub — we call it defensively)
# ---------------------------------------------------------------------------


async def _generate_recommendation(incident_id: str, context: dict, groq_client, prompt_loader) -> dict | None:
    """Call llm_client.generate_recommendation with correct args; fall back to Groq directly."""
    try:
        from src.modules.copilot.llm_client import generate_recommendation
        result = await generate_recommendation(
            incident_id=incident_id,
            context=context,
            groq_client=groq_client,
            prompt_loader=prompt_loader,
        )
        # CopilotResponse dataclass → dict
        if hasattr(result, "model_dump"):
            return result.model_dump()
        return result
    except Exception as exc:
        logger.debug("copilot_trigger: llm_client failed, trying direct Groq", error=str(exc))

    # Fall back: call Groq directly with a minimal system prompt.
    try:
        from src.integrations.groq.client import call_copilot_safe

        incident = context.get("incident", context)
        system_prompt = (
            "You are TrafficCopilot, an AI assistant for traffic management officers. "
            "Analyse the incident context and respond with a JSON object containing: "
            "incident_summary (str), signal_actions (list), diversion_plan (object|null), "
            "alert_drafts (list), narrative (str), overall_confidence (float 0-1), "
            "review_required (bool), blocked_reason (str|null), evidence_refs (list), "
            "conversational_answer (str|null)."
        )
        user_prompt = json.dumps(context, default=str)
        result = await call_copilot_safe(system_prompt, user_prompt)
        return result
    except Exception as exc:
        logger.warning("copilot_trigger: Groq fallback also failed", error=str(exc))
        return None


# ---------------------------------------------------------------------------
# Policy validator (may be a stub)
# ---------------------------------------------------------------------------


def _validate(response_dict: dict) -> dict:
    """Run policy validation; return validated dict (possibly modified)."""
    try:
        from src.modules.policies.validator import validate_copilot_response
        from src.schemas.recommendation import CopilotResponse
        resp_obj = CopilotResponse(**response_dict) if not hasattr(response_dict, "model_dump") else response_dict
        validated = validate_copilot_response(resp_obj)
        return validated.model_dump() if hasattr(validated, "model_dump") else validated
    except Exception as exc:
        logger.debug("copilot_trigger: policy validation failed, returning raw", error=str(exc))
        return response_dict


# ---------------------------------------------------------------------------
# Audit logger (may be a stub)
# ---------------------------------------------------------------------------


async def _audit_log(session, incident_id: str, action: str, officer_id: str, details: dict) -> None:
    try:
        from src.modules.audit.logger import log_event
        await log_event(
            event_type=action,
            actor=officer_id,
            payload={"incident_id": incident_id, **details},
            session=session,
        )
    except Exception as exc:
        logger.warning("copilot_trigger: audit log write failed", error=str(exc))


# ---------------------------------------------------------------------------
# Fallback CopilotResponse when LLM unavailable
# ---------------------------------------------------------------------------


def _fallback_response(snapshot: dict) -> dict:
    incident = snapshot.get("incident", {})
    return {
        "incident_summary": (
            f"Incident detected (severity={incident.get('severity', 'unknown')}). "
            "LLM unavailable — manual review required."
        ),
        "signal_actions": [],
        "diversion_plan": None,
        "alert_drafts": [
            {
                "channel": "vms",
                "message": "INCIDENT AHEAD — USE CAUTION",
                "char_count": 27,
            }
        ],
        "narrative": "Automated LLM recommendation unavailable. Officer review required.",
        "overall_confidence": 0.0,
        "review_required": True,
        "blocked_reason": "LLM service unavailable — fallback response generated",
        "evidence_refs": [],
        "conversational_answer": None,
    }


# ---------------------------------------------------------------------------
# Main message handler
# ---------------------------------------------------------------------------


async def _handle_message(payload: dict[str, Any], topic: str) -> None:
    """Process a single incident.state.updated message."""
    from src.integrations.kafka.producer import publish
    from src.integrations.kafka.topics import RECOMMENDATION_READY
    from sqlalchemy import text

    snapshot = payload
    incident_data = snapshot.get("incident", {})
    incident_id = str(incident_data.get("id", ""))

    if not incident_id:
        logger.warning("copilot_trigger: snapshot missing incident.id, skipping")
        return

    incident_status = incident_data.get("status", "active")

    # Only trigger for active/monitoring incidents.
    if incident_status not in ("active", "monitoring"):
        logger.debug(
            "copilot_trigger: skipping non-actionable incident",
            incident_id=incident_id,
            status=incident_status,
        )
        return

    logger.info("copilot_trigger: processing incident", incident_id=incident_id)

    # ------------------------------------------------------------------ #
    # 1. Deps                                                              #
    # ------------------------------------------------------------------ #
    from src.db.session import AsyncSessionLocal
    from src.integrations.redis.client import get_redis
    from src.integrations.groq.client import get_groq_client
    import src.modules.copilot.prompt_loader as prompt_loader

    redis_client = await get_redis()
    groq_client = get_groq_client()

    # ------------------------------------------------------------------ #
    # 2. Build context                                                     #
    # ------------------------------------------------------------------ #
    async with AsyncSessionLocal() as ctx_session:
        context = await _build_context(incident_id, snapshot, ctx_session, redis_client, groq_client)

    # ------------------------------------------------------------------ #
    # 3. Call LLM                                                          #
    # ------------------------------------------------------------------ #
    llm_fallback_used = False
    raw_response = await _generate_recommendation(incident_id, context, groq_client, prompt_loader)

    if raw_response is None:
        raw_response = _fallback_response(snapshot)
        llm_fallback_used = True
        logger.warning("copilot_trigger: using fallback response", incident_id=incident_id)

    # ------------------------------------------------------------------ #
    # 3. Validate                                                          #
    # ------------------------------------------------------------------ #
    validated = _validate(raw_response)

    # ------------------------------------------------------------------ #
    # 4+5. Persist to DB                                                   #
    # ------------------------------------------------------------------ #
    async with AsyncSessionLocal() as session:
        recommendation_id = str(uuid4())
        alert_ids: list[str] = []
        now = datetime.now(tz=timezone.utc)

        # 4. Write recommendation record.
        try:
            await session.execute(
                text(
                    """
                    INSERT INTO recommendations
                        (id, incident_id, rec_type, action, expected_impact,
                         evidence_refs, confidence, blocked_reason, review_required,
                         status, prompt_snapshot, copilot_response, created_at)
                    VALUES
                        (:id, :incident_id, 'composite', :action, :expected_impact,
                         CAST(:evidence_refs AS jsonb), :confidence, :blocked_reason,
                         :review_required, 'pending', CAST(:prompt_snapshot AS jsonb),
                         CAST(:copilot_response AS jsonb), :now)
                    """
                ),
                {
                    "id": recommendation_id,
                    "incident_id": incident_id,
                    "action": validated.get("incident_summary", "See narrative for details"),
                    "expected_impact": validated.get("narrative", "")[:500],
                    "evidence_refs": json.dumps(validated.get("evidence_refs", []), default=str),
                    "confidence": validated.get("overall_confidence", 0.0),
                    "blocked_reason": validated.get("blocked_reason"),
                    "review_required": validated.get("review_required", True),
                    "now": now,
                    "prompt_snapshot": json.dumps({"context_keys": list(context.keys())}, default=str),
                    "copilot_response": json.dumps(validated, default=str),
                },
            )
        except Exception as exc:
            logger.error(
                "copilot_trigger: failed to write recommendation",
                incident_id=incident_id,
                error=str(exc),
                exc_info=True,
            )
            await session.rollback()
            return

        # 5. Write alert drafts.
        alert_drafts = validated.get("alert_drafts", [])
        for draft in alert_drafts:
            # LLM sometimes returns strings instead of {"channel":..., "message":...} dicts
            if isinstance(draft, str):
                draft = {"channel": "vms", "message": draft}
            elif not isinstance(draft, dict):
                continue
            alert_id = str(uuid4())
            alert_ids.append(alert_id)
            channel = draft.get("channel", "vms")
            message = draft.get("message", draft.get("text", str(draft)))
            try:
                await session.execute(
                    text(
                        """
                        INSERT INTO alerts
                            (id, recommendation_id, incident_id, channel, draft_text,
                             status, created_at)
                        VALUES
                            (:id, :recommendation_id, :incident_id, :channel,
                             :draft_text, 'draft', :now)
                        """
                    ),
                    {
                        "id": alert_id,
                        "recommendation_id": recommendation_id,
                        "incident_id": incident_id,
                        "channel": channel,
                        "draft_text": message,
                        "now": now,
                    },
                )
            except Exception as exc:
                logger.warning(
                    "copilot_trigger: failed to write alert draft",
                    alert_id=alert_id,
                    channel=channel,
                    error=str(exc),
                )

        # 7. Audit log.
        audit_action = "LLM_FALLBACK_USED" if llm_fallback_used else "LLM_CALLED"
        await _audit_log(
            session=session,
            incident_id=incident_id,
            action=audit_action,
            officer_id="system",
            details={
                "recommendation_id": recommendation_id,
                "model": "groq",
                "confidence": validated.get("overall_confidence", 0.0),
                "fallback": llm_fallback_used,
            },
        )

        await session.commit()

    # ------------------------------------------------------------------ #
    # 6. Publish to recommendation.ready                                   #
    # ------------------------------------------------------------------ #
    outgoing = {
        "recommendation_id": recommendation_id,
        "incident_id": incident_id,
        "status": "pending",
        "review_required": validated.get("review_required", True),
        "confidence": validated.get("overall_confidence", 0.0),
        "alert_ids": alert_ids,
        "copilot_response": validated,
        "created_at": now.isoformat(),
    }

    try:
        await publish(RECOMMENDATION_READY, outgoing, key=incident_id)
        logger.info(
            "copilot_trigger: published recommendation",
            recommendation_id=recommendation_id,
            incident_id=incident_id,
            fallback=llm_fallback_used,
        )
    except Exception as exc:
        logger.error(
            "copilot_trigger: failed to publish to recommendation.ready",
            incident_id=incident_id,
            error=str(exc),
            exc_info=True,
        )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


async def run_copilot_trigger() -> None:
    """Main consumer loop. Runs forever."""
    from src.core.config import settings
    from src.integrations.kafka.consumer import create_consumer, consume_messages
    from src.integrations.kafka.topics import INCIDENT_STATE_UPDATED

    logger.info("copilot_trigger starting up")

    consumer = await create_consumer(
        topics=[INCIDENT_STATE_UPDATED],
        group_id=f"{settings.kafka_consumer_group_id}-copilot-trigger",
        bootstrap_servers=settings.kafka_bootstrap_servers,
        auto_offset_reset="latest",
    )

    await consume_messages(consumer, _handle_message)
    logger.info("copilot_trigger shut down")
