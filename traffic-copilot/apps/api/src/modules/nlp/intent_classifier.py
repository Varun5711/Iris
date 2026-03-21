"""
Rule-based officer question intent classifier.

Deliberately contains no LLM call — this runs on the hot path before the
copilot decides whether to invoke Groq, so it must be synchronous and fast.
"""

from __future__ import annotations

import logging
import re
from enum import Enum

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enum
# ---------------------------------------------------------------------------

class OfficerIntent(str, Enum):
    STATUS_CHECK = "status_check"       # "how bad is it?"
    SAFETY_QUERY = "safety_query"       # "is it safe to open the lane?"
    ETA_QUERY = "eta_query"             # "when will it clear?"
    ACTION_REQUEST = "action_request"   # "should I reroute traffic?"
    SENSOR_QUERY = "sensor_query"       # "what's the speed on segment X?"
    GENERAL = "general"                 # everything else


# ---------------------------------------------------------------------------
# Keyword ruleset
# ---------------------------------------------------------------------------
# Each entry is (OfficerIntent, list-of-lowercase-keywords-or-phrases).
# Order matters: first match wins.

_RULES: list[tuple[OfficerIntent, list[str]]] = [
    (OfficerIntent.SENSOR_QUERY, [
        "speed", "sensor", "reading", "data", "segment",
        "flow rate", "vehicle count", "detector", "loop",
    ]),
    (OfficerIntent.SAFETY_QUERY, [
        "safe", "open", "shoulder", "reopen", "re-open",
        "clear to open", "is it ok", "is it okay",
    ]),
    (OfficerIntent.ETA_QUERY, [
        "when will", "how long", "clear", "resolve",
        "estimate", "eta", "time to clear", "how soon",
        "minutes until", "hours until",
    ]),
    (OfficerIntent.ACTION_REQUEST, [
        "should i", "should we", "recommend", "suggest",
        "divert", "reroute", "re-route", "redirect", "advice",
        "what do i do", "what should", "can you advise",
        "do you recommend",
    ]),
    (OfficerIntent.STATUS_CHECK, [
        "how bad", "how severe", "status", "update",
        "what's happening", "what is happening", "current situation",
        "latest", "any change", "overview",
    ]),
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def classify_intent(question: str) -> OfficerIntent:
    """Classify the intent of an officer's question using keyword rules.

    The classifier is case-insensitive and checks for each keyword/phrase as
    a substring of the normalised question text.  The first matching rule
    wins.  Returns OfficerIntent.GENERAL if no rule matches.

    Args:
        question: Free-form natural language question from the officer.

    Returns an OfficerIntent enum member.
    """
    if not question or not question.strip():
        return OfficerIntent.GENERAL

    normalised = question.lower().strip()
    # Remove punctuation noise to improve substring matching.
    normalised = re.sub(r"[?!.,;:\"']", " ", normalised)
    normalised = re.sub(r"\s+", " ", normalised)

    for intent, keywords in _RULES:
        for kw in keywords:
            if kw in normalised:
                logger.debug("classify_intent: matched '%s' → %s", kw, intent.value)
                return intent

    return OfficerIntent.GENERAL


def can_answer_without_llm(intent: OfficerIntent, context: dict) -> bool:
    """Return True when the question can be answered from cached sensor data.

    Currently only SENSOR_QUERY intents with fresh Redis data qualify for the
    fast path — all other intents require LLM reasoning.

    Args:
        intent:  Classified OfficerIntent.
        context: Context dict, typically built by context_builder.  Must
                 contain a "sensor_data" key with a non-empty dict and a
                 "data_age_seconds" key <= 60 to be considered fresh.

    Returns True if the intent is sensor-related and data is available and fresh.
    """
    if intent != OfficerIntent.SENSOR_QUERY:
        return False

    sensor_data = context.get("sensor_data")
    if not sensor_data or not isinstance(sensor_data, dict):
        return False

    data_age = context.get("data_age_seconds", 9999)
    try:
        age = float(data_age)
    except (TypeError, ValueError):
        return False

    return age <= 60.0  # Only trust data fresher than 60 seconds.


def answer_without_llm(intent: OfficerIntent, context: dict, question: str) -> str | None:
    """Return a direct answer for sensor queries from cached context.

    This is the fast path — avoids LLM latency for straightforward data
    lookups.  Returns None if the data is insufficient or the intent requires
    LLM reasoning.

    Args:
        intent:   The classified OfficerIntent.
        context:  Context dict with sensor_data, segment info, etc.
        question: Original officer question (used for context in the answer).

    Returns a formatted string answer, or None to signal that the LLM should
    be invoked.
    """
    if not can_answer_without_llm(intent, context):
        return None

    sensor_data = context.get("sensor_data", {})
    segment_id = context.get("segment_id", "the monitored segment")
    data_age = context.get("data_age_seconds", 0)

    speed_kph = sensor_data.get("speed_kph")
    flow_vph = sensor_data.get("flow_vph")
    occupancy_pct = sensor_data.get("occupancy_pct")

    parts: list[str] = [f"Current sensor readings for {segment_id}"]
    if speed_kph is not None:
        parts.append(f"speed: {speed_kph:.1f} km/h")
    if flow_vph is not None:
        parts.append(f"flow: {int(flow_vph)} veh/h")
    if occupancy_pct is not None:
        parts.append(f"occupancy: {occupancy_pct:.0f}%")

    if len(parts) == 1:
        return None  # No useful data to report.

    answer = " — ".join(parts[:1]) + " (" + ", ".join(parts[1:]) + ")"
    answer += f". Data is {int(data_age)}s old."
    return answer
