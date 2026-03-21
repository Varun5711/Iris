"""
Rule-based traffic signal retiming suggestions.

No LLM call is made here — the rules are deterministic and designed to run
synchronously on every incident state update so operators always have an
immediate, explainable recommendation.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class SignalSuggestion:
    intersection_id: str
    intersection_lat: float
    intersection_lon: float
    current_cycle_seconds: int
    suggested_cycle_seconds: int
    green_extension_seconds: int
    affected_approach: str        # "northbound" | "southbound" | "eastbound" | "westbound"
    rationale: str
    confidence: float             # 0.0 – 1.0
    action_description: str       # human-readable one-liner for the operator


# ---------------------------------------------------------------------------
# Rule constants
# ---------------------------------------------------------------------------

_HIGH_CONGESTION_THRESHOLD = 70.0   # %
_MEDIUM_CONGESTION_THRESHOLD = 40.0  # %

_HIGH_GREEN_EXTENSION_S = 30
_MEDIUM_GREEN_EXTENSION_S = 15
_NO_CHANGE_EXTENSION_S = 0

_HIGH_CONFIDENCE = 0.90
_MEDIUM_CONFIDENCE = 0.75
_LOW_CONFIDENCE = 0.60

_DEFAULT_CYCLE_SECONDS = 90

# Maximum intersections returned.
_MAX_SUGGESTIONS = 5

# Diversion route intersections get a shorter cycle to increase throughput.
_DIVERSION_CYCLE_REDUCTION_S = 10


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def suggest_signal_retiming(
    intersections: list[dict],
    incident_direction: str,
    congestion_pct: float,
    delay_seconds: int,
) -> list[SignalSuggestion]:
    """Generate signal retiming suggestions for intersections near an incident.

    Args:
        intersections:      List of intersection dicts from
                            corridor.get_nearby_intersections(). Each dict must
                            have keys: node_id, lat, lon, road_names.
        incident_direction: Cardinal direction that is congested — one of
                            northbound, southbound, eastbound, westbound.
        congestion_pct:     Current segment congestion (0–100).
        delay_seconds:      Estimated delay in seconds for the segment.

    Returns up to _MAX_SUGGESTIONS SignalSuggestion objects.
    """
    if not intersections:
        return []

    congestion_pct = float(congestion_pct or 0.0)
    delay_seconds = int(delay_seconds or 0)
    incident_direction = _normalise_direction(incident_direction)

    suggestions: list[SignalSuggestion] = []

    for idx, intersection in enumerate(intersections[:_MAX_SUGGESTIONS]):
        node_id = str(intersection.get("node_id", f"unknown-{idx}"))
        lat = float(intersection.get("lat", 0.0))
        lon = float(intersection.get("lon", 0.0))
        road_names = intersection.get("road_names", [])

        # Determine if this intersection is on the incident approach or a
        # potential diversion route.
        on_incident_approach = _is_on_incident_approach(road_names, incident_direction, idx)

        current_cycle = _DEFAULT_CYCLE_SECONDS
        approach = incident_direction if on_incident_approach else _opposite_direction(incident_direction)

        if on_incident_approach:
            extension, confidence, rationale = _incident_approach_rules(
                congestion_pct, delay_seconds, road_names
            )
        else:
            extension, confidence, rationale = _diversion_route_rules(
                congestion_pct, road_names
            )

        suggested_cycle = current_cycle + extension
        if not on_incident_approach:
            # Diversion routes benefit from shorter cycle (higher frequency).
            suggested_cycle = max(60, current_cycle - _DIVERSION_CYCLE_REDUCTION_S)

        action_desc = _build_action_description(
            on_incident_approach, extension, approach, road_names, suggested_cycle, current_cycle
        )

        suggestions.append(SignalSuggestion(
            intersection_id=node_id,
            intersection_lat=lat,
            intersection_lon=lon,
            current_cycle_seconds=current_cycle,
            suggested_cycle_seconds=suggested_cycle,
            green_extension_seconds=extension,
            affected_approach=approach,
            rationale=rationale,
            confidence=confidence,
            action_description=action_desc,
        ))

    return suggestions


# ---------------------------------------------------------------------------
# Direction helpers
# ---------------------------------------------------------------------------

def direction_from_nodes(graph, u: int, v: int) -> str:
    """Determine the cardinal direction of travel along edge u → v.

    Uses the bearing from node u to node v computed from their lat/lon
    coordinates.

    Returns one of: northbound | southbound | eastbound | westbound
    """
    if graph is None:
        return "northbound"

    try:
        u_data = graph.nodes.get(u, {})
        v_data = graph.nodes.get(v, {})

        lat1, lon1 = float(u_data.get("y", 0.0)), float(u_data.get("x", 0.0))
        lat2, lon2 = float(v_data.get("y", 0.0)), float(v_data.get("x", 0.0))

        bearing = _compute_bearing(lat1, lon1, lat2, lon2)
        return _bearing_to_cardinal(bearing)
    except Exception:
        logger.exception("direction_from_nodes failed for (%d, %d)", u, v)
        return "northbound"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _compute_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Compute the forward azimuth (bearing) in degrees [0, 360) from point 1 to 2."""
    lat1_r = math.radians(lat1)
    lat2_r = math.radians(lat2)
    dlon_r = math.radians(lon2 - lon1)

    x = math.sin(dlon_r) * math.cos(lat2_r)
    y = (math.cos(lat1_r) * math.sin(lat2_r)
         - math.sin(lat1_r) * math.cos(lat2_r) * math.cos(dlon_r))
    bearing = math.degrees(math.atan2(x, y))
    return (bearing + 360) % 360


def _bearing_to_cardinal(bearing: float) -> str:
    """Map a bearing in degrees to a cardinal direction string."""
    if bearing < 45 or bearing >= 315:
        return "northbound"
    if 45 <= bearing < 135:
        return "eastbound"
    if 135 <= bearing < 225:
        return "southbound"
    return "westbound"


def _normalise_direction(direction: str) -> str:
    """Ensure direction is a valid cardinal label, defaulting to northbound."""
    valid = {"northbound", "southbound", "eastbound", "westbound"}
    if direction and direction.lower() in valid:
        return direction.lower()
    return "northbound"


def _opposite_direction(direction: str) -> str:
    opposites = {
        "northbound": "southbound",
        "southbound": "northbound",
        "eastbound": "westbound",
        "westbound": "eastbound",
    }
    return opposites.get(direction, "northbound")


def _is_on_incident_approach(
    road_names: list[str],
    incident_direction: str,
    idx: int,
) -> bool:
    """Heuristic: first two intersections are on the incident approach,
    remaining ones are treated as potential diversion routes."""
    return idx < 2


def _incident_approach_rules(
    congestion_pct: float,
    delay_seconds: int,
    road_names: list[str],
) -> tuple[int, float, str]:
    """Return (green_extension_s, confidence, rationale) for an approach intersection."""
    road_label = road_names[0] if road_names else "this segment"

    if congestion_pct > _HIGH_CONGESTION_THRESHOLD:
        ext = _HIGH_GREEN_EXTENSION_S
        conf = _HIGH_CONFIDENCE
        rationale = (
            f"Congestion at {congestion_pct:.0f}% on {road_label} with "
            f"{delay_seconds}s delay. Extending green phase by {ext}s to "
            f"maximise throughput on the incident approach."
        )
    elif congestion_pct > _MEDIUM_CONGESTION_THRESHOLD:
        ext = _MEDIUM_GREEN_EXTENSION_S
        conf = _MEDIUM_CONFIDENCE
        rationale = (
            f"Moderate congestion ({congestion_pct:.0f}%) on {road_label}. "
            f"Extending green phase by {ext}s to ease build-up."
        )
    else:
        ext = _NO_CHANGE_EXTENSION_S
        conf = _LOW_CONFIDENCE
        rationale = (
            f"Congestion on {road_label} is light ({congestion_pct:.0f}%). "
            f"No signal retiming required at this time."
        )

    return ext, conf, rationale


def _diversion_route_rules(
    congestion_pct: float,
    road_names: list[str],
) -> tuple[int, float, str]:
    """Return (green_extension_s, confidence, rationale) for a diversion intersection."""
    road_label = road_names[0] if road_names else "diversion route"

    if congestion_pct > _HIGH_CONGESTION_THRESHOLD:
        ext = _MEDIUM_GREEN_EXTENSION_S
        conf = _MEDIUM_CONFIDENCE
        rationale = (
            f"Diversion traffic expected on {road_label}. "
            f"Increasing cycle frequency to absorb redirected volume."
        )
    else:
        ext = _NO_CHANGE_EXTENSION_S
        conf = _MEDIUM_CONFIDENCE
        rationale = (
            f"Pre-emptive adjustment on {road_label} to handle potential "
            f"diversion traffic from nearby incident."
        )

    return ext, conf, rationale


def _build_action_description(
    on_incident_approach: bool,
    extension_s: int,
    approach: str,
    road_names: list[str],
    suggested_cycle: int,
    current_cycle: int,
) -> str:
    """Compose a concise human-readable action string for the operator."""
    road_label = road_names[0] if road_names else "intersection"
    approach_label = approach.replace("bound", "-bound")

    if extension_s > 0 and on_incident_approach:
        return (
            f"Extend {approach_label} green phase by {extension_s}s at {road_label} "
            f"(cycle: {current_cycle}s → {suggested_cycle}s)"
        )
    if not on_incident_approach and suggested_cycle < current_cycle:
        reduction = current_cycle - suggested_cycle
        return (
            f"Reduce cycle time by {reduction}s at {road_label} to increase "
            f"throughput on diversion route (cycle: {current_cycle}s → {suggested_cycle}s)"
        )
    return (
        f"Monitor {road_label} — no signal changes recommended (congestion within normal range)"
    )
