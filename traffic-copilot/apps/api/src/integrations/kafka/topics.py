"""
Kafka topic name constants and startup helper for TrafficCopilot.

Topics
------
traffic.events.raw       — raw ingest payloads from all sensor sources
incident.state.updated   — incident lifecycle transitions (created/updated/resolved)
recommendation.ready     — AI-generated recommendation packages ready for officer review
approval.actioned        — officer approval / rejection events

Usage
-----
    from src.integrations.kafka.topics import create_topics, ALL_TOPICS
    await create_topics(settings.kafka_bootstrap_servers)
"""

from __future__ import annotations

import logging

from aiokafka.admin import AIOKafkaAdminClient, NewTopic
from aiokafka.errors import TopicAlreadyExistsError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Topic name constants
# ---------------------------------------------------------------------------

TRAFFIC_EVENTS_RAW = "traffic.events.raw"
INCIDENT_STATE_UPDATED = "incident.state.updated"
RECOMMENDATION_READY = "recommendation.ready"
APPROVAL_ACTIONED = "approval.actioned"

ALL_TOPICS: list[str] = [
    TRAFFIC_EVENTS_RAW,
    INCIDENT_STATE_UPDATED,
    RECOMMENDATION_READY,
    APPROVAL_ACTIONED,
]

# ---------------------------------------------------------------------------
# Topic creation
# ---------------------------------------------------------------------------

_NUM_PARTITIONS = 3
_REPLICATION_FACTOR = 1


async def create_topics(bootstrap_servers: str) -> None:
    """
    Idempotently create all TrafficCopilot Kafka topics.

    Each topic is created with 3 partitions and replication_factor=1 (suitable
    for a single-broker development / hackathon setup).  Topics that already
    exist are silently skipped.

    Parameters
    ----------
    bootstrap_servers:
        Comma-separated list of Kafka broker addresses, e.g. ``"localhost:9092"``.
    """
    admin: AIOKafkaAdminClient = AIOKafkaAdminClient(
        bootstrap_servers=bootstrap_servers,
    )
    await admin.start()
    try:
        new_topics = [
            NewTopic(
                name=topic,
                num_partitions=_NUM_PARTITIONS,
                replication_factor=_REPLICATION_FACTOR,
            )
            for topic in ALL_TOPICS
        ]
        results = await admin.create_topics(new_topics, validate_only=False)
        for topic, error in results.items():
            if error is None:
                logger.info("Kafka topic created: %s", topic)
            elif isinstance(error, TopicAlreadyExistsError):
                logger.debug("Kafka topic already exists (skipping): %s", topic)
            else:
                logger.error(
                    "Failed to create Kafka topic %s: %s", topic, error
                )
                raise error
    finally:
        await admin.close()
