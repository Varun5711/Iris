"""
HuggingFace Inference API — image classification for incident detection.

Uses google/vit-base-patch16-224 (ViT, ImageNet-1k) via the HF Inference Router.
ImageNet labels are mapped to an incident-relevance score so the endpoint
produces a normalised confidence value without needing zero-shot classification.

New HF router URL: https://router.huggingface.co/hf-inference/models/{model}
"""

from __future__ import annotations

import structlog
import httpx

from src.core.config import settings

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# ImageNet label → incident weight mapping
# Higher weight = stronger signal that an incident is present.
# Labels are lower-cased substrings matched against the raw ImageNet class name.
# ---------------------------------------------------------------------------
_INCIDENT_KEYWORDS: dict[str, float] = {
    # Emergency vehicles (very strong signal)
    "ambulance": 1.0,
    "fire engine": 1.0,
    "fire truck": 1.0,
    "police van": 1.0,
    "police car": 1.0,
    # Crash / obstruction indicators
    "wreck": 0.9,
    "crash": 0.9,
    "wrecker": 0.9,          # "tow car, wrecker" label variant
    "tow truck": 0.9,
    "breakdown": 0.8,
    "moving van": 0.5,       # often misclassified overturned vehicles
    # Road / traffic objects (moderate signal)
    "traffic light": 0.4,
    "road": 0.3,
    "highway": 0.3,
    "minibus": 0.3,
    "car": 0.2,
    "truck": 0.2,
    "bus": 0.2,
    "motorcycle": 0.2,
    "bicycle": 0.15,
    "pedestrian": 0.15,
}

# Output labels we expose to callers (mapped from internal ImageNet labels)
_LABEL_FRIENDLY = {
    "ambulance": "emergency vehicle",
    "fire engine": "emergency vehicle",
    "fire truck": "emergency vehicle",
    "police van": "emergency vehicle",
    "police car": "emergency vehicle",
    "wreck": "vehicle collision",
    "crash": "vehicle collision",
    "tow truck": "road obstruction",
    "traffic light": "traffic infrastructure",
    "car": "normal traffic",
    "truck": "normal traffic",
    "bus": "normal traffic",
    "motorcycle": "normal traffic",
    "bicycle": "normal traffic",
    "pedestrian": "road obstruction",
}

_HF_ROUTER = "https://router.huggingface.co/hf-inference/models"
_VISION_MODEL = "google/vit-base-patch16-224"

# Top-N ImageNet predictions to consider
_TOP_K = 10


async def analyze_image(image_bytes: bytes, filename: str = "upload") -> dict:
    """
    Classify *image_bytes* using ViT (ImageNet-1k) via the HuggingFace Inference Router.

    Returns:
        {
            "incident_detected": bool,
            "confidence": float,       # weighted incident score in [0, 1]
            "top_label": str,          # friendly label for the top prediction
            "scores": {label: score},  # top-k raw predictions
            "model": str,
            "source": "huggingface" | "mock"
        }
    """
    threshold = settings.vision_confidence_threshold

    if not settings.hf_api_token:
        logger.warning("vision: hf_api_token not set — returning mock result")
        return _mock_result()

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{_HF_ROUTER}/{_VISION_MODEL}",
                headers={
                    "Authorization": f"Bearer {settings.hf_api_token}",
                    "Content-Type": "image/jpeg",
                    "x-wait-for-model": "true",
                },
                content=image_bytes,
            )

        if resp.status_code != 200:
            logger.warning(
                "vision: HF API returned non-200",
                status=resp.status_code,
                body=resp.text[:300],
                model=_VISION_MODEL,
            )
            return _mock_result()

        raw = resp.json()
        return _parse_vit_response(raw, threshold)

    except Exception as exc:
        logger.warning("vision: HF API call failed", error=str(exc), model=_VISION_MODEL)
        return _mock_result()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _parse_vit_response(raw: object, threshold: float) -> dict:
    """
    Parse ViT ImageNet response and compute an incident confidence score.

    HF returns:  [{label: str, score: float}, ...]  sorted by descending score.
    """
    if not isinstance(raw, list):
        logger.warning("vision: unexpected HF response format", raw=str(raw)[:200])
        return _mock_result()

    # Take top-k predictions
    top_preds = raw[:_TOP_K]

    # Build raw scores dict
    raw_scores: dict[str, float] = {}
    for item in top_preds:
        if isinstance(item, dict) and "label" in item and "score" in item:
            raw_scores[item["label"]] = float(item["score"])

    if not raw_scores:
        return _mock_result()

    # Compute weighted incident confidence
    incident_score = 0.0
    matched_keyword: str | None = None

    for imagenet_label, imagenet_score in raw_scores.items():
        label_lower = imagenet_label.lower()
        for keyword, weight in _INCIDENT_KEYWORDS.items():
            if keyword in label_lower:
                contribution = imagenet_score * weight
                if contribution > incident_score:
                    incident_score = contribution
                    matched_keyword = keyword
                break  # first match wins per label

    # Friendly label for the top raw prediction
    top_imagenet_label = top_preds[0].get("label", "unknown") if top_preds else "unknown"
    top_label = _friendly_label(top_imagenet_label, matched_keyword)

    incident_detected = incident_score >= threshold

    return {
        "incident_detected": incident_detected,
        "confidence": round(incident_score, 4),
        "top_label": top_label,
        "scores": {item["label"]: round(float(item["score"]), 4) for item in top_preds if "label" in item and "score" in item},
        "model": _VISION_MODEL,
        "source": "huggingface",
    }


def _friendly_label(imagenet_label: str, matched_keyword: str | None) -> str:
    """Map raw ImageNet label to a human-friendly traffic incident label."""
    if matched_keyword and matched_keyword in _LABEL_FRIENDLY:
        return _LABEL_FRIENDLY[matched_keyword]
    label_lower = imagenet_label.lower()
    for keyword, friendly in _LABEL_FRIENDLY.items():
        if keyword in label_lower:
            return friendly
    return "normal traffic"


def _mock_result() -> dict:
    return {
        "incident_detected": False,
        "confidence": 0.0,
        "top_label": "normal traffic",
        "scores": {},
        "model": _VISION_MODEL,
        "source": "mock",
    }
