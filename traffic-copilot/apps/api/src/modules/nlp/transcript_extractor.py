"""
Extract structured incident signals from radio dispatch transcripts.

Primary path: Groq LLM call with extract_transcript_signals prompt.
Fallback path: keyword-based extraction when the LLM is unavailable.
"""

from __future__ import annotations

import json
import logging
import re

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompt template (inline fallback if the file-based prompt is unavailable)
# ---------------------------------------------------------------------------

_INLINE_PROMPT = """You are a traffic incident analysis assistant.
Extract structured information from the following radio/dispatch transcript.

Respond ONLY with valid JSON in this exact schema (no markdown, no prose):
{
  "incident_type": "<collision|breakdown|debris|flooding|fire|medical|pedestrian|road_hazard|null>",
  "location_text": "<raw location description from transcript or null>",
  "severity_hint": "<minor|major|critical|null>",
  "lane_info": "<lane blockage description or null>",
  "units_responding": ["<unit_id>", ...],
  "confidence": <float 0.0-1.0>
}

Transcript:
{transcript}
"""

# ---------------------------------------------------------------------------
# Keyword dictionaries for the fallback extractor
# ---------------------------------------------------------------------------

_INCIDENT_TYPE_KEYWORDS: dict[str, list[str]] = {
    "collision": ["crash", "accident", "collision", "hit", "struck", "rear-end", "fender"],
    "breakdown": ["breakdown", "disabled vehicle", "stalled", "broken down", "flat tyre", "flat tire"],
    "debris": ["debris", "obstacle", "object in road", "spill", "spillage"],
    "flooding": ["flood", "flooding", "water on road", "standing water"],
    "fire": ["fire", "flames", "burning", "smoke"],
    "medical": ["injury", "injured", "medical", "ambulance", "ems", "paramedic"],
    "pedestrian": ["pedestrian", "person on road", "walker"],
    "road_hazard": ["pothole", "ice", "oil", "slippery", "hazard"],
}

_SEVERITY_KEYWORDS: dict[str, list[str]] = {
    "critical": ["critical", "fatality", "fatal", "serious injury", "overturned", "rollover", "multiple vehicles"],
    "major": ["major", "significant", "blocking", "all lanes", "freeway closed", "highway closed", "injury"],
    "minor": ["minor", "fender bender", "no injury", "shoulder", "partial"],
}

_LANE_KEYWORDS = [
    "left lane", "right lane", "centre lane", "center lane",
    "all lanes", "shoulder", "hard shoulder", "lane blocked",
    "two lanes", "three lanes", "exit ramp",
]

_UNIT_PATTERN = re.compile(
    r"\b(?:unit|car|engine|truck|squad|patrol|medic|haz-?mat|alpha|bravo|charlie|delta)\s*[-]?\s*\d+\b",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def extract_incident_signals(transcript: str, groq_client) -> dict:
    """Extract structured incident data from a radio transcript via Groq.

    Args:
        transcript:   Raw text from the radio/CAD transcript.
        groq_client:  An initialised Groq async client instance.

    Returns a dict with keys:
        incident_type, location_text, severity_hint, lane_info,
        units_responding, confidence
    Falls back to keyword extraction if the Groq call fails or returns
    unparseable output.
    """
    if not transcript or not transcript.strip():
        return _empty_result()

    if groq_client is None:
        logger.warning("extract_incident_signals: groq_client is None — using keyword fallback")
        return keyword_fallback_extraction(transcript)

    prompt_text = _build_prompt(transcript)

    try:
        response = await groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "You are a traffic incident analysis assistant. Respond only with valid JSON."},
                {"role": "user", "content": prompt_text},
            ],
            temperature=0.0,
            max_tokens=512,
        )
        raw_text = response.choices[0].message.content or ""
        result = _parse_llm_response(raw_text)
        if result is not None:
            logger.debug("extract_incident_signals: LLM extraction succeeded")
            return result
        logger.warning("extract_incident_signals: LLM returned unparseable JSON — falling back")
    except Exception:
        logger.exception("extract_incident_signals: Groq call failed — falling back to keywords")

    return keyword_fallback_extraction(transcript)


def keyword_fallback_extraction(transcript: str) -> dict:
    """Simple keyword-based extraction when the LLM is unavailable.

    Scans for known incident-type words, severity markers, lane blockage
    language, and unit identifiers.

    Returns a dict matching the same schema as extract_incident_signals.
    """
    if not transcript:
        return _empty_result()

    lower = transcript.lower()

    incident_type = _match_keywords(lower, _INCIDENT_TYPE_KEYWORDS)
    severity_hint = _match_keywords(lower, _SEVERITY_KEYWORDS)
    lane_info = _extract_lane_info(lower)
    units_responding = _extract_units(transcript)
    location_text = _extract_location_hint(transcript)

    # Confidence is low for pure keyword matching.
    found_fields = sum([
        incident_type is not None,
        location_text is not None,
        severity_hint is not None,
        lane_info is not None,
        len(units_responding) > 0,
    ])
    confidence = round(min(0.6, 0.1 + found_fields * 0.1), 2)

    return {
        "incident_type": incident_type,
        "location_text": location_text,
        "severity_hint": severity_hint,
        "lane_info": lane_info,
        "units_responding": units_responding,
        "confidence": confidence,
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_prompt(transcript: str) -> str:
    """Attempt to load the prompt template from disk; fall back to inline."""
    try:
        from src.core.config import settings  # type: ignore[attr-defined]
        import os
        prompt_path = os.path.join(settings.prompts_dir, "tasks", "extract_transcript_signals.txt")
        with open(prompt_path) as fh:
            template = fh.read()
        if "{transcript}" in template:
            return template.replace("{transcript}", transcript)
        return template + "\n\nTranscript:\n" + transcript
    except Exception:
        return _INLINE_PROMPT.replace("{transcript}", transcript)


def _parse_llm_response(raw: str) -> dict | None:
    """Attempt to parse the LLM output as JSON.  Returns None on failure."""
    raw = raw.strip()

    # Strip markdown code fences if present.
    raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
    raw = re.sub(r"\s*```$", "", raw)
    raw = raw.strip()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        # Try to extract a JSON object from somewhere in the string.
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            return None
        try:
            data = json.loads(match.group())
        except json.JSONDecodeError:
            return None

    # Validate required keys.
    required = {"incident_type", "location_text", "severity_hint", "lane_info", "units_responding", "confidence"}
    if not required.issubset(data.keys()):
        # Fill missing keys with None/defaults.
        for key in required:
            data.setdefault(key, None)

    # Normalise units_responding to a list.
    if not isinstance(data.get("units_responding"), list):
        raw_units = data.get("units_responding")
        data["units_responding"] = [str(raw_units)] if raw_units else []

    # Clamp confidence.
    try:
        data["confidence"] = max(0.0, min(1.0, float(data.get("confidence", 0.5))))
    except (TypeError, ValueError):
        data["confidence"] = 0.5

    return data


def _match_keywords(text: str, keyword_map: dict[str, list[str]]) -> str | None:
    """Return the first category whose keywords appear in *text*."""
    for category, keywords in keyword_map.items():
        for kw in keywords:
            if kw in text:
                return category
    return None


def _extract_lane_info(lower: str) -> str | None:
    for phrase in _LANE_KEYWORDS:
        if phrase in lower:
            # Return the surrounding context (up to 40 chars).
            idx = lower.find(phrase)
            start = max(0, idx - 5)
            end = min(len(lower), idx + len(phrase) + 20)
            return lower[start:end].strip()
    return None


def _extract_units(transcript: str) -> list[str]:
    matches = _UNIT_PATTERN.findall(transcript)
    seen: set[str] = set()
    result: list[str] = []
    for m in matches:
        normalised = re.sub(r"\s+", " ", m.strip().upper())
        if normalised not in seen:
            seen.add(normalised)
            result.append(normalised)
    return result


def _extract_location_hint(transcript: str) -> str | None:
    """Heuristic: find the first capitalised proper-noun-style phrase that
    looks like a road name or intersection."""
    road_pattern = re.compile(
        r"\b(?:on|at|near|approaching|intersection of|junction of)\s+([A-Z][A-Za-z0-9 \-/']{3,40})",
    )
    m = road_pattern.search(transcript)
    if m:
        return m.group(1).strip()

    # Fallback: look for "Xth Street / Avenue / Boulevard / Highway" patterns.
    fallback = re.compile(
        r"\b([A-Z][A-Za-z0-9 \-]{2,30}\s+(?:Street|St|Avenue|Ave|Boulevard|Blvd|Road|Rd|Highway|Hwy|Freeway|Interstate|I-\d+))\b"
    )
    m2 = fallback.search(transcript)
    if m2:
        return m2.group(1).strip()

    return None


def _empty_result() -> dict:
    return {
        "incident_type": None,
        "location_text": None,
        "severity_hint": None,
        "lane_info": None,
        "units_responding": [],
        "confidence": 0.0,
    }
