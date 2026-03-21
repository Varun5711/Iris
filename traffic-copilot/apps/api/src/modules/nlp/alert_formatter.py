"""
Channel-specific alert formatting and validation.

Enforces hard constraints per channel (VMS, radio, social media) and
provides an abbreviation layer for VMS where character space is precious.
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Channel limits
# ---------------------------------------------------------------------------

VMS_MAX_CHARS = 100
RADIO_MAX_WORDS = 50
SOCIAL_MAX_CHARS = 280

# ---------------------------------------------------------------------------
# Abbreviation table (case-insensitive matching; output is uppercase for VMS)
# ---------------------------------------------------------------------------

ABBREVIATIONS: dict[str, str] = {
    "northbound": "NB",
    "southbound": "SB",
    "eastbound": "EB",
    "westbound": "WB",
    "interstate": "I-",
    "highway": "HWY",
    "avenue": "AVE",
    "boulevard": "BLVD",
    "accident": "ACCT",
    "expect": "EXPCT",
    "minutes": "MIN",
    "road": "RD",
    "street": "ST",
    "drive": "DR",
    "lane": "LN",
    "place": "PL",
    "court": "CT",
    "traffic": "TRAF",
    "congestion": "CONG",
    "incident": "INC",
    "emergency": "EMRG",
    "delay": "DLY",
    "delays": "DLYS",
    "approximately": "APPROX",
    "junction": "JCT",
    "interchange": "XCHG",
    "construction": "CNSTR",
    "closed": "CLSD",
    "diversion": "DIV",
    "information": "INFO",
    "proceed": "PROC",
    "caution": "CAUT",
}

# Pre-compile a replacement regex for efficiency.  Match whole words only.
_ABBREV_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(k) for k in ABBREVIATIONS) + r")\b",
    re.IGNORECASE,
)

# Social media hashtag set appended when congestion/incident keywords found.
_SOCIAL_HASHTAGS: dict[str, str] = {
    "accident": "#TrafficAlert #Accident",
    "collision": "#TrafficAlert #Collision",
    "breakdown": "#TrafficAlert #Breakdown",
    "closed": "#RoadClosed",
    "delay": "#TrafficDelay",
    "congestion": "#Congestion",
    "flood": "#Flooding",
    "incident": "#TrafficAlert",
}

_SOCIAL_EMOJI = "🚨"


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------

def format_vms(text: str) -> str:
    """Format text for Variable Message Signs.

    Rules:
    - Convert to UPPERCASE.
    - Apply standard abbreviations.
    - Truncate to VMS_MAX_CHARS (100 chars), cutting at last space if possible.

    Returns the formatted string (never exceeds VMS_MAX_CHARS).
    """
    if not text:
        return ""

    upper = text.upper()

    # Apply abbreviations (already uppercase map; matching is case-insensitive).
    def _replace(m: re.Match) -> str:
        return ABBREVIATIONS[m.group(0).lower()]

    abbreviated = _ABBREV_PATTERN.sub(_replace, upper)

    # Remove multiple spaces.
    abbreviated = re.sub(r"\s+", " ", abbreviated).strip()

    # Truncate to VMS_MAX_CHARS.
    if len(abbreviated) <= VMS_MAX_CHARS:
        return abbreviated

    truncated = abbreviated[:VMS_MAX_CHARS]
    last_space = truncated.rfind(" ")
    if last_space > VMS_MAX_CHARS // 2:
        return truncated[:last_space].strip()
    return truncated.strip()


def format_radio(text: str) -> str:
    """Format text for radio broadcast.

    Rules:
    - Sentence case (first letter capitalised, rest lowercase-ish as entered).
    - Maximum RADIO_MAX_WORDS (50) words; trim at last full word.
    - Ensure the text ends with a period.

    Returns the formatted string.
    """
    if not text:
        return ""

    # Sentence-case: capitalise the first letter, leave the rest unchanged
    # (preserves proper nouns that are already capitalised).
    text = text.strip()
    if text:
        text = text[0].upper() + text[1:]

    # Remove excess whitespace.
    text = re.sub(r"\s+", " ", text)

    # Trim to RADIO_MAX_WORDS words.
    words = text.split()
    if len(words) > RADIO_MAX_WORDS:
        words = words[:RADIO_MAX_WORDS]
        text = " ".join(words)
        # Remove dangling punctuation from truncation boundary.
        text = re.sub(r"[,;:\-–—]+$", "", text).strip()

    # Ensure ends with a period.
    if not text.endswith("."):
        text = text.rstrip("!?") + "."

    return text


def format_social(text: str) -> str:
    """Format text for social media (Twitter/X style).

    Rules:
    - Maximum SOCIAL_MAX_CHARS (280) characters including emoji and hashtags.
    - Prepend 🚨 emoji if not already present.
    - Append relevant hashtags based on incident keywords.
    - Truncate body if necessary to fit all elements within the limit.

    Returns the formatted string.
    """
    if not text:
        return ""

    text = text.strip()

    # Determine relevant hashtags.
    lower = text.lower()
    hashtags_to_add: list[str] = []
    seen_tags: set[str] = set()
    for keyword, tag_string in _SOCIAL_HASHTAGS.items():
        if keyword in lower:
            for tag in tag_string.split():
                if tag not in seen_tags:
                    seen_tags.add(tag)
                    hashtags_to_add.append(tag)

    # Default hashtag if nothing matched.
    if not hashtags_to_add:
        hashtags_to_add = ["#TrafficUpdate"]

    hashtag_str = " ".join(hashtags_to_add)

    # Add leading emoji.
    if not text.startswith(_SOCIAL_EMOJI):
        body = f"{_SOCIAL_EMOJI} {text}"
    else:
        body = text

    # Calculate how much space body can occupy.
    # Format: "{body} {hashtags}"
    suffix = f" {hashtag_str}"
    max_body_chars = SOCIAL_MAX_CHARS - len(suffix)

    if len(body) > max_body_chars:
        truncated = body[:max_body_chars]
        last_space = truncated.rfind(" ")
        if last_space > max_body_chars // 2:
            body = truncated[:last_space].strip()
        else:
            body = truncated.strip()

    result = f"{body}{suffix}"

    # Final safety truncation.
    if len(result) > SOCIAL_MAX_CHARS:
        result = result[:SOCIAL_MAX_CHARS]

    return result


# ---------------------------------------------------------------------------
# Validator
# ---------------------------------------------------------------------------

def validate_alert(channel: str, text: str) -> tuple[bool, str]:
    """Check that *text* meets the formatting rules for *channel*.

    Args:
        channel: One of "vms", "radio", "social" (case-insensitive).
        text:    The alert text to validate.

    Returns (is_valid, error_message).  error_message is empty string on success.
    """
    if not text or not text.strip():
        return False, "Alert text is empty."

    channel_lower = channel.lower().strip()

    if channel_lower == "vms":
        if len(text) > VMS_MAX_CHARS:
            return False, f"VMS text exceeds {VMS_MAX_CHARS} characters ({len(text)} chars)."
        if text != text.upper():
            return False, "VMS text must be uppercase."
        return True, ""

    if channel_lower == "radio":
        words = text.split()
        if len(words) > RADIO_MAX_WORDS:
            return False, f"Radio text exceeds {RADIO_MAX_WORDS} words ({len(words)} words)."
        if not text.endswith("."):
            return False, "Radio text must end with a period."
        if not text[0].isupper():
            return False, "Radio text must start with an uppercase letter."
        return True, ""

    if channel_lower == "social":
        if len(text) > SOCIAL_MAX_CHARS:
            return False, f"Social text exceeds {SOCIAL_MAX_CHARS} characters ({len(text)} chars)."
        return True, ""

    return False, f"Unknown channel '{channel}'. Valid channels: vms, radio, social."
