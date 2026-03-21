"""
Singleton AIOKafkaProducer for TrafficCopilot.

Lifecycle
---------
Call ``start_producer`` once at application startup (e.g. in a FastAPI lifespan
handler), then use ``publish`` throughout the application, and ``stop_producer``
on shutdown.

Usage
-----
    from src.integrations.kafka.producer import start_producer, stop_producer, publish
    from src.integrations.kafka import topics

    # startup
    await start_producer(settings.kafka_bootstrap_servers)

    # publish
    await publish(topics.INCIDENT_STATE_UPDATED, {"incident_id": "...", "status": "active"})

    # shutdown
    await stop_producer()
"""

from __future__ import annotations

import json
import logging
from typing import Any

from aiokafka import AIOKafkaProducer

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_producer: AIOKafkaProducer | None = None


# ---------------------------------------------------------------------------
# Lifecycle helpers
# ---------------------------------------------------------------------------


async def start_producer(bootstrap_servers: str) -> None:
    """
    Create and start the global ``AIOKafkaProducer`` singleton.

    Safe to call multiple times — subsequent calls are no-ops if the producer
    is already running.

    Parameters
    ----------
    bootstrap_servers:
        Comma-separated Kafka broker addresses, e.g. ``"localhost:9092"``.
    """
    global _producer
    if _producer is not None:
        logger.debug("Kafka producer already started; skipping initialisation.")
        return

    _producer = AIOKafkaProducer(
        bootstrap_servers=bootstrap_servers,
        # publish() pre-encodes both key and value to bytes before calling
        # send_and_wait(), so no serializers are needed here.
        # acks="all" gives durability; idempotence is omitted because
        # enable_idempotence=True triggers InitProducerIdRequest which can
        # time-out on a single-node KRaft broker during startup.
        acks="all",
        compression_type="gzip",
        max_batch_size=16384,
        linger_ms=10,
    )
    await _producer.start()
    logger.info(
        "Kafka producer started (bootstrap_servers=%s)", bootstrap_servers
    )


async def stop_producer() -> None:
    """
    Flush pending messages and stop the global producer.

    Safe to call even if ``start_producer`` was never called.
    """
    global _producer
    if _producer is None:
        return
    await _producer.stop()
    _producer = None
    logger.info("Kafka producer stopped.")


async def get_producer() -> AIOKafkaProducer:
    """
    Return the running singleton producer.

    Raises
    ------
    RuntimeError
        If ``start_producer`` has not been called yet.
    """
    if _producer is None:
        raise RuntimeError(
            "Kafka producer is not initialised. "
            "Call start_producer(bootstrap_servers) first."
        )
    return _producer


# ---------------------------------------------------------------------------
# Publish helper
# ---------------------------------------------------------------------------


async def publish(
    topic: str,
    value: dict[str, Any],
    key: str | None = None,
) -> None:
    """
    JSON-serialise *value* and publish it to *topic*.

    Parameters
    ----------
    topic:
        Destination Kafka topic name (use constants from
        ``src.integrations.kafka.topics``).
    value:
        Dictionary to serialise and publish.  Must be JSON-serialisable.
    key:
        Optional message key used for partition routing.  If provided it is
        UTF-8 encoded before being sent.
    """
    producer = await get_producer()
    encoded_value: bytes = json.dumps(value, default=str).encode("utf-8")
    encoded_key: bytes | None = key.encode("utf-8") if key is not None else None

    await producer.send_and_wait(topic, value=encoded_value, key=encoded_key)
    logger.debug(
        "Published to Kafka topic=%s key=%s bytes=%d",
        topic,
        key,
        len(encoded_value),
    )
