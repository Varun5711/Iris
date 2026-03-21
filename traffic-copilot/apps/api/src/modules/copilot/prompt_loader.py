"""
Prompt template loader for TrafficCopilot.

Prompts live under ``$PROMPTS_DIR`` (default ``/app/prompts``) in two
sub-directories:
    prompts/system/   — system-role prompts (officer_copilot.txt, etc.)
    prompts/tasks/    — task-specific user-role prompts

All loaded content is cached in memory after the first read so repeated calls
within a request add zero I/O overhead.
"""

from __future__ import annotations

import logging
from pathlib import Path

from src.core.config import settings

logger = logging.getLogger(__name__)

# In-memory cache: absolute path string → prompt text.
_cache: dict[str, str] = {}


def _prompts_root() -> Path:
    """Return the configured prompts root directory as a Path."""
    return Path(settings.prompts_dir)


def load_prompt(name: str) -> str:
    """
    Load a prompt file by name, searching ``tasks/`` then ``system/`` directories.

    The ``.txt`` extension is added automatically if not present.

    Parameters
    ----------
    name:
        Filename without extension, e.g. ``"summarize_incident"``.

    Returns
    -------
    str
        Raw prompt text with leading/trailing whitespace stripped.

    Raises
    ------
    FileNotFoundError
        If the file is not found in either search location.
    """
    filename = name if name.endswith(".txt") else f"{name}.txt"
    root = _prompts_root()

    candidates = [
        root / "tasks" / filename,
        root / "system" / filename,
    ]

    for path in candidates:
        key = str(path)
        if key in _cache:
            return _cache[key]
        if path.exists():
            text = path.read_text(encoding="utf-8").strip()
            _cache[key] = text
            logger.debug("Loaded prompt %s from %s", name, path)
            return text

    searched = ", ".join(str(p) for p in candidates)
    raise FileNotFoundError(
        f"Prompt '{name}' not found. Searched: {searched}. "
        f"Check that PROMPTS_DIR ({settings.prompts_dir}) is correct and the file exists."
    )


def load_system_prompt(name: str) -> str:
    """
    Load a prompt from the ``prompts/system/`` directory.

    Parameters
    ----------
    name:
        Filename without extension, e.g. ``"officer_copilot"``.

    Returns
    -------
    str
        Raw prompt text.

    Raises
    ------
    FileNotFoundError
        If the file does not exist in ``prompts/system/``.
    """
    filename = name if name.endswith(".txt") else f"{name}.txt"
    path = _prompts_root() / "system" / filename
    key = str(path)

    if key in _cache:
        return _cache[key]

    if not path.exists():
        raise FileNotFoundError(
            f"System prompt '{name}' not found at {path}. "
            f"Check that PROMPTS_DIR ({settings.prompts_dir}) is correct."
        )

    text = path.read_text(encoding="utf-8").strip()
    _cache[key] = text
    logger.debug("Loaded system prompt %s from %s", name, path)
    return text


def load_task_prompt(name: str) -> str:
    """
    Load a prompt from the ``prompts/tasks/`` directory.

    Parameters
    ----------
    name:
        Filename without extension, e.g. ``"summarize_incident"``.

    Returns
    -------
    str
        Raw prompt text.

    Raises
    ------
    FileNotFoundError
        If the file does not exist in ``prompts/tasks/``.
    """
    filename = name if name.endswith(".txt") else f"{name}.txt"
    path = _prompts_root() / "tasks" / filename
    key = str(path)

    if key in _cache:
        return _cache[key]

    if not path.exists():
        raise FileNotFoundError(
            f"Task prompt '{name}' not found at {path}. "
            f"Check that PROMPTS_DIR ({settings.prompts_dir}) is correct."
        )

    text = path.read_text(encoding="utf-8").strip()
    _cache[key] = text
    logger.debug("Loaded task prompt %s from %s", name, path)
    return text


def format_prompt(template: str, **kwargs: object) -> str:
    """
    Replace ``{key}`` placeholders in *template* with *kwargs* values.

    Uses :meth:`str.format_map` so missing keys raise ``KeyError``.

    Parameters
    ----------
    template:
        Prompt text containing ``{placeholder}`` markers.
    **kwargs:
        Values to substitute.

    Returns
    -------
    str
        Formatted prompt string.
    """
    return template.format_map(kwargs)


def clear_cache() -> None:
    """Flush the in-memory prompt cache (useful in tests)."""
    _cache.clear()
    logger.debug("Prompt cache cleared")
