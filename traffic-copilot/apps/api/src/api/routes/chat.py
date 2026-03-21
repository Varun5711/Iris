"""
Chat / Q&A endpoint — officers can ask free-form questions about an incident.

POST /chat/
    body: {incident_id: UUID, question: str, officer_id: str}
    1. Classify intent via nlp/intent_classifier
    2. Check if answerable without LLM (sensor_query + fresh Redis data)
    3. If yes: return direct answer
    4. If no: build chat context via context_builder.build_chat_context()
    5. Call copilot/llm_client.generate_chat_answer()
    6. Store in recommendations table as rec_type="chat"
    7. Log to audit_log (CHAT_QUESTION_ASKED)
    8. Return RecommendationOut
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.logging import get_logger
from src.db.session import get_db
from src.schemas.recommendation import CopilotResponse, RecommendationOut

logger = get_logger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


# ---------------------------------------------------------------------------
# Request schema
# ---------------------------------------------------------------------------


class ChatRequest(BaseModel):
    incident_id: UUID
    question: str
    officer_id: str = "anonymous"


# ---------------------------------------------------------------------------
# Intent classification (defensive — module may be a stub)
# ---------------------------------------------------------------------------


async def _classify_intent(question: str) -> str:
    """Return an intent label for the question. Falls back to 'general'."""
    try:
        from src.modules.nlp.intent_classifier import classify_intent  # type: ignore[import]
        result = classify_intent(question)
        return result.value if hasattr(result, "value") else str(result)
    except (ImportError, AttributeError):
        pass

    # Simple keyword-based fallback.
    q = question.lower()
    if any(kw in q for kw in ("speed", "sensor", "kmh", "mph", "flow", "occupancy")):
        return "sensor_query"
    if any(kw in q for kw in ("divert", "route", "alternative", "detour", "bypass")):
        return "diversion_query"
    if any(kw in q for kw in ("signal", "light", "phase", "green", "red", "timing")):
        return "signal_query"
    if any(kw in q for kw in ("status", "what's happening", "update", "latest")):
        return "status_query"
    return "general"


# ---------------------------------------------------------------------------
# Direct answer from Redis (no LLM hop)
# ---------------------------------------------------------------------------


async def _try_direct_answer(intent: str, incident_id: str, question: str) -> str | None:
    """
    For simple sensor queries, try to answer from Redis hot cache.
    Returns a plain-text answer or None if the question needs the LLM.
    """
    if intent not in ("sensor_query", "status_query"):
        return None

    try:
        from src.integrations.redis.client import cache_get, incident_snapshot_key

        snapshot = await cache_get(incident_snapshot_key(incident_id))
        if snapshot is None:
            return None

        if intent == "status_query":
            incident = snapshot.get("incident", {})
            return (
                f"Incident {incident_id} is currently {incident.get('status', 'unknown')} "
                f"(severity: {incident.get('severity', 'unknown')}). "
                f"Last updated: {snapshot.get('last_updated', 'unknown')}."
            )

        if intent == "sensor_query":
            segments = snapshot.get("affected_segments", [])
            if not segments:
                return "No sensor data available for this incident yet."
            seg = segments[0]
            return (
                f"Current congestion: {seg.get('congestion_pct', 0):.1f}%. "
                f"Estimated delay: {seg.get('delay_seconds', 0)}s on the most affected segment."
            )
    except Exception as exc:
        logger.debug("chat: direct answer attempt failed", error=str(exc))

    return None


# ---------------------------------------------------------------------------
# Context builder (defensive)
# ---------------------------------------------------------------------------


async def _build_chat_context(incident_id: str, question: str, intent: str, session, redis_client, groq_client) -> dict:
    try:
        from src.modules.context_builder.builder import build_chat_context
        return await build_chat_context(
            incident_id=incident_id,
            question=question,
            session=session,
            redis_client=redis_client,
            groq_client=groq_client,
        )
    except Exception as exc:
        logger.debug("chat: build_chat_context failed, using minimal context", error=str(exc))
        return {"incident_id": incident_id, "question": question, "intent": intent}


# ---------------------------------------------------------------------------
# LLM answer (defensive)
# ---------------------------------------------------------------------------


async def _generate_chat_answer(incident_id: str, question: str, context: dict, intent: str, groq_client, prompt_loader) -> str:
    # Try the module method first.
    try:
        from src.modules.copilot.llm_client import generate_chat_answer
        result = await generate_chat_answer(
            incident_id=incident_id,
            question=question,
            context=context,
            groq_client=groq_client,
            prompt_loader=prompt_loader,
            intent=intent,
        )
        if hasattr(result, "conversational_answer") and result.conversational_answer:
            return result.conversational_answer
        if hasattr(result, "model_dump"):
            result = result.model_dump()
        if isinstance(result, dict):
            return result.get("conversational_answer") or result.get("answer") or json.dumps(result, default=str)
        return str(result)
    except (ImportError, AttributeError):
        pass

    # Fall back to raw Groq call.
    try:
        from src.integrations.groq.client import call_copilot_safe

        system_prompt = (
            "You are TrafficCopilot, an expert traffic management assistant. "
            "Answer the officer's question concisely based on the incident context provided. "
            "Respond with a JSON object containing 'answer' (string)."
        )
        user_prompt = json.dumps(
            {"context": context, "question": question}, default=str
        )
        result = await call_copilot_safe(system_prompt, user_prompt)
        if result and isinstance(result, dict):
            return result.get("answer") or result.get("conversational_answer") or str(result)
    except Exception as exc:
        logger.warning("chat: Groq fallback failed", error=str(exc))

    return "I was unable to answer your question at this time. Please contact dispatch for assistance."


# ---------------------------------------------------------------------------
# POST /chat/
# ---------------------------------------------------------------------------


@router.post("/", response_model=RecommendationOut)
async def ask_question(
    body: ChatRequest,
    db: AsyncSession = Depends(get_db),
) -> RecommendationOut:
    """
    body: {incident_id: UUID, question: str, officer_id: str}
    1. Classify intent via nlp/intent_classifier
    2. Check if answerable without LLM (sensor_query + fresh Redis data)
    3. If yes: return direct answer
    4. If no: build chat context via context_builder.build_chat_context()
    5. Call copilot/llm_client.generate_chat_answer()
    6. Store in recommendations table as rec_type="chat"
    7. Log to audit_log (CHAT_QUESTION_ASKED)
    8. Return RecommendationOut
    """
    incident_id = str(body.incident_id)

    # Verify incident exists.
    chk = await db.execute(
        text("SELECT id FROM incidents WHERE id = :id"),
        {"id": incident_id},
    )
    if chk.fetchone() is None:
        raise HTTPException(status_code=404, detail=f"Incident {body.incident_id} not found")

    # ------------------------------------------------------------------ #
    # 1. Classify intent                                                  #
    # ------------------------------------------------------------------ #
    intent = await _classify_intent(body.question)
    logger.debug("chat: classified intent", intent=intent, incident_id=incident_id)

    # ------------------------------------------------------------------ #
    # 2. Try direct answer from Redis                                     #
    # ------------------------------------------------------------------ #
    direct = await _try_direct_answer(intent, incident_id, body.question)
    answer_text: str
    used_llm: bool

    if direct is not None:
        answer_text = direct
        used_llm = False
        logger.debug("chat: answered directly from cache", incident_id=incident_id)
    else:
        # ------------------------------------------------------------------ #
        # 3+4. Build chat context and call LLM                               #
        # ------------------------------------------------------------------ #
        # Fetch snapshot for context.
        snapshot: dict = {}
        try:
            from src.integrations.redis.client import cache_get, incident_snapshot_key
            cached = await cache_get(incident_snapshot_key(incident_id))
            if cached:
                snapshot = cached
        except Exception:
            pass

        from src.integrations.redis.client import get_redis
        from src.integrations.groq.client import get_groq_client
        import src.modules.copilot.prompt_loader as prompt_loader
        redis_client = await get_redis()
        groq_client = get_groq_client()

        chat_context = await _build_chat_context(incident_id, body.question, intent, db, redis_client, groq_client)
        answer_text = await _generate_chat_answer(incident_id, body.question, chat_context, intent, groq_client, prompt_loader)
        used_llm = "unable to answer" not in answer_text.lower()

    # ------------------------------------------------------------------ #
    # 5. Store recommendation with rec_type="chat"                        #
    # ------------------------------------------------------------------ #
    rec_id = str(uuid4())
    now = datetime.now(tz=timezone.utc)

    llm_blocked = not used_llm and direct is None  # Groq failed, not a cache hit
    copilot_response_json = json.dumps(
        {
            "incident_summary": f"Chat Q&A — intent: {intent}",
            "signal_actions": [],
            "diversion_plan": None,
            "alert_drafts": [],
            "narrative": "",
            "conversational_answer": answer_text,
            "overall_confidence": 0.8 if used_llm else 1.0,
            "review_required": False,
            "blocked_reason": "llm_unavailable" if llm_blocked else None,
            "evidence_refs": [],
        },
        default=str,
    )

    try:
        await db.execute(
            text(
                """
                INSERT INTO recommendations
                    (id, incident_id, rec_type, action, expected_impact, evidence_refs,
                     confidence, blocked_reason, review_required, status, created_at,
                     copilot_response)
                VALUES
                    (:id, :incident_id, 'chat', :action, NULL, CAST('[]' AS jsonb),
                     :confidence, :blocked_reason, false, 'pending', :now, CAST(:copilot_response AS jsonb))
                """
            ),
            {
                "id": rec_id,
                "incident_id": incident_id,
                "action": body.question[:500],
                "confidence": 0.8 if used_llm else 1.0,
                "blocked_reason": "llm_unavailable" if llm_blocked else None,
                "now": now,
                "copilot_response": copilot_response_json,
            },
        )
    except Exception as exc:
        logger.error("chat: failed to store recommendation", error=str(exc), exc_info=True)
        # Don't fail the request — still return the answer.
        await db.rollback()

    # ------------------------------------------------------------------ #
    # 6. Audit log                                                         #
    # ------------------------------------------------------------------ #
    try:
        await db.execute(
            text(
                """
                INSERT INTO audit_log (id, event_type, actor, payload, created_at)
                VALUES (:id, :event_type, :actor, CAST(:payload AS jsonb), :now)
                """
            ),
            {
                "id": str(uuid4()),
                "event_type": "CHAT_QUESTION_ASKED",
                "actor": body.officer_id,
                "payload": json.dumps(
                    {
                        "incident_id": incident_id,
                        "recommendation_id": rec_id,
                        "question": body.question,
                        "intent": intent,
                        "used_llm": used_llm,
                    },
                    default=str,
                ),
                "now": now,
            },
        )
        await db.commit()
    except Exception as exc:
        logger.warning("chat: audit log write failed", error=str(exc))

    logger.info(
        "chat: answered",
        incident_id=incident_id,
        intent=intent,
        used_llm=used_llm,
        officer_id=body.officer_id,
    )

    # ------------------------------------------------------------------ #
    # 7. Return RecommendationOut                                          #
    # ------------------------------------------------------------------ #
    copilot_response_obj = CopilotResponse.model_validate(json.loads(copilot_response_json))

    return RecommendationOut(
        id=UUID(rec_id),
        incident_id=body.incident_id,
        rec_type="chat",
        action=body.question[:500],
        location=None,
        expected_impact=answer_text,
        evidence_refs=[],
        confidence=0.8 if used_llm else 1.0,
        blocked_reason=None,
        review_required=False,
        status="pending",
        created_at=now,
        copilot_response=copilot_response_obj,
    )
