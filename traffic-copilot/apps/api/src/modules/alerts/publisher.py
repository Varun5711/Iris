"""
Alert publisher — post-approval only.

GUARD: Every publish path verifies that the parent recommendation has
``status == 'approved'`` before writing anything.  If the guard fails the
function raises ``PermissionError`` so the API layer can return HTTP 403.

Mock channel dispatch:
  vms    — structlog INFO with VMS-board formatting
  radio  — structlog INFO with radio-broadcast formatting
  social — structlog INFO with social-media formatting

In production these stubs would be replaced by real NTCIP / broadcast / API
integrations.
"""

from __future__ import annotations

import json
import logging

import structlog

from src.modules.audit.logger import log_event

logger = structlog.get_logger(__name__)
_stdlib_logger = logging.getLogger(__name__)

# Kafka topic for approval actioned events.
_KAFKA_TOPIC = "approval.actioned"


async def publish_alert(
    alert_id: str,
    channel: str,
    message: str,
    incident_id: str,
    session,
    redis_client,
    kafka_producer,
) -> dict:
    """
    Publish an approved alert to its target channel.

    Guard
    -----
    Queries the ``alerts`` table to find the parent ``recommendation_id``,
    then calls :func:`check_approval_guard` to verify the recommendation is
    approved.  Raises :exc:`PermissionError` if it is not.

    Steps after guard passes:
    1. Log to structlog with channel + message + incident_id.
    2. Update ``alerts.status`` to ``'published'`` in DB.
    3. Write ``ALERT_PUBLISHED`` event to ``audit_log``.
    4. Publish to Kafka ``approval.actioned`` topic.
    5. Return ``{"status": "published", "channel": channel, "message": message}``.

    Parameters
    ----------
    alert_id:
        UUID string of the ``alerts`` row.
    channel:
        One of ``"vms"``, ``"radio"``, ``"social"``.
    message:
        Final message text (may differ from draft if officer edited it).
    incident_id:
        UUID string of the parent incident (for audit context).
    session:
        Active SQLAlchemy async session.
    redis_client:
        aioredis / redis-py async client (for cache invalidation if needed).
    kafka_producer:
        aiokafka AIOKafkaProducer (or compatible mock).

    Returns
    -------
    dict
        ``{"status": "published", "channel": channel, "message": message}``

    Raises
    ------
    PermissionError
        If the parent recommendation is not in ``'approved'`` status.
    ValueError
        If the alert row is not found.
    """
    from sqlalchemy import text

    # ---- Locate alert row and parent recommendation -----------------------
    try:
        row = await session.execute(
            text(
                """
                SELECT recommendation_id::text
                FROM alerts
                WHERE id = :alert_id::uuid
                """
            ),
            {"alert_id": alert_id},
        )
        mapping = row.mappings().first()
    except Exception as exc:
        _stdlib_logger.error("publish_alert: DB lookup failed for alert_id=%s — %s", alert_id, exc)
        raise

    if mapping is None:
        raise ValueError(f"Alert {alert_id!r} not found in database.")

    recommendation_id: str = mapping["recommendation_id"]

    # ---- Approval guard ---------------------------------------------------
    is_approved = await check_approval_guard(recommendation_id, session)
    if not is_approved:
        raise PermissionError(
            f"Cannot publish alert {alert_id!r}: recommendation {recommendation_id!r} "
            "has not been approved by an officer."
        )

    # ---- Channel dispatch -------------------------------------------------
    _dispatch_to_channel(channel, message, alert_id, incident_id)

    # ---- Update DB status -------------------------------------------------
    try:
        await session.execute(
            text(
                """
                UPDATE alerts
                SET status = 'published'
                WHERE id = :alert_id::uuid
                """
            ),
            {"alert_id": alert_id},
        )
        await session.flush()
    except Exception as exc:
        _stdlib_logger.error(
            "publish_alert: failed to update alerts.status for alert_id=%s — %s", alert_id, exc
        )
        raise

    # ---- Audit log --------------------------------------------------------
    await log_event(
        event_type="ALERT_PUBLISHED",
        actor="system",
        payload={
            "alert_id": alert_id,
            "recommendation_id": recommendation_id,
            "incident_id": incident_id,
            "channel": channel,
            "message_length": len(message),
        },
        session=session,
    )

    # ---- Kafka publish ----------------------------------------------------
    await _publish_to_kafka(
        kafka_producer=kafka_producer,
        alert_id=alert_id,
        recommendation_id=recommendation_id,
        incident_id=incident_id,
        channel=channel,
        message=message,
    )

    result = {"status": "published", "channel": channel, "message": message}
    logger.info(
        "alert_published",
        alert_id=alert_id,
        channel=channel,
        incident_id=incident_id,
    )
    return result


async def check_approval_guard(recommendation_id: str, session) -> bool:
    """
    Query the ``recommendations`` table and return ``True`` only if the record's
    ``status`` column equals ``'approved'``.

    Parameters
    ----------
    recommendation_id:
        UUID string of the recommendation to check.
    session:
        Active SQLAlchemy async session.

    Returns
    -------
    bool
        ``True`` if and only if ``status == 'approved'``.
    """
    from sqlalchemy import text

    try:
        row = await session.execute(
            text(
                """
                SELECT status
                FROM recommendations
                WHERE id = :rec_id::uuid
                """
            ),
            {"rec_id": recommendation_id},
        )
        mapping = row.mappings().first()
        if mapping is None:
            _stdlib_logger.warning(
                "check_approval_guard: recommendation %s not found", recommendation_id
            )
            return False
        return mapping["status"] == "approved"
    except Exception as exc:  # noqa: BLE001
        _stdlib_logger.error(
            "check_approval_guard: DB error for recommendation_id=%s — %s",
            recommendation_id,
            exc,
        )
        return False


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _dispatch_to_channel(
    channel: str,
    message: str,
    alert_id: str,
    incident_id: str,
) -> None:
    """Log the alert to the appropriate mock channel handler."""
    channel_lower = channel.lower()

    if channel_lower == "vms":
        logger.info(
            "VMS_BOARD_PUBLISH",
            display="📺 VMS BOARD: " + message,
            alert_id=alert_id,
            incident_id=incident_id,
            channel="vms",
        )
    elif channel_lower == "radio":
        logger.info(
            "RADIO_BROADCAST_PUBLISH",
            display="📻 RADIO BROADCAST: " + message,
            alert_id=alert_id,
            incident_id=incident_id,
            channel="radio",
        )
    elif channel_lower == "social":
        logger.info(
            "SOCIAL_POST_PUBLISH",
            display="🐦 SOCIAL POST: " + message,
            alert_id=alert_id,
            incident_id=incident_id,
            channel="social",
        )
    else:
        logger.warning(
            "unknown_channel",
            channel=channel,
            alert_id=alert_id,
            message=message,
        )


async def _publish_to_kafka(
    kafka_producer,
    alert_id: str,
    recommendation_id: str,
    incident_id: str,
    channel: str,
    message: str,
) -> None:
    """
    Publish the approval-actioned event to Kafka.

    Failures are logged and swallowed — Kafka unavailability must not block
    the alert from being marked published in the DB.
    """
    if kafka_producer is None:
        _stdlib_logger.debug("_publish_to_kafka: producer is None — skipping")
        return

    event_payload = {
        "event": "ALERT_PUBLISHED",
        "alert_id": alert_id,
        "recommendation_id": recommendation_id,
        "incident_id": incident_id,
        "channel": channel,
        "message": message,
    }

    try:
        encoded = json.dumps(event_payload, ensure_ascii=False).encode("utf-8")
        await kafka_producer.send_and_wait(_KAFKA_TOPIC, value=encoded)
        _stdlib_logger.debug(
            "_publish_to_kafka: sent to topic=%s alert_id=%s", _KAFKA_TOPIC, alert_id
        )
    except Exception as exc:  # noqa: BLE001
        _stdlib_logger.warning(
            "_publish_to_kafka: Kafka publish failed alert_id=%s — %s", alert_id, exc
        )
