"""
Audit trail logger for TrafficCopilot.

All audit writes go to the ``audit_log`` table (append-only).
Functions are async and accept an SQLAlchemy ``AsyncSession``.

Event types (non-exhaustive):
  INCIDENT_CREATED, EVENT_INGESTED, RECOMMENDATION_GENERATED,
  RECOMMENDATION_APPROVED, RECOMMENDATION_REJECTED, ALERT_PUBLISHED,
  CHAT_QUESTION_ASKED, LLM_CALLED, LLM_FALLBACK_USED
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def log_event(
    event_type: str,
    actor: str | None,
    payload: dict[str, Any],
    session: AsyncSession,
) -> None:
    """
    Write a single audit-log row to the ``audit_log`` table.

    Parameters
    ----------
    event_type:
        Short uppercase string identifying the event, e.g. ``"INCIDENT_CREATED"``.
    actor:
        Officer badge number, system service name, or ``None`` if actor is unknown.
    payload:
        Arbitrary JSON-serialisable dict with event-specific data.
    session:
        Active SQLAlchemy async session.  The caller is responsible for the
        surrounding transaction; this function calls ``flush()`` (not ``commit()``)
        so the row is written in the current transaction unit.

    Notes
    -----
    Failures are logged but never propagated — audit logging must never break
    the primary request path.
    """
    try:
        await session.execute(
            text(
                """
                INSERT INTO audit_log (event_type, actor, payload)
                VALUES (:event_type, :actor, CAST(:payload AS jsonb))
                """
            ),
            {
                "event_type": event_type,
                "actor": actor,
                "payload": _to_jsonb_string(payload),
            },
        )
        await session.flush()
        logger.debug("audit_log: event_type=%s actor=%s", event_type, actor)
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "audit log_event failed — event_type=%s actor=%s error=%s",
            event_type,
            actor,
            exc,
        )


async def log_llm_call(
    incident_id: str,
    prompt_tokens: int,
    completion_tokens: int,
    model: str,
    latency_ms: float,
    session: AsyncSession,
) -> None:
    """
    Record LLM call metrics to the audit log.

    Parameters
    ----------
    incident_id:
        UUID string of the incident for which the LLM was called.
    prompt_tokens:
        Number of tokens in the prompt (from the API response usage object).
    completion_tokens:
        Number of tokens in the completion.
    model:
        Model identifier string, e.g. ``"llama-3.3-70b-versatile"``.
    latency_ms:
        Wall-clock latency of the API call in milliseconds.
    session:
        Active SQLAlchemy async session.
    """
    await log_event(
        event_type="LLM_CALLED",
        actor="system",
        payload={
            "incident_id": incident_id,
            "model": model,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
            "latency_ms": round(latency_ms, 2),
        },
        session=session,
    )


async def log_approval(
    recommendation_id: str,
    officer_id: str,
    action: str,
    note: str | None,
    session: AsyncSession,
) -> None:
    """
    Record an officer approval or rejection action to the audit log.

    Parameters
    ----------
    recommendation_id:
        UUID string of the recommendation being acted upon.
    officer_id:
        Badge number or user ID of the officer.
    action:
        One of ``"approved"`` or ``"rejected"``.
    note:
        Optional free-text justification or modification note.
    session:
        Active SQLAlchemy async session.
    """
    event_type = (
        "RECOMMENDATION_APPROVED" if action == "approved" else "RECOMMENDATION_REJECTED"
    )
    await log_event(
        event_type=event_type,
        actor=officer_id,
        payload={
            "recommendation_id": recommendation_id,
            "action": action,
            "note": note,
        },
        session=session,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _to_jsonb_string(payload: dict[str, Any]) -> str:
    """
    Serialise *payload* to a JSON string suitable for PostgreSQL's ``::jsonb`` cast.

    Non-serialisable values are converted to their ``repr()`` string so the
    cast never fails.
    """
    import json

    def _default(obj: Any) -> str:
        return repr(obj)

    return json.dumps(payload, default=_default, ensure_ascii=False)
