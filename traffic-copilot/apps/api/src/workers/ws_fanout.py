"""
Consumes from: incident.state.updated, recommendation.ready, approval.actioned
For each message: calls connection_manager.broadcast(incident_id, payload)
This is the bridge between Kafka and connected WebSocket clients.
"""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from src.core.logging import get_logger

if TYPE_CHECKING:
    from src.api.ws.live_updates import ConnectionManager

logger = get_logger(__name__)

# Map topic name → event_type string sent to WebSocket clients.
_TOPIC_EVENT_TYPES: dict[str, str] = {
    "incident.state.updated": "state_updated",
    "recommendation.ready": "recommendation_ready",
    "approval.actioned": "approval_actioned",
}


def _extract_incident_id(payload: dict[str, Any], topic: str) -> str | None:
    """Pull the incident_id out of the payload regardless of message shape."""
    # incident.state.updated → payload.incident.id  or  payload.incident_id
    if topic == "incident.state.updated":
        incident_block = payload.get("incident", {})
        if isinstance(incident_block, dict):
            iid = incident_block.get("id")
            if iid:
                return str(iid)
        return str(payload.get("incident_id", "")) or None

    # recommendation.ready / approval.actioned → payload.incident_id
    iid = payload.get("incident_id")
    if iid:
        return str(iid)

    # Last resort: nested structures.
    for key in ("incident", "data"):
        block = payload.get(key, {})
        if isinstance(block, dict):
            iid = block.get("incident_id") or block.get("id")
            if iid:
                return str(iid)

    return None


async def run_ws_fanout(connection_manager: "ConnectionManager") -> None:
    """
    Main consumer loop consuming 3 topics.
    Map topic → event_type:
    - incident.state.updated  → "state_updated"
    - recommendation.ready    → "recommendation_ready"
    - approval.actioned       → "approval_actioned"
    Broadcast payload: {"event_type": str, "incident_id": str, "data": dict}
    """
    from src.core.config import settings
    from src.integrations.kafka.consumer import create_consumer, consume_messages
    from src.integrations.kafka.topics import (
        APPROVAL_ACTIONED,
        INCIDENT_STATE_UPDATED,
        RECOMMENDATION_READY,
    )

    logger.info("ws_fanout starting up")

    async def handle(payload: dict[str, Any], topic: str) -> None:
        event_type = _TOPIC_EVENT_TYPES.get(topic, topic)
        incident_id = _extract_incident_id(payload, topic)

        outgoing = {
            "event_type": event_type,
            "incident_id": incident_id or "",
            "data": payload,
        }

        if incident_id:
            await connection_manager.broadcast(incident_id, outgoing)
        else:
            # No incident_id — broadcast to all rooms (e.g. system-level events).
            logger.debug("ws_fanout: no incident_id found, broadcasting to all rooms", topic=topic)
            await connection_manager.broadcast_all(outgoing)

        logger.debug(
            "ws_fanout: broadcasted",
            event_type=event_type,
            incident_id=incident_id,
            topic=topic,
        )

    consumer = await create_consumer(
        topics=[INCIDENT_STATE_UPDATED, RECOMMENDATION_READY, APPROVAL_ACTIONED],
        group_id=f"{settings.kafka_consumer_group_id}-ws-fanout",
        bootstrap_servers=settings.kafka_bootstrap_servers,
        auto_offset_reset="latest",
    )

    await consume_messages(consumer, handle)
    logger.info("ws_fanout shut down")
