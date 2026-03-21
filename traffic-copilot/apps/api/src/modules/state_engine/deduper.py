"""
Event deduplication using Redis SET NX with TTL.

The contract is simple: the first caller for a given event_id wins and
gets False (not a duplicate). Every subsequent caller within the TTL
window gets True (duplicate — discard).
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


async def is_duplicate(
    event_id: str,
    redis_client,
    ttl_seconds: int = 300,
) -> bool:
    """Check if event_id was already processed. If not, mark as seen.

    Uses Redis SET NX (set-if-not-exists) with an expiry so the key
    automatically ages out after *ttl_seconds*.

    Args:
        event_id:     Unique identifier for the event (e.g. UUID string).
        redis_client: An async Redis client instance (redis.asyncio.Redis).
        ttl_seconds:  How long to remember the event (default 5 minutes).

    Returns:
        True  — the key already existed → this is a duplicate, discard it.
        False — the key was just created → this is the first time we see it.
    """
    if not event_id:
        logger.warning("is_duplicate called with empty event_id — treating as non-duplicate")
        return False

    key = f"dedup:{event_id}"
    try:
        result = await redis_client.set(key, "1", ex=ttl_seconds, nx=True)
        # SET NX returns True when key was created, None when it already existed.
        is_dup = result is None
        if is_dup:
            logger.debug("Duplicate event detected: %s", event_id)
        return is_dup
    except Exception:
        logger.exception("Redis error in is_duplicate for event_id=%s; treating as non-duplicate", event_id)
        # Fail open: on Redis outage, allow the event through rather than
        # silently dropping legitimate events.
        return False


async def clear_event(event_id: str, redis_client) -> bool:
    """Remove a dedup key early (useful in tests or manual replay).

    Returns True if the key existed and was deleted, False otherwise.
    """
    key = f"dedup:{event_id}"
    try:
        deleted = await redis_client.delete(key)
        return deleted > 0
    except Exception:
        logger.exception("Redis error while clearing dedup key for event_id=%s", event_id)
        return False


async def get_ttl(event_id: str, redis_client) -> int:
    """Return remaining TTL in seconds for a dedup key, or -2 if it doesn't exist."""
    key = f"dedup:{event_id}"
    try:
        ttl = await redis_client.ttl(key)
        return int(ttl)
    except Exception:
        logger.exception("Redis error while fetching TTL for event_id=%s", event_id)
        return -2
