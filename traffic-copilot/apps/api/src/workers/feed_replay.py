"""
Reads data/replays/scenario_1/*.json files and produces messages to Kafka traffic.events.raw topic.
Each JSON file in the scenario dir is a TrafficEvent dict.
Files are sorted and replayed with a configurable delay between messages.

Batching behaviour
------------------
Events are published in batches of `batch_size`.  After each full batch the
worker sleeps `batch_interval_seconds` before sending the next batch.  This
spaces out LLM token consumption so you don't exhaust the daily Groq quota in
one burst.

Graph-wait
----------
The worker polls for the OSMnx graph singleton to be ready before it starts
replaying.  This ensures that the incident_processor can do geo-routing as soon
as the first event arrives.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from src.core.logging import get_logger

logger = get_logger(__name__)

# How often (seconds) to poll while waiting for the OSM graph to load.
_GRAPH_POLL_INTERVAL = 5.0


async def _wait_for_graph() -> None:
    """Block until the OSMnx graph singleton is initialised."""
    from src.integrations.osm.loader import is_graph_ready

    if is_graph_ready():
        return

    logger.info("feed_replay: waiting for OSM graph to finish loading …")
    while not is_graph_ready():
        await asyncio.sleep(_GRAPH_POLL_INTERVAL)
    logger.info("feed_replay: OSM graph is ready — starting replay")


async def run_feed_replay(
    scenario_dir: str = "/app/data/replays/scenario_1",
    interval_seconds: float = 2.0,
    loop: bool = False,
    batch_size: int = 10,
    batch_interval_seconds: float = 30.0,
) -> None:
    """
    Main worker loop:
    1. Wait for OSM graph to be ready
    2. Read all *.json files from scenario_dir sorted by filename
    3. Publish events in batches of `batch_size`, sleeping `interval_seconds`
       between individual events and `batch_interval_seconds` after each batch
    4. If loop=True: restart after all files consumed
    """
    from src.integrations.kafka.producer import publish
    from src.integrations.kafka.topics import TRAFFIC_EVENTS_RAW

    path = Path(scenario_dir)

    logger.info(
        "feed_replay starting",
        scenario_dir=scenario_dir,
        interval=interval_seconds,
        batch_size=batch_size,
        batch_interval=batch_interval_seconds,
        loop=loop,
    )

    # ── Wait for OSM graph before first replay pass ───────────────────────
    await _wait_for_graph()

    while True:
        if not path.exists() or not path.is_dir():
            logger.warning(
                "feed_replay: scenario_dir does not exist or is not a directory",
                path=str(path),
            )
            await asyncio.sleep(30.0)
            if not loop:
                return
            continue

        json_files = sorted(path.glob("*.json"))

        if not json_files:
            logger.warning(
                "feed_replay: no *.json files found in scenario_dir",
                path=str(path),
            )
            await asyncio.sleep(30.0)
            if not loop:
                return
            continue

        logger.info(
            "feed_replay: replaying scenario",
            file_count=len(json_files),
            scenario_dir=str(path),
            batch_size=batch_size,
            batch_interval=batch_interval_seconds,
        )

        for idx, json_file in enumerate(json_files, start=1):
            try:
                raw = json_file.read_text(encoding="utf-8")
                payload: dict = json.loads(raw)
            except (OSError, json.JSONDecodeError) as exc:
                logger.error(
                    "feed_replay: failed to read/parse file",
                    file=str(json_file),
                    error=str(exc),
                )
                continue

            _raw_key = payload.get("incident_id") or payload.get("event_id")
            key: str | None = str(_raw_key) if _raw_key is not None else None

            try:
                await publish(TRAFFIC_EVENTS_RAW, payload, key=key)
                logger.info(
                    "feed_replay: published event",
                    file=json_file.name,
                    key=key,
                    topic=TRAFFIC_EVENTS_RAW,
                    batch_pos=f"{idx % batch_size or batch_size}/{batch_size}",
                )
            except Exception as exc:
                logger.error(
                    "feed_replay: failed to publish event",
                    file=json_file.name,
                    error=str(exc),
                    exc_info=True,
                )

            # ── Inter-event sleep ─────────────────────────────────────────
            try:
                await asyncio.sleep(interval_seconds)
            except asyncio.CancelledError:
                logger.info("feed_replay: cancelled during inter-event sleep")
                raise

            # ── After each full batch: extra pause ────────────────────────
            if idx % batch_size == 0 and idx < len(json_files):
                logger.info(
                    "feed_replay: batch complete — pausing before next batch",
                    events_sent=idx,
                    events_remaining=len(json_files) - idx,
                    pause_seconds=batch_interval_seconds,
                )
                try:
                    await asyncio.sleep(batch_interval_seconds)
                except asyncio.CancelledError:
                    logger.info("feed_replay: cancelled during batch pause")
                    raise

        logger.info("feed_replay: scenario replay complete", file_count=len(json_files))

        if not loop:
            logger.info("feed_replay: loop=False, exiting")
            return

        logger.info("feed_replay: loop=True, restarting scenario from beginning")
        await asyncio.sleep(max(batch_interval_seconds, 30.0))
