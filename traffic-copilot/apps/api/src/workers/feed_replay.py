"""
Reads data/replays/scenario_1/*.json files and produces messages to Kafka traffic.events.raw topic.
Each JSON file in the scenario dir is a TrafficEvent dict.
Files are sorted and replayed with a configurable delay between messages.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from src.core.logging import get_logger

logger = get_logger(__name__)


async def run_feed_replay(
    scenario_dir: str = "/app/data/replays/scenario_1",
    interval_seconds: float = 2.0,
    loop: bool = False,
) -> None:
    """
    Main worker loop:
    1. Read all *.json files from scenario_dir sorted by filename
    2. For each file: publish to traffic.events.raw
    3. Sleep interval_seconds between messages
    4. If loop=True: restart after all files consumed
    """
    from src.integrations.kafka.producer import publish
    from src.integrations.kafka.topics import TRAFFIC_EVENTS_RAW

    path = Path(scenario_dir)

    logger.info("feed_replay starting", scenario_dir=scenario_dir, interval=interval_seconds, loop=loop)

    while True:
        if not path.exists() or not path.is_dir():
            logger.warning("feed_replay: scenario_dir does not exist or is not a directory", path=str(path))
            await asyncio.sleep(30.0)
            if not loop:
                return
            continue

        json_files = sorted(path.glob("*.json"))

        if not json_files:
            logger.warning("feed_replay: no *.json files found in scenario_dir", path=str(path))
            await asyncio.sleep(30.0)
            if not loop:
                return
            continue

        logger.info("feed_replay: replaying scenario", file_count=len(json_files), scenario_dir=str(path))

        for json_file in json_files:
            try:
                raw = json_file.read_text(encoding="utf-8")
                payload: dict = json.loads(raw)
            except (OSError, json.JSONDecodeError) as exc:
                logger.error("feed_replay: failed to read/parse file", file=str(json_file), error=str(exc))
                continue

            # Use incident_id or event_id as the Kafka message key for partition routing.
            # Avoid str(None) = "None" — only stringify when the value is actually present.
            _raw_key = payload.get("incident_id") or payload.get("event_id")
            key: str | None = str(_raw_key) if _raw_key is not None else None

            try:
                await publish(TRAFFIC_EVENTS_RAW, payload, key=key)
                logger.debug(
                    "feed_replay: published event",
                    file=json_file.name,
                    key=key,
                    topic=TRAFFIC_EVENTS_RAW,
                )
            except Exception as exc:
                logger.error(
                    "feed_replay: failed to publish event",
                    file=json_file.name,
                    error=str(exc),
                    exc_info=True,
                )

            try:
                await asyncio.sleep(interval_seconds)
            except asyncio.CancelledError:
                logger.info("feed_replay: cancelled during sleep")
                raise

        logger.info("feed_replay: scenario replay complete", file_count=len(json_files))

        if not loop:
            logger.info("feed_replay: loop=False, exiting")
            return

        logger.info("feed_replay: loop=True, restarting scenario from beginning")
        # Brief pause before looping to avoid hammering Kafka on empty/tiny scenarios.
        await asyncio.sleep(max(interval_seconds, 1.0))
