
from __future__ import annotations

import logging
import sys
from typing import Any

import structlog
from structlog.types import EventDict, Processor

from src.core.config import settings


def _add_service_name(
    logger: Any,  # noqa: ANN401
    method: str,
    event_dict: EventDict,
) -> EventDict:
    """Inject a constant 'service' key into every log record."""
    event_dict.setdefault("service", "trafficcopilot-api")
    event_dict.setdefault("environment", settings.environment)
    return event_dict


def _drop_color_message_key(
    logger: Any,  # noqa: ANN401
    method: str,
    event_dict: EventDict,
) -> EventDict:
    """
    uvicorn emits a 'color_message' key alongside 'message'.
    Drop it to keep logs clean.
    """
    event_dict.pop("color_message", None)
    return event_dict


def configure_logging() -> None:
    """
    Call once at application startup (e.g. inside the FastAPI lifespan handler
    or at module import time).  Idempotent — safe to call multiple times.
    """
    log_level_name = settings.log_level.upper()
    log_level = getattr(logging, log_level_name, logging.INFO)

    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        _add_service_name,
        _drop_color_message_key,
    ]

    if settings.is_production:
        # ------------------------------------------------------------------
        # Production: newline-delimited JSON for log shippers
        # ------------------------------------------------------------------
        renderer: Processor = structlog.processors.JSONRenderer()
        structlog.configure(
            processors=[
                *shared_processors,
                structlog.processors.format_exc_info,
                structlog.processors.UnicodeDecoder(),
                renderer,
            ],
            wrapper_class=structlog.make_filtering_bound_logger(log_level),
            context_class=dict,
            logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
            cache_logger_on_first_use=True,
        )
    else:
        # ------------------------------------------------------------------
        # Development: pretty console output with colour
        # ------------------------------------------------------------------
        renderer = structlog.dev.ConsoleRenderer(colors=True)
        structlog.configure(
            processors=[
                *shared_processors,
                structlog.dev.set_exc_info,
                renderer,
            ],
            wrapper_class=structlog.make_filtering_bound_logger(log_level),
            context_class=dict,
            logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
            cache_logger_on_first_use=False,  # Allows reconfiguration in tests
        )

    # ------------------------------------------------------------------
    # Route stdlib logging through structlog so third-party libs (SQLAlchemy,
    # aiokafka, uvicorn …) also produce structured output.
    # ------------------------------------------------------------------
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )
    for name in ("uvicorn", "uvicorn.access", "uvicorn.error", "sqlalchemy.engine"):
        logging.getLogger(name).setLevel(log_level)


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """
    Return a bound structlog logger.

    Parameters
    ----------
    name:
        Typically ``__name__`` of the calling module.  When omitted a root
        logger is returned.

    Returns
    -------
    structlog.stdlib.BoundLogger
        A logger with all shared processors already wired in.
    """
    return structlog.get_logger(name)


# ---------------------------------------------------------------------------
# Auto-configure on import so that simply doing ``from src.core.logging import
# get_logger`` is sufficient in workers / scripts.
# ---------------------------------------------------------------------------
configure_logging()
