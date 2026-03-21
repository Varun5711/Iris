"""
AIOKafkaConsumer factory and message-loop helpers for TrafficCopilot.

Usage
-----
    from src.integrations.kafka.consumer import create_consumer, consume_messages
    from src.integrations.kafka import topics

    consumer = await create_consumer(
        topics=[topics.TRAFFIC_EVENTS_RAW],
        group_id="my-worker",
        bootstrap_servers=settings.kafka_bootstrap_servers,
    )

    async def handler(msg: dict, topic: str) -> None:
        print(f"Received from {topic}: {msg}")

    # Run until cancelled
    await consume_messages(consumer, handler)
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiokafka import AIOKafkaConsumer
from aiokafka.errors import KafkaError

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


async def create_consumer(
    topics: list[str],
    group_id: str,
    bootstrap_servers: str,
    auto_offset_reset: str = "latest",
) -> AIOKafkaConsumer:
    """
    Create and start an ``AIOKafkaConsumer`` subscribed to *topics*.

    Parameters
    ----------
    topics:
        List of Kafka topic names to subscribe to.
    group_id:
        Consumer group identifier.  Use a stable, unique name per worker type
        so offset commits are correctly tracked.
    bootstrap_servers:
        Comma-separated Kafka broker addresses.
    auto_offset_reset:
        ``"latest"`` (default) or ``"earliest"``.  Use ``"earliest"`` when
        replaying historical data.

    Returns
    -------
    AIOKafkaConsumer
        A fully started consumer ready to receive messages.
    """
    consumer = AIOKafkaConsumer(
        *topics,
        bootstrap_servers=bootstrap_servers,
        group_id=group_id,
        auto_offset_reset=auto_offset_reset,
        enable_auto_commit=True,
        auto_commit_interval_ms=5000,
        # Deserialise bytes → str; JSON parsing is done in the consume loop
        # so that malformed messages can be caught and logged individually.
        value_deserializer=lambda v: v.decode("utf-8") if v is not None else None,
        key_deserializer=lambda k: k.decode("utf-8") if k is not None else None,
        # Heartbeat and session timeouts tuned for typical worker restart times
        heartbeat_interval_ms=3000,
        session_timeout_ms=30000,
        max_poll_interval_ms=300000,
        # Fetch settings
        fetch_max_wait_ms=500,
        max_partition_fetch_bytes=1048576,  # 1 MB per partition per fetch
    )
    await consumer.start()
    logger.info(
        "Kafka consumer started (group=%s topics=%s offset_reset=%s)",
        group_id,
        topics,
        auto_offset_reset,
    )
    return consumer


# ---------------------------------------------------------------------------
# Message loop
# ---------------------------------------------------------------------------


async def consume_messages(
    consumer: AIOKafkaConsumer,
    handler: Callable[[dict[str, Any], str], Awaitable[None]],
) -> None:
    """
    Run an infinite message-consumption loop, calling *handler* for every
    message received.

    The loop runs until the coroutine is cancelled (e.g. via
    ``asyncio.CancelledError``), at which point the consumer is stopped
    cleanly.

    Parameters
    ----------
    consumer:
        A started ``AIOKafkaConsumer`` returned by :func:`create_consumer`.
    handler:
        Async callable ``(msg_dict, topic) -> None``.  Called once per message
        with the JSON-decoded payload and the source topic name.

        If the message value cannot be JSON-decoded it is logged and skipped.
        If *handler* raises an exception the error is logged but the loop
        continues — this prevents a single bad message from killing the worker.
    """
    try:
        async for msg in consumer:
            topic: str = msg.topic
            raw_value: str | None = msg.value

            if raw_value is None:
                logger.warning(
                    "Received tombstone (null value) on topic=%s partition=%d offset=%d",
                    topic,
                    msg.partition,
                    msg.offset,
                )
                continue

            try:
                payload: dict[str, Any] = json.loads(raw_value)
            except json.JSONDecodeError as exc:
                logger.error(
                    "Failed to JSON-decode message on topic=%s partition=%d offset=%d: %s",
                    topic,
                    msg.partition,
                    msg.offset,
                    exc,
                )
                continue

            try:
                await handler(payload, topic)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                logger.exception(
                    "Handler raised an exception for topic=%s partition=%d offset=%d: %s",
                    topic,
                    msg.partition,
                    msg.offset,
                    exc,
                )
    except asyncio.CancelledError:
        logger.info("Kafka consume loop cancelled — shutting down consumer.")
    except KafkaError as exc:
        logger.error("Kafka error in consume loop: %s", exc)
        raise
    finally:
        await consumer.stop()
        logger.info("Kafka consumer stopped.")
