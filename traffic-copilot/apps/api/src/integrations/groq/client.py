"""
Groq async client — structured JSON completions + text embeddings.

Singleton pattern: one AsyncGroq instance is created on first use and reused
across the process lifetime.

Embedding fallback: Groq's embeddings endpoint is used when available.  If the
API call fails (model not found, quota, etc.) a deterministic mock embedding is
produced from the text's SHA-256 digest so the rest of the pipeline can keep
running during development without a valid API key.
"""

from __future__ import annotations

import hashlib
import json
import logging
import struct

from groq import AsyncGroq

from src.core.config import settings

logger = logging.getLogger(__name__)

_client: AsyncGroq | None = None

# Groq embedding model — falls back to mock if unavailable.
_EMBEDDING_MODEL = "nomic-embed-text"
# Target embedding dimension (matches pgvector schema).
_EMBEDDING_DIM = 1024


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


async def get_embedding(text: str) -> list[float]:
    """
    Generate a 1024-dimensional text embedding.

    Attempts the Groq embeddings endpoint first.  If that fails (the model is
    not available on this key / environment) it falls back to a deterministic
    pseudo-embedding derived from the SHA-256 of the text so that the
    pgvector search path still executes during local development.

    Parameters
    ----------
    text:
        Input text to embed.

    Returns
    -------
    list[float]
        A list of ``_EMBEDDING_DIM`` floats in the range [-1, 1].
    """
    if not text or not text.strip():
        logger.warning("get_embedding called with empty text — returning zero vector")
        return [0.0] * _EMBEDDING_DIM

    try:
        client = get_groq_client()
        response = await client.embeddings.create(
            model=_EMBEDDING_MODEL,
            input=text.strip(),
        )
        embedding = response.data[0].embedding

        # Groq nomic-embed-text returns 768 dims; pad or truncate to 1024.
        if len(embedding) < _EMBEDDING_DIM:
            embedding = embedding + [0.0] * (_EMBEDDING_DIM - len(embedding))
        elif len(embedding) > _EMBEDDING_DIM:
            embedding = embedding[:_EMBEDDING_DIM]

        logger.debug("Groq embedding generated dim=%d", len(embedding))
        return embedding

    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "get_embedding: Groq embeddings unavailable (%s: %s) — using deterministic mock",
            type(exc).__name__,
            exc,
        )
        return _mock_embedding(text)


def _mock_embedding(text: str) -> list[float]:
    """
    Produce a deterministic pseudo-embedding from the SHA-256 of *text*.

    The digest bytes are unpacked as little-endian floats and normalised to
    [-1, 1].  Because SHA-256 is deterministic, the same text always produces
    the same vector, which is sufficient for development-time similarity search.
    """
    digest = hashlib.sha256(text.encode("utf-8", errors="replace")).digest()

    # SHA-256 = 32 bytes.  Repeat to fill _EMBEDDING_DIM floats (each is 4 B).
    needed_bytes = _EMBEDDING_DIM * 4
    repeated = (digest * (needed_bytes // len(digest) + 1))[:needed_bytes]

    raw_floats = list(struct.unpack(f"<{_EMBEDDING_DIM}f", repeated))

    # Normalise to [-1, 1] by dividing by the max absolute value.
    max_abs = max(abs(v) for v in raw_floats) or 1.0
    return [v / max_abs for v in raw_floats]
