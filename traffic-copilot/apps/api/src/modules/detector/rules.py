"""
Per-source detection scoring rules for TrafficCopilot.

Each function accepts a typed event and returns a float confidence-score
contribution in the range [0.0, 1.0].  The weights define the maximum
contribution each source can make to the aggregate confidence.

Design rationale
----------------
- Sensor readings below a configurable speed ratio trigger a full weight
  contribution; degraded (but above threshold) readings contribute
  proportionally.
- Camera events contribute their model confidence scaled by the camera weight.
- Radio transcripts use keyword matching against a tiered vocabulary.
- Manual entries from officers are treated as near-certain evidence.
"""

from __future__ import annotations

import re

from src.schemas.event import (
    CameraMetaEvent,
    ManualIncidentEvent,
    RadioTranscriptEvent,
    SensorSpeedEvent,
    TrafficEvent,
)

# ---------------------------------------------------------------------------
# Source weights (maximum score contribution per source)
# ---------------------------------------------------------------------------

SPEED_WEIGHT: float = 0.4
CAMERA_WEIGHT: float = 0.4
RADIO_WEIGHT: float = 0.3
MANUAL_WEIGHT: float = 0.9

# ---------------------------------------------------------------------------
# Radio keyword vocabularies
# ---------------------------------------------------------------------------

# High-confidence keywords — strongly suggest an active incident
_STRONG_KEYWORDS: frozenset[str] = frozenset(
    {
        "crash",
        "accident",
        "collision",
        "blocked",
        "debris",
        "injury",
        "injured",
        "fatality",
        "fatal",
        "overturned",
        "rollover",
        "fire",
        "hazmat",
        "hazardous",
        "spillage",
    }
)

# Marginal keywords — suggest degraded conditions but not a confirmed incident
_MARGINAL_KEYWORDS: frozenset[str] = frozenset(
    {
        "slow",
        "stopped",
        "delay",
        "congestion",
        "backup",
        "queue",
        "standstill",
        "gridlock",
        "stall",
        "stalled",
    }
)


def _tokenise(text: str) -> list[str]:
    """Lowercase and split *text* into word tokens."""
    return re.findall(r"[a-z]+", text.lower())


# ---------------------------------------------------------------------------
# Sensor scoring
# ---------------------------------------------------------------------------


def score_sensor_event(
    event: SensorSpeedEvent,
    threshold_ratio: float = 0.4,
) -> float:
    """
    Score a speed-sensor reading based on speed degradation.

    Returns the full ``SPEED_WEIGHT`` (0.4) when the measured speed is below
    *threshold_ratio* × free-flow speed.  When speed is between
    *threshold_ratio* and 1.0 × free-flow speed the score scales linearly from
    ``SPEED_WEIGHT`` down to 0.0.  Speed at or above free-flow contributes 0.

    Parameters
    ----------
    event:
        Validated :class:`SensorSpeedEvent`.
    threshold_ratio:
        Fraction of free-flow speed below which a full score is returned.
        Default is 0.4 (speed < 40 % of free-flow).

    Returns
    -------
    float
        Score in ``[0.0, SPEED_WEIGHT]``.
    """
    if event.free_flow_kmh <= 0.0:
        return 0.0

    ratio: float = event.speed_kmh / event.free_flow_kmh

    if ratio <= threshold_ratio:
        # Speed well below threshold — full weight
        return SPEED_WEIGHT

    if ratio >= 1.0:
        # Speed at or above free-flow — no contribution
        return 0.0

    # Linear interpolation between full score (at threshold_ratio) and 0.0
    # (at free-flow).  The band (threshold_ratio, 1.0) maps to (SPEED_WEIGHT, 0).
    band = 1.0 - threshold_ratio
    position_in_band = ratio - threshold_ratio  # 0 at threshold, band at free-flow
    decay = 1.0 - (position_in_band / band)
    return round(SPEED_WEIGHT * decay, 4)


# ---------------------------------------------------------------------------
# Camera scoring
# ---------------------------------------------------------------------------


def score_camera_event(event: CameraMetaEvent) -> float:
    """
    Score a camera-pipeline metadata event.

    Returns ``event.confidence × CAMERA_WEIGHT`` when an incident was
    detected; zero otherwise.

    Parameters
    ----------
    event:
        Validated :class:`CameraMetaEvent`.

    Returns
    -------
    float
        Score in ``[0.0, CAMERA_WEIGHT]``.
    """
    if not event.incident_detected:
        return 0.0
    return round(event.confidence * CAMERA_WEIGHT, 4)


# ---------------------------------------------------------------------------
# Radio scoring
# ---------------------------------------------------------------------------


def score_radio_event(event: RadioTranscriptEvent) -> float:
    """
    Score a radio transcript by keyword presence.

    Scoring tiers
    ~~~~~~~~~~~~~
    - Any strong keyword (crash, accident, …): returns ``RADIO_WEIGHT`` (0.3)
    - Any marginal keyword (slow, stopped, …): returns ``RADIO_WEIGHT × 0.5``
      (i.e. 0.15)
    - No relevant keywords: returns 0.0

    Parameters
    ----------
    event:
        Validated :class:`RadioTranscriptEvent`.

    Returns
    -------
    float
        Score in ``[0.0, RADIO_WEIGHT]``.
    """
    tokens: set[str] = set(_tokenise(event.transcript))

    if tokens & _STRONG_KEYWORDS:
        return RADIO_WEIGHT

    if tokens & _MARGINAL_KEYWORDS:
        return round(RADIO_WEIGHT * 0.5, 4)

    return 0.0


# ---------------------------------------------------------------------------
# Manual scoring
# ---------------------------------------------------------------------------


def score_manual_event(event: ManualIncidentEvent) -> float:
    """
    Score a manually entered incident report.

    Manual reports from officers are treated as high-confidence evidence
    regardless of severity label.

    Parameters
    ----------
    event:
        Validated :class:`ManualIncidentEvent`.

    Returns
    -------
    float
        Always ``MANUAL_WEIGHT`` (0.9).
    """
    return MANUAL_WEIGHT


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------


def score_event(
    event: TrafficEvent,
    threshold_ratio: float = 0.4,
) -> float:
    """
    Dispatch *event* to the correct per-source scorer.

    Parameters
    ----------
    event:
        Any :class:`TrafficEvent` subclass.
    threshold_ratio:
        Speed-ratio threshold forwarded to :func:`score_sensor_event`.

    Returns
    -------
    float
        Confidence score contribution from this single event.

    Raises
    ------
    TypeError
        If *event* is not a recognised subclass.
    """
    if isinstance(event, SensorSpeedEvent):
        return score_sensor_event(event, threshold_ratio=threshold_ratio)
    if isinstance(event, CameraMetaEvent):
        return score_camera_event(event)
    if isinstance(event, RadioTranscriptEvent):
        return score_radio_event(event)
    if isinstance(event, ManualIncidentEvent):
        return score_manual_event(event)
    raise TypeError(
        f"Unrecognised event type {type(event).__name__!r}. "
        "Expected SensorSpeedEvent, CameraMetaEvent, "
        "RadioTranscriptEvent, or ManualIncidentEvent."
    )
