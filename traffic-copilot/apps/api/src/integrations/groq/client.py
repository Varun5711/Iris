"""
Groq async client for chat completions plus local Hugging Face embeddings.

Singleton pattern: one AsyncGroq instance is created on first use and reused
across the process lifetime.

Embeddings are generated locally via a lazily loaded SentenceTransformer model.
If local model load or inference fails, a deterministic mock embedding is
produced from the text's SHA-256 digest so the rest of the pipeline can keep
running during development.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import struct
import threading

from groq import AsyncGroq

from src.core.config import settings

logger = logging.getLogger(__name__)

_client: AsyncGroq | None = None

_embedding_model = None
_embedding_lock = threading.Lock()


def get_groq_client() -> AsyncGroq:
    """Return (and lazily create) the shared AsyncGroq singleton."""
    global _client
    if _client is None:
        _client = AsyncGroq(api_key=settings.groq_api_key)
        logger.debug("AsyncGroq client initialised (model=%s)", settings.groq_model)
    return _client


# ---------------------------------------------------------------------------
# Chat completions — structured JSON output
# ---------------------------------------------------------------------------


async def call_copilot(system_prompt: str, user_prompt: str) -> dict:
    """
    Call Groq chat completions with ``response_format={"type": "json_object"}``.

    Parameters
    ----------
    system_prompt:
        The system-role message (officer_copilot.txt or similar).
    user_prompt:
        The user-role message containing serialised context.

    Returns
    -------
    dict
        Parsed JSON from the LLM response.

    Raises
    ------
    Exception
        Any Groq API error or JSON parse error propagates to the caller.
    """
    client = get_groq_client()

    response = await client.chat.completions.create(
        model=settings.groq_model,
        temperature=settings.llm_temperature,
        max_tokens=settings.llm_max_tokens,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )

    raw_text = response.choices[0].message.content
    parsed = json.loads(raw_text)

    logger.info(
        "Groq call completed model=%s prompt_tokens=%d completion_tokens=%d",
        settings.groq_model,
        response.usage.prompt_tokens if response.usage else 0,
        response.usage.completion_tokens if response.usage else 0,
    )
    return parsed


async def call_copilot_safe(system_prompt: str, user_prompt: str) -> dict | None:
    """
    Wrapper around :func:`call_copilot` that catches all exceptions.

    Returns
    -------
    dict | None
        Parsed response dict, or ``None`` if any error occurred.
    """
    try:
        return await call_copilot(system_prompt, user_prompt)
    except Exception as exc:  # noqa: BLE001
        logger.warning("call_copilot_safe: Groq call failed — %s: %s", type(exc).__name__, exc)
        return None


# ---------------------------------------------------------------------------
# Embeddings
# ---------------------------------------------------------------------------

# HuggingFace Inference API endpoint.
# The old /pipeline/feature-extraction/ path returned 410 Gone.
# The current path is /models/{model} with the same POST body.
_HF_EMBED_URL = "https://api-inference.huggingface.co/models/{model}"


async def get_embedding(text: str) -> list[float]:
    """
    Generate an embedding for *text*.

    Priority order
    --------------
    1. **HF Inference API** — if ``HF_API_TOKEN`` is set in the environment /
       .env, a free remote call is made to the HuggingFace hosted inference
       endpoint for ``EMBEDDING_MODEL_NAME``.  No local download required.
    2. **Mock** — if ``EMBEDDING_USE_MOCK=true`` (or the HF call fails), a
       deterministic SHA-256 pseudo-embedding is returned instantly.  Quality
       is sufficient for a hackathon demo; the same text always produces the
       same vector so similarity search still works between identical strings.

    The returned list is always exactly ``settings.embedding_dim`` floats.
    """
    if not text or not text.strip():
        logger.warning("get_embedding called with empty text — returning zero vector")
        return [0.0] * settings.embedding_dim

    clean = text.strip()

    # Fast path: deterministic mock (no network, no download).
    if settings.embedding_use_mock or not settings.hf_api_token:
        return _mock_embedding(clean)

    # HuggingFace Inference API — free tier, no model download.
    try:
        return await _hf_api_embedding(clean)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "get_embedding: HF API call failed (%s: %s) — falling back to mock",
            type(exc).__name__,
            exc,
        )
        return _mock_embedding(clean)


async def _hf_api_embedding(text: str) -> list[float]:
    """
    Call the HuggingFace Inference API for a single text embedding.

    Uses ``HF_API_TOKEN`` for auth and ``EMBEDDING_MODEL_NAME`` to select the
    model (e.g. ``sentence-transformers/all-MiniLM-L6-v2``).

    The raw response is a list (or nested list) of floats. We flatten, then
    pad/truncate to ``settings.embedding_dim``.
    """
    import httpx

    url = _HF_EMBED_URL.format(model=settings.embedding_model_name)
    headers = {
        "Authorization": f"Bearer {settings.hf_api_token}",
        "Content-Type": "application/json",
    }
    payload = {"inputs": text, "options": {"wait_for_model": True}}

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()

    # The API may return a nested list for batched inputs — flatten one level.
    if isinstance(data, list) and data and isinstance(data[0], list):
        embedding: list[float] = data[0]
    else:
        embedding = data  # type: ignore[assignment]

    # Pad or truncate to the target pgvector dimension.
    target_dim = settings.embedding_dim
    if len(embedding) < target_dim:
        embedding.extend([0.0] * (target_dim - len(embedding)))
    elif len(embedding) > target_dim:
        embedding = embedding[:target_dim]

    return embedding


def _mock_embedding(text: str) -> list[float]:
    """
    Produce a deterministic pseudo-embedding from the SHA-256 of *text*.

    The digest bytes are unpacked as little-endian floats and normalised to
    [-1, 1].  Because SHA-256 is deterministic, the same text always produces
    the same vector, which is sufficient for development-time similarity search.
    """
    import math

    digest = hashlib.sha256(text.encode("utf-8", errors="replace")).digest()

    # SHA-256 = 32 bytes.  Repeat to fill embedding_dim floats (each is 4 B).
    needed_bytes = settings.embedding_dim * 4
    repeated = (digest * (needed_bytes // len(digest) + 1))[:needed_bytes]

    raw_floats = list(struct.unpack(f"<{settings.embedding_dim}f", repeated))

    # Replace NaN / ±Inf with 0.0 — struct.unpack can produce these from raw bytes
    # and pgvector rejects them with "NaN not allowed in vector".
    raw_floats = [0.0 if not math.isfinite(v) else v for v in raw_floats]

    # Normalise to [-1, 1] by dividing by the max absolute value.
    max_abs = max((abs(v) for v in raw_floats), default=1.0) or 1.0
    return [v / max_abs for v in raw_floats]
