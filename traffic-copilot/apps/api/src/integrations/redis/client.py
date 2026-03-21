"""
Async Redis client singleton and cache helpers for TrafficCopilot.

All cache values are JSON-serialised dicts.  TTLs are configurable per call.

Lifecycle
---------
    from src.integrations.redis.client import start_redis, stop_redis

    await start_redis(settings.redis_url)   # at startup
    await stop_redis()                       # at shutdown

Cache helpers
-------------
    from src.integrations.redis.client import cache_set, cache_get
    from src.integrations.redis.client import incident_snapshot_key

    await cache_set(incident_snapshot_key("abc-123"), snapshot_dict, ttl_seconds=300)
    data = await cache_get(incident_snapshot_key("abc-123"))
"""

from __future__ import annotations

import json
import logging
from typing import Any

import redis.asyncio as aioredis

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_redis: aioredis.Redis | None = None


async def start_redis(url: str) -> None:
    """
    Initialise the global Redis client and verify connectivity with a PING.

    Parameters
    ----------
    url:
        Redis DSN, e.g. ``"redis://localhost:6379/0"``.
    """
    global _redis
    if _redis is not None:
        logger.debug("Redis client already initialised; skipping.")
        return

    _redis = aioredis.from_url(
        url,
        encoding="utf-8",
        decode_responses=False,  # we handle encoding ourselves
        socket_connect_timeout=5,
        socket_keepalive=True,
        retry_on_timeout=True,
        health_check_interval=30,
    )
    await _redis.ping()
    logger.info("Redis client started (url=%s)", url)


async def stop_redis() -> None:
    """Close the Redis client connection pool."""
    global _redis
    if _redis is None:
        return
    await _redis.aclose()
    _redis = None
    logger.info("Redis client stopped.")


async def get_redis() -> aioredis.Redis:
    """
    Return the running Redis client singleton.

    Raises
    ------
    RuntimeError
        If ``start_redis`` has not been called.
    """
    if _redis is None:
        raise RuntimeError(
            "Redis client is not initialised. Call start_redis(url) first."
        )
    return _redis


# ---------------------------------------------------------------------------
# Generic cache operations
# ---------------------------------------------------------------------------


async def cache_set(
    key: str,
    value: dict[str, Any],
    ttl_seconds: int = 60,
) -> None:
    """
    Serialise *value* as JSON and store it under *key* with the given TTL.

    Parameters
    ----------
    key:
        Cache key (use the helpers below for consistency).
    value:
        JSON-serialisable dictionary.
    ttl_seconds:
        Time-to-live in seconds.  Pass ``0`` to persist indefinitely (not
        recommended for ephemeral operational data).
    """
    client = await get_redis()
    encoded: bytes = json.dumps(value, default=str).encode("utf-8")
    if ttl_seconds > 0:
        await client.setex(key, ttl_seconds, encoded)
    else:
        await client.set(key, encoded)
    logger.debug("cache_set key=%s ttl=%ds bytes=%d", key, ttl_seconds, len(encoded))


async def cache_get(key: str) -> dict[str, Any] | None:
    """
    Retrieve and JSON-deserialise the value stored under *key*.

    Returns
    -------
    dict | None
        The stored dictionary, or ``None`` if the key does not exist or has
        expired.
    """
    client = await get_redis()
    raw: bytes | None = await client.get(key)
    if raw is None:
        return None
    try:
        return json.loads(raw.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        logger.error("Failed to deserialise cache value for key=%s: %s", key, exc)
        return None


# ---------------------------------------------------------------------------
# Cache key helpers
# ---------------------------------------------------------------------------


def incident_snapshot_key(incident_id: str) -> str:
    """
    Full incident state snapshot — all fields from the DB plus computed data.

    ``incident:{incident_id}:snapshot``
    """
    return f"incident:{incident_id}:snapshot"


def incident_segments_key(incident_id: str) -> str:
    """
    List of affected road segments for an incident.

    ``incident:{incident_id}:segments``
    """
    return f"incident:{incident_id}:segments"


def incident_diversion_key(incident_id: str) -> str:
    """
    Active diversion route(s) for an incident.

    ``incident:{incident_id}:diversion``
    """
    return f"incident:{incident_id}:diversion"


def incident_signal_plan_key(incident_id: str) -> str:
    """
    Signal plan candidate(s) associated with an incident.

    ``incident:{incident_id}:signal_plan``
    """
    return f"incident:{incident_id}:signal_plan"


def sensor_speed_key(segment_id: str) -> str:
    """
    Latest sensor speed reading for a road segment.

    ``sensor:{segment_id}:speed``
    """
    return f"sensor:{segment_id}:speed"


def vision_analysis_key(incident_id: str) -> str:
    """
    Latest vision-model analysis result for an incident (from POST /vision).

    ``vision:{incident_id}``
    """
    return f"vision:{incident_id}"
