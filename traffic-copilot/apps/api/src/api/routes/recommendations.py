"""
Recommendation endpoints — fetch, approve, and reject co-pilot recommendations.

GET  /recommendations/{incident_id}                  List recommendations for an incident
POST /recommendations/{recommendation_id}/approve    Officer approves a recommendation
POST /recommendations/{recommendation_id}/reject     Officer rejects a recommendation
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.logging import get_logger
from src.db.session import get_db
from src.schemas.alert import ApprovalOut, ApprovalRequest
from src.schemas.recommendation import CopilotResponse, RecommendationOut

logger = get_logger(__name__)

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _row_to_recommendation_out(row) -> RecommendationOut:
    """Convert a DB row mapping to RecommendationOut."""
    copilot_response: CopilotResponse | None = None
    raw_cr = row.get("copilot_response")
    if raw_cr:
        try:
            if isinstance(raw_cr, str):
                raw_cr = json.loads(raw_cr)
            copilot_response = CopilotResponse.model_validate(raw_cr)
        except Exception:
            pass

    evidence_refs = row.get("evidence_refs") or []
    if isinstance(evidence_refs, str):
        try:
            evidence_refs = json.loads(evidence_refs)
        except Exception:
            evidence_refs = []

    return RecommendationOut(
        id=row["id"],
        incident_id=row["incident_id"],
        rec_type=row.get("rec_type", "composite"),
        action=row.get("action", ""),
        location=row.get("location"),
        expected_impact=row.get("expected_impact"),
        evidence_refs=evidence_refs,
        confidence=row.get("confidence"),
        blocked_reason=row.get("blocked_reason"),
        review_required=row.get("review_required", True),
        status=row.get("status", "pending"),
        created_at=row["created_at"],
        copilot_response=copilot_response,
    )


async def _write_approval(
    db: AsyncSession,
    recommendation_id: str,
    incident_id: str,
    officer_id: str,
    action: str,
    note: str | None,
) -> ApprovalOut:
    """
    Within a single transaction:
    1. Update recommendation status.
    2. Insert approval record.
    3. Write audit log.
    Returns the persisted ApprovalOut.
    """
    approval_id = str(uuid4())
    now = datetime.now(tz=timezone.utc)

    # Update recommendation.
    await db.execute(
        text(
            """
            UPDATE recommendations
            SET status = :status, updated_at = :now
            WHERE id = :id
            """
        ),
        {"status": action, "now": now, "id": recommendation_id},
    )

    # Insert approval record.
    await db.execute(
        text(
            """
            INSERT INTO approvals
                (id, recommendation_id, officer_id, action, note, actioned_at)
            VALUES (:id, :recommendation_id, :officer_id, :action, :note, :now)
            """
        ),
        {
            "id": approval_id,
            "recommendation_id": recommendation_id,
            "officer_id": officer_id,
            "action": action,
            "note": note,
            "now": now,
        },
    )

    # Audit log.
    audit_action = (
        "RECOMMENDATION_APPROVED" if action == "approved" else "RECOMMENDATION_REJECTED"
    )
    await db.execute(
        text(
            """
            INSERT INTO audit_log
                (id, event_type, actor, payload, created_at)
            VALUES (:id, :event_type, :actor, CAST(:payload AS jsonb), :now)
            """
        ),
        {
            "id": str(uuid4()),
            "event_type": audit_action,
            "actor": officer_id,
            "payload": json.dumps(
                {"incident_id": incident_id, "recommendation_id": recommendation_id, "note": note}, default=str
            ),
            "now": now,
        },
    )

    await db.commit()

    return ApprovalOut(
        id=UUID(approval_id),
        recommendation_id=UUID(recommendation_id),
        officer_id=officer_id,
        action=action,  # type: ignore[arg-type]
        note=note,
        actioned_at=now,
    )


# ---------------------------------------------------------------------------
# GET /recommendations/{incident_id}
# ---------------------------------------------------------------------------


@router.get("/{incident_id}", response_model=list[RecommendationOut])
async def get_recommendations(
    incident_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> list[RecommendationOut]:
    """Return latest recommendations for incident, ordered by created_at desc."""
    result = await db.execute(
        text(
            """
            SELECT id, incident_id, rec_type, action, location, expected_impact,
                   evidence_refs, confidence, blocked_reason, review_required,
                   status, created_at, copilot_response
            FROM recommendations
            WHERE incident_id = :incident_id
            ORDER BY created_at DESC
            """
        ),
        {"incident_id": str(incident_id)},
    )
    rows = result.mappings().fetchall()
    return [_row_to_recommendation_out(row) for row in rows]


# ---------------------------------------------------------------------------
# POST /recommendations/{recommendation_id}/approve
# ---------------------------------------------------------------------------


@router.post(
    "/{recommendation_id}/approve",
    response_model=ApprovalOut,
    status_code=status.HTTP_200_OK,
)
async def approve_recommendation(
    recommendation_id: UUID,
    body: ApprovalRequest,
    db: AsyncSession = Depends(get_db),
) -> ApprovalOut:
    """
    1. Verify recommendation exists and status == pending
    2. Update status to approved
    3. Write to approvals table
    4. Write to audit_log (RECOMMENDATION_APPROVED)
    5. Publish to Kafka approval.actioned
    6. Return ApprovalOut
    Must be in single DB transaction (approval + audit_log together).
    """
    from src.integrations.kafka.producer import publish
    from src.integrations.kafka.topics import APPROVAL_ACTIONED

    rid = str(recommendation_id)

    # Fetch the recommendation.
    chk = await db.execute(
        text("SELECT id, incident_id, status FROM recommendations WHERE id = :id"),
        {"id": rid},
    )
    rec = chk.mappings().fetchone()
    if rec is None:
        raise HTTPException(status_code=404, detail=f"Recommendation {recommendation_id} not found")
    if rec["status"] != "pending":
        raise HTTPException(
            status_code=409,
            detail=f"Recommendation is not in 'pending' state (current: {rec['status']})",
        )

    incident_id = str(rec["incident_id"])
    approval_out = await _write_approval(
        db=db,
        recommendation_id=rid,
        incident_id=incident_id,
        officer_id=body.officer_id,
        action="approved",
        note=body.note,
    )

    # Publish to Kafka (best effort).
    try:
        await publish(
            APPROVAL_ACTIONED,
            {
                "approval_id": str(approval_out.id),
                "recommendation_id": rid,
                "incident_id": incident_id,
                "action": "approved",
                "officer_id": body.officer_id,
                "note": body.note,
                "actioned_at": approval_out.actioned_at.isoformat(),
            },
            key=incident_id,
        )
    except Exception as exc:
        logger.warning("recommendations: Kafka publish failed (non-fatal)", error=str(exc))

    logger.info(
        "recommendations: approved",
        recommendation_id=rid,
        incident_id=incident_id,
        officer_id=body.officer_id,
    )
    return approval_out


# ---------------------------------------------------------------------------
# POST /recommendations/{recommendation_id}/reject
# ---------------------------------------------------------------------------


@router.post(
    "/{recommendation_id}/reject",
    response_model=ApprovalOut,
    status_code=status.HTTP_200_OK,
)
async def reject_recommendation(
    recommendation_id: UUID,
    body: ApprovalRequest,
    db: AsyncSession = Depends(get_db),
) -> ApprovalOut:
    """Same as approve but action=rejected."""
    from src.integrations.kafka.producer import publish
    from src.integrations.kafka.topics import APPROVAL_ACTIONED

    rid = str(recommendation_id)

    chk = await db.execute(
        text("SELECT id, incident_id, status FROM recommendations WHERE id = :id"),
        {"id": rid},
    )
    rec = chk.mappings().fetchone()
    if rec is None:
        raise HTTPException(status_code=404, detail=f"Recommendation {recommendation_id} not found")
    if rec["status"] != "pending":
        raise HTTPException(
            status_code=409,
            detail=f"Recommendation is not in 'pending' state (current: {rec['status']})",
        )

    incident_id = str(rec["incident_id"])
    approval_out = await _write_approval(
        db=db,
        recommendation_id=rid,
        incident_id=incident_id,
        officer_id=body.officer_id,
        action="rejected",
        note=body.note,
    )

    # Publish to Kafka (best effort).
    try:
        await publish(
            APPROVAL_ACTIONED,
            {
                "approval_id": str(approval_out.id),
                "recommendation_id": rid,
                "incident_id": incident_id,
                "action": "rejected",
                "officer_id": body.officer_id,
                "note": body.note,
                "actioned_at": approval_out.actioned_at.isoformat(),
            },
            key=incident_id,
        )
    except Exception as exc:
        logger.warning("recommendations: Kafka publish failed (non-fatal)", error=str(exc))

    logger.info(
        "recommendations: rejected",
        recommendation_id=rid,
        incident_id=incident_id,
        officer_id=body.officer_id,
    )
    return approval_out
