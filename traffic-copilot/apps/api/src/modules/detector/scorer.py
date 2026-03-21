"""
Multi-signal confidence aggregator for TrafficCopilot.

``IncidentScorer`` maintains a rolling confidence score for a single location
or corridor.  Signals decay exponentially over time so stale evidence does not
permanently inflate the confidence.

Usage
-----
    from src.modules.detector.scorer import IncidentScorer

    scorer = IncidentScorer(corridor_id="COR-001", decay_seconds=300)

    state = scorer.add_signal(sensor_event, score=0.4)
    if scorer.is_incident():
        print("Incident detected! confidence:", state.confidence)
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from src.schemas.event import TrafficEvent

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class DetectionState:
    """
    A snapshot of the current detection state for a corridor / location.

    Attributes
    ----------
    incident_id:
        UUID string of the active DB incident, or ``None`` if no incident
        has been created yet.
    confidence:
        Aggregate confidence score in ``[0.0, 1.0]``.  Combines contributions
        from all signals with exponential time-decay applied to older signals.
    contributing_events:
        List of dicts summarising each signal that contributed to the current
        confidence (for audit / UI display).
    last_updated:
        UTC timestamp of the most recent signal addition.
    signal_counts:
        Count of signals received per source type since the scorer was created.
    """

    incident_id: str | None
    confidence: float
    contributing_events: list[dict[str, Any]]
    last_updated: datetime
    signal_counts: dict[str, int]


# ---------------------------------------------------------------------------
# Scorer
# ---------------------------------------------------------------------------


class IncidentScorer:
    """
    Maintains rolling confidence for a single corridor or geo-cluster.

    Confidence Calculation
    ~~~~~~~~~~~~~~~~~~~~~~
    Each new signal contributes a weighted score.  Old signals are
    subject to exponential decay:  their effective contribution at time ``t``
    is ``score × exp(-λ × Δt)`` where ``λ = ln(2) / half_life`` and
    ``Δt`` is seconds since the signal arrived.  The half-life equals
    ``decay_seconds``.

    The aggregate confidence is the sum of all decayed contributions, capped
    at 1.0.

    Resolution Detection
    ~~~~~~~~~~~~~~~~~~~~
    The scorer tracks when the confidence first fell below
    ``all_clear_threshold``.  :meth:`should_resolve` returns ``True`` when
    the scorer has been below that threshold continuously for 5 minutes,
    signalling that the incident has likely cleared.

    Parameters
    ----------
    corridor_id:
        Identifier of the corridor or geo-cluster this scorer belongs to.
    decay_seconds:
        Signal half-life in seconds.  Defaults to 300 (5 minutes).
    """

    def __init__(self, corridor_id: str, decay_seconds: int = 300) -> None:
        self.corridor_id: str = corridor_id
        self.decay_seconds: int = decay_seconds
        # λ for exponential decay: confidence halves every decay_seconds
        self._lambda: float = math.log(2) / max(decay_seconds, 1)

        # Each signal is stored as (arrival_time, base_score, source, event_id)
        self._signals: list[tuple[datetime, float, str, str]] = []

        self._incident_id: str | None = None
        self._signal_counts: dict[str, int] = {}

        # Timestamp when confidence first dropped to all-clear level
        self._below_all_clear_since: datetime | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_signal(self, event: TrafficEvent, score: float) -> DetectionState:
        """
        Record a new signal and return the updated :class:`DetectionState`.

        Parameters
        ----------
        event:
            The raw traffic event that produced *score*.
        score:
            Contribution from the detection-rules scorer (0.0 – 1.0).

        Returns
        -------
        DetectionState
            Current aggregated state after incorporating the new signal.
        """
        now = datetime.now(tz=timezone.utc)
        source: str = event.source
        event_id: str = str(event.event_id)

        self._signals.append((now, score, source, event_id))
        self._signal_counts[source] = self._signal_counts.get(source, 0) + 1

        # Prune signals that have effectively decayed to zero
        # (effective contribution < 0.001 of original score)
        cutoff_seconds = -math.log(0.001) / self._lambda
        cutoff_dt = now - timedelta(seconds=cutoff_seconds)
        self._signals = [s for s in self._signals if s[0] >= cutoff_dt]

        return self.get_state()

    def get_state(self) -> DetectionState:
        """
        Compute and return the current :class:`DetectionState`.

        Time-decayed contributions are recalculated on each call so the
        state reflects the passage of time even without new signals.
        """
        now = datetime.now(tz=timezone.utc)

        total_confidence: float = 0.0
        contributing_events: list[dict[str, Any]] = []

        for arrival_time, base_score, source, event_id in self._signals:
            delta_seconds: float = (now - arrival_time).total_seconds()
            decayed_score: float = base_score * math.exp(-self._lambda * delta_seconds)
            if decayed_score < 1e-6:
                continue
            total_confidence += decayed_score
            contributing_events.append(
                {
                    "event_id": event_id,
                    "source": source,
                    "base_score": round(base_score, 4),
                    "decayed_score": round(decayed_score, 4),
                    "age_seconds": round(delta_seconds, 1),
                }
            )

        confidence: float = min(total_confidence, 1.0)

        last_updated: datetime = (
            self._signals[-1][0] if self._signals else now
        )

        return DetectionState(
            incident_id=self._incident_id,
            confidence=round(confidence, 4),
            contributing_events=contributing_events,
            last_updated=last_updated,
            signal_counts=dict(self._signal_counts),
        )

    def set_incident_id(self, incident_id: str) -> None:
        """Associate this scorer with a DB incident."""
        self._incident_id = incident_id

    def is_incident(self, threshold: float = 0.5) -> bool:
        """
        Return ``True`` when current confidence is at or above *threshold*.

        Parameters
        ----------
        threshold:
            Default is 0.5 — matches ``settings.detection_confidence_threshold``.
        """
        return self.get_state().confidence >= threshold

    def should_resolve(self, all_clear_threshold: float = 0.1) -> bool:
        """
        Return ``True`` when confidence has been below *all_clear_threshold*
        continuously for 5 or more minutes.

        Parameters
        ----------
        all_clear_threshold:
            Confidence level below which conditions are considered cleared.
            Defaults to 0.1.
        """
        now = datetime.now(tz=timezone.utc)
        current_confidence: float = self.get_state().confidence

        if current_confidence < all_clear_threshold:
            if self._below_all_clear_since is None:
                self._below_all_clear_since = now
            elapsed = (now - self._below_all_clear_since).total_seconds()
            return elapsed >= 300.0  # 5 minutes
        else:
            # Confidence recovered — reset the timer
            self._below_all_clear_since = None
            return False
