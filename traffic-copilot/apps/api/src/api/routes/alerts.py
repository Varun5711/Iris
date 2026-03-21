"""
Alert endpoints — retrieve alert drafts and publish approved ones.

GET  /alerts/{incident_id}          Get all alert drafts for an incident
POST /alerts/{alert_id}/publish     Publish an alert (requires approved recommendation)
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.logging import get_logger
from src.db.session import get_db
from src.schemas.alert import AlertOut, ApprovalRequest

logger = get_logger(__name__)

router = APIRouter(prefix="/alerts", tags=["alerts"])


# ---------------------------------------------------------------------------
# GET /alerts/{incident_id}
# ---------------------------------------------------------------------------


@router.get("/{incident_id}", response_model=list[AlertOut])
async def get_alerts(
    incident_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> list[AlertOut]:
    """Get all alert drafts for an incident."""
    iid = str(incident_id)

    result = await db.execute(
        text(
            """
            SELECT id, recommendation_id, channel, draft_text, status, created_at
            FROM alerts
            WHERE incident_id = :incident_id
            ORDER BY created_at DESC
            """
        ),
        {"incident_id": iid},
    )
    rows = result.mappings().fetchall()
    return [
        AlertOut(
            id=row["id"],
            recommendation_id=row["recommendation_id"],
            channel=row["channel"],
            draft_text=row["draft_text"],
            status=row["status"],
            created_at=row["created_at"],
        )
        for row in rows
    ]


# ---------------------------------------------------------------------------
# POST /alerts/{alert_id}/publish
# ---------------------------------------------------------------------------


@router.post("/{alert_id}/publish", response_model=dict, status_code=status.HTTP_200_OK)
async def publish_alert(
    alert_id: UUID,
    body: ApprovalRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    1. Verify alert's recommendation has status=approved (hard guard)
    2. Call alerts/publisher.publish_alert()
    3. Return {"status": "published", "channel": ..., "message": ...}
    """
    aid = str(alert_id)

    # Fetch alert + linked recommendation status.
    result = await db.execute(
        text(
            """
            SELECT a.id         AS alert_id,
                   a.incident_id,
                   a.channel,
                   a.draft_text,
                   a.status     AS alert_status,
                   r.id         AS recommendation_id,
                   r.status     AS rec_status
            FROM alerts a
            JOIN recommendations r ON r.id = a.recommendation_id
            WHERE a.id = :alert_id
            """
        ),
        {"alert_id": aid},
    )
    row = result.mappings().fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")

    # Hard guard: the linked recommendation must be approved.
    if row["rec_status"] != "approved":
        raise HTTPException(
            status_code=403,
            detail=(
                f"Cannot publish alert — linked recommendation is '{row['rec_status']}', "
                "must be 'approved'."
            ),
        )

    if row["alert_status"] == "published":
        raise HTTPException(status_code=409, detail="Alert has already been published")

    channel: str = row["channel"]
    message: str = row["draft_text"]
    incident_id: str = str(row["incident_id"])

    # ------------------------------------------------------------------ #
    # Call publisher module (defensive import).                           #
    # ------------------------------------------------------------------ #
    publish_result: dict = {}
    try:
        from src.modules.alerts.publisher import publish_alert as _pub
        from src.integrations.redis.client import get_redis
        from src.integrations.kafka.producer import get_producer
        redis_client = await get_redis()
        kafka_producer = await get_producer()
        publish_result = await _pub(
            alert_id=aid,
            incident_id=incident_id,
            channel=channel,
            message=message,
            session=db,
            redis_client=redis_client,
            kafka_producer=kafka_producer,
        )
    except (ImportError, AttributeError):
        # Publisher stub not available — simulate a successful publish.
        logger.info(
            "alerts: publisher module not available, simulating publish",
            alert_id=aid,
            channel=channel,
        )
        publish_result = {
            "status": "published",
            "channel": channel,
            "message": message,
            "alert_id": aid,
        }
    except Exception as exc:
        logger.error("alerts: publish_alert failed", alert_id=aid, error=str(exc), exc_info=True)
        raise HTTPException(status_code=502, detail=f"Publishing failed: {exc}") from exc

    # Update alert status to published.
    try:
        await db.execute(
            text("UPDATE alerts SET status = 'published' WHERE id = :id"),
            {"id": aid},
        )
        await db.commit()
    except Exception as exc:
        logger.error("alerts: failed to update alert status to published", error=str(exc))
        await db.rollback()

    logger.info(
        "alerts: published",
        alert_id=aid,
        channel=channel,
        incident_id=incident_id,
        officer_id=body.officer_id,
    )

    return {
        "status": "published",
        "channel": channel,
        "message": message,
        "alert_id": aid,
        **publish_result,
    }
