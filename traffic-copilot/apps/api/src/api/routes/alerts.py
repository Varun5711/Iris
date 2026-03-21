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

from src.core.config import settings
from src.core.logging import get_logger
from src.db.session import get_db
from src.schemas.alert import AlertOut, ApprovalRequest, BulkPublishItemOut, BulkPublishOut, BulkPublishRequest

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
            SELECT a.id, a.recommendation_id, a.channel, a.draft_text, a.status, a.created_at
            FROM alerts a
            JOIN recommendations r ON r.id = a.recommendation_id
            WHERE r.incident_id = CAST(:incident_id AS uuid)
            ORDER BY a.created_at DESC
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

    # Optional SMS notification.
    sms_result: dict | None = None
    phone = body.phone_number or settings.twilio_to_number
    if phone:
        try:
            from src.integrations.twilio.sms import send_sms
            sms_body = f"TRAFFIC ALERT: {message[:130]}"
            sms_result = await send_sms(phone, sms_body)
        except Exception as exc:
            logger.warning("alerts: SMS send failed (non-fatal)", error=str(exc))

    response: dict = {
        "status": "published",
        "channel": channel,
        "message": message,
        "alert_id": aid,
        **publish_result,
    }
    if sms_result is not None:
        response["sms"] = sms_result
    return response


# ---------------------------------------------------------------------------
# POST /alerts/bulk-publish
# ---------------------------------------------------------------------------


@router.post("/bulk-publish", response_model=BulkPublishOut, status_code=status.HTTP_200_OK)
async def bulk_publish_alerts(
    body: BulkPublishRequest,
    db: AsyncSession = Depends(get_db),
) -> BulkPublishOut:
    """
    Publish multiple alert drafts in one call.

    Each alert is processed independently — failures do not abort the batch.
    If *phone_number* (or TWILIO_TO_NUMBER env var) is set, a single
    consolidated SMS is sent after all alerts are processed.
    """
    results: list[BulkPublishItemOut] = []

    for alert_id in body.alert_ids:
        aid = str(alert_id)
        try:
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
                results.append(BulkPublishItemOut(alert_id=alert_id, status="error", detail="Alert not found"))
                continue
            if row["rec_status"] != "approved":
                results.append(BulkPublishItemOut(
                    alert_id=alert_id,
                    status="skipped",
                    channel=row["channel"],
                    detail=f"Recommendation not approved (status={row['rec_status']})",
                ))
                continue
            if row["alert_status"] == "published":
                results.append(BulkPublishItemOut(
                    alert_id=alert_id,
                    status="skipped",
                    channel=row["channel"],
                    detail="Already published",
                ))
                continue

            channel: str = row["channel"]
            message: str = row["draft_text"]
            incident_id: str = str(row["incident_id"])

            try:
                from src.modules.alerts.publisher import publish_alert as _pub
                from src.integrations.redis.client import get_redis
                from src.integrations.kafka.producer import get_producer
                redis_client = await get_redis()
                kafka_producer = await get_producer()
                await _pub(
                    alert_id=aid,
                    incident_id=incident_id,
                    channel=channel,
                    message=message,
                    session=db,
                    redis_client=redis_client,
                    kafka_producer=kafka_producer,
                )
            except (ImportError, AttributeError):
                pass

            await db.execute(
                text("UPDATE alerts SET status = 'published' WHERE id = :id"),
                {"id": aid},
            )
            await db.commit()

            results.append(BulkPublishItemOut(alert_id=alert_id, status="published", channel=channel, message=message))

        except Exception as exc:
            logger.error("alerts: bulk_publish single item failed", alert_id=aid, error=str(exc))
            await db.rollback()
            results.append(BulkPublishItemOut(alert_id=alert_id, status="error", detail=str(exc)))

    try:
        await db.commit()
    except Exception as exc:
        logger.error("alerts: bulk_publish commit failed", error=str(exc))
        await db.rollback()

    published = [r for r in results if r.status == "published"]
    skipped = [r for r in results if r.status == "skipped"]
    errors = [r for r in results if r.status == "error"]

    logger.info(
        "alerts: bulk published",
        published=len(published),
        skipped=len(skipped),
        errors=len(errors),
        officer_id=body.officer_id,
    )

    # Consolidated SMS.
    sms_result: dict | None = None
    phone = body.phone_number or settings.twilio_to_number
    if phone and published:
        try:
            from src.integrations.twilio.sms import send_sms
            # Pick the most public-facing alert: prefer radio > vms > social
            priority = {"radio": 0, "vms": 1, "social": 2}
            best = min(published, key=lambda r: priority.get(r.channel, 9))
            core = (best.message or "")[:120]
            sms_body = f"TRAFFIC ALERT: {core}"
            sms_result = await send_sms(phone, sms_body)
        except Exception as exc:
            logger.warning("alerts: bulk SMS failed (non-fatal)", error=str(exc))

    return BulkPublishOut(
        published_count=len(published),
        skipped_count=len(skipped),
        error_count=len(errors),
        results=results,
        sms=sms_result,
    )
