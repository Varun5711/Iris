"""
Queue length and delay estimation from speed observations.

All calculations use the simple Bureau of Public Roads (BPR) / ratio model:
  congestion = (1 - observed_speed / free_flow_speed)
  extra_travel_time = segment_length / observed_speed - segment_length / free_flow_speed
  queue_length ≈ congestion_ratio * segment_length (heuristic)
"""

from __future__ import annotations

import logging
import math

logger = logging.getLogger(__name__)

# Default free-flow speed for urban arterials when none is provided.
DEFAULT_FREE_FLOW_KMH = 50.0

# Minimum speed floor to avoid division-by-zero (1 km/h crawl).
MIN_SPEED_KMH = 1.0

# Congestion thresholds (inclusive lower bound → label).
_CONGESTION_BANDS: list[tuple[float, str]] = [
    (80.0, "gridlock"),
    (60.0, "heavy"),
    (40.0, "moderate"),
    (15.0, "light"),
    (0.0, "free_flow"),
]


def estimate_delay(
    speed_kmh: float,
    free_flow_kmh: float,
    segment_length_m: float = 500.0,
) -> dict:
    """Estimate congestion severity and delay for a road segment.

    Args:
        speed_kmh:        Current observed average speed on the segment.
        free_flow_kmh:    Speed under uncongested conditions.
        segment_length_m: Physical length of the segment in metres (default 500 m).

    Returns a dict with:
        congestion_pct  – How congested the segment is (0 = free, 100 = standstill).
        delay_seconds   – Extra travel time vs. free-flow conditions (integer seconds).
        queue_length_m  – Heuristic queue estimate in metres behind the incident.
    """
    # --- Input sanitisation --------------------------------------------------
    if free_flow_kmh is None or free_flow_kmh <= 0:
        free_flow_kmh = DEFAULT_FREE_FLOW_KMH
        logger.debug("estimate_delay: invalid free_flow_kmh, using default %.1f", free_flow_kmh)

    if speed_kmh is None or speed_kmh < 0:
        speed_kmh = 0.0

    if segment_length_m is None or segment_length_m <= 0:
        segment_length_m = 500.0

    # Clamp speed so it cannot exceed free flow (sensor noise guard).
    speed_kmh = max(MIN_SPEED_KMH, min(speed_kmh, free_flow_kmh))

    # --- Core calculations ---------------------------------------------------
    congestion_ratio = 1.0 - (speed_kmh / free_flow_kmh)
    congestion_pct = round(max(0.0, min(100.0, congestion_ratio * 100.0)), 2)

    # Travel time at observed speed vs free-flow (convert km/h → m/s first).
    speed_ms = speed_kmh / 3.6
    free_flow_ms = free_flow_kmh / 3.6

    travel_time_actual = segment_length_m / speed_ms
    travel_time_free = segment_length_m / free_flow_ms
    delay_seconds = max(0, int(round(travel_time_actual - travel_time_free)))

    # Heuristic queue length: congested fraction of segment.
    queue_length_m = round(congestion_ratio * segment_length_m, 1)

    return {
        "congestion_pct": congestion_pct,
        "delay_seconds": delay_seconds,
        "queue_length_m": queue_length_m,
    }


def classify_congestion(congestion_pct: float) -> str:
    """Map a congestion percentage to a human-readable severity label.

    Args:
        congestion_pct: Value between 0 and 100 from estimate_delay().

    Returns one of: free_flow | light | moderate | heavy | gridlock
    """
    if congestion_pct is None:
        return "free_flow"

    pct = float(congestion_pct)
    for threshold, label in _CONGESTION_BANDS:
        if pct >= threshold:
            return label
    return "free_flow"


def estimate_clearance_time(
    queue_length_m: float,
    incident_clearance_rate_m_per_min: float = 50.0,
) -> int:
    """Estimate how many minutes until the queue clears.

    Uses a simple drain model: clearance_rate metres of queue dissipate per
    minute once the incident is being cleared.

    Returns an integer number of minutes (minimum 1).
    """
    if queue_length_m <= 0:
        return 0
    if incident_clearance_rate_m_per_min <= 0:
        incident_clearance_rate_m_per_min = 50.0
    return max(1, int(math.ceil(queue_length_m / incident_clearance_rate_m_per_min)))
