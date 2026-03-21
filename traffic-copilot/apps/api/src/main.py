"""
TrafficCopilot API — FastAPI application entry point.

Lifespan:
  STARTUP  → logging, Kafka producer, Redis, OSMnx graph, embedding sync,
             background workers (incident_processor, copilot_trigger,
             ws_fanout, feed_replay in dev)
  SHUTDOWN → cancel workers, stop Kafka producer + Redis
"""

from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.core.config import settings
from src.core.logging import configure_logging, get_logger

# Configure logging before anything else.
configure_logging()
logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Background task registry
# ---------------------------------------------------------------------------

_background_tasks: list[asyncio.Task] = []


def _spawn(coro, name: str) -> asyncio.Task:
    """Create an asyncio Task, register it, and attach a crash-log callback."""
    task = asyncio.create_task(coro, name=name)
    _background_tasks.append(task)

    def _on_done(t: asyncio.Task) -> None:
        if t.cancelled():
            return
        exc = t.exception()
        if exc is not None:
            logger.error("worker_crashed", worker=name, error=str(exc), exc_info=exc)

    task.add_done_callback(_on_done)
    return task


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # ── 1. Logging ────────────────────────────────────────────────────────
    configure_logging()
    log = get_logger("lifespan")
    log.info("startup_begin", environment=settings.environment)

    # ── 2. Kafka producer ─────────────────────────────────────────────────
    from src.integrations.kafka.producer import start_producer
    from src.integrations.kafka.topics import create_topics

    try:
        await start_producer(settings.kafka_bootstrap_servers)
        log.info("kafka_producer_started")
    except Exception as exc:
        log.error("kafka_producer_start_failed", error=str(exc))

    try:
        await create_topics(settings.kafka_bootstrap_servers)
        log.info("kafka_topics_ensured")
    except Exception as exc:
        log.warning("kafka_topic_creation_failed", error=str(exc))

    # ── 3. Redis ──────────────────────────────────────────────────────────
    from src.integrations.redis.client import start_redis

    try:
        await start_redis(settings.redis_url)
        log.info("redis_started")
    except Exception as exc:
        log.error("redis_start_failed", error=str(exc))

    # ── 4. OSMnx graph (best-effort, non-blocking) ────────────────────────
    from src.integrations.osm.loader import initialize_graph

    async def _init_graph() -> None:
        try:
            await initialize_graph(settings.osm_place_name, settings.osm_graph_cache)
            log.info("osm_graph_loaded", cache=settings.osm_graph_cache)
        except Exception as exc:
            log.warning(
                "osm_graph_load_failed",
                error=str(exc),
                hint="Run 'make graph' or set OSM_GRAPH_CACHE to a valid .gpickle path.",
            )

    asyncio.create_task(_init_graph(), name="osm_graph_init")

    # ── 5. Embedding sync (one-shot, non-blocking) ────────────────────────
    from src.db.session import AsyncSessionLocal
    from src.integrations.groq.client import get_groq_client
    from src.workers.embedding_sync import run_embedding_sync

    async def _embedding_sync() -> None:
        try:
            async with AsyncSessionLocal() as session:
                await run_embedding_sync(session, get_groq_client())
        except Exception as exc:
            log.warning("embedding_sync_failed", error=str(exc))

    _spawn(_embedding_sync(), name="embedding_sync")

    # ── 6. WebSocket connection manager ───────────────────────────────────
    from src.api.ws.live_updates import manager as ws_manager

    # ── 7. Background workers ─────────────────────────────────────────────
    from src.workers.incident_processor import run_incident_processor
    from src.workers.copilot_trigger import run_copilot_trigger
    from src.workers.ws_fanout import run_ws_fanout

    _spawn(run_incident_processor(), name="incident_processor")
    log.info("worker_started", worker="incident_processor")

    _spawn(run_copilot_trigger(), name="copilot_trigger")
    log.info("worker_started", worker="copilot_trigger")

    _spawn(run_ws_fanout(ws_manager), name="ws_fanout")
    log.info("worker_started", worker="ws_fanout")

    # Feed replay only in development.
    if settings.is_development:
        from src.workers.feed_replay import run_feed_replay

        replay_dir = settings.replay_scenario_dir
        replay_interval = settings.replay_interval_seconds
        _spawn(
            run_feed_replay(
                scenario_dir=replay_dir,
                interval_seconds=replay_interval,
                loop=True,
            ),
            name="feed_replay",
        )
        log.info("worker_started", worker="feed_replay", scenario=replay_dir)

    log.info("startup_complete", workers=len(_background_tasks))

    # ── yield (app is running) ────────────────────────────────────────────
    yield

    # ── SHUTDOWN ──────────────────────────────────────────────────────────
    log.info("shutdown_begin", active_workers=len(_background_tasks))

    for task in _background_tasks:
        if not task.done():
            task.cancel()

    await asyncio.gather(*_background_tasks, return_exceptions=True)
    _background_tasks.clear()

    from src.integrations.kafka.producer import stop_producer
    from src.integrations.redis.client import stop_redis

    try:
        await stop_producer()
    except Exception as exc:
        log.warning("kafka_producer_stop_error", error=str(exc))

    try:
        await stop_redis()
    except Exception as exc:
        log.warning("redis_stop_error", error=str(exc))

    log.info("shutdown_complete")


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(
    title="TrafficCopilot API",
    description=(
        "Officer-in-the-loop traffic incident co-pilot. "
        "Ingests live feeds, detects incidents, generates structured AI recommendations, "
        "and enforces human approval before any action is published."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── CORS (dev-friendly; tighten in production) ────────────────────────────
_cors_origins: list[str] = (
    ["*"]
    if settings.environment != "production"
    else os.getenv("CORS_ORIGINS", "").split(",")
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Prometheus metrics (optional) ─────────────────────────────────────────
try:
    from prometheus_fastapi_instrumentator import Instrumentator  # type: ignore[import]

    Instrumentator().instrument(app).expose(app, endpoint="/metrics")
    logger.debug("prometheus_metrics_enabled")
except ImportError:
    logger.debug("prometheus_fastapi_instrumentator not installed, /metrics unavailable")

# ── Routers ───────────────────────────────────────────────────────────────
from src.api.routes.incidents import router as incidents_router
from src.api.routes.recommendations import router as recommendations_router
from src.api.routes.alerts import router as alerts_router
from src.api.routes.chat import router as chat_router
from src.api.ws.live_updates import router as ws_router

app.include_router(incidents_router)
app.include_router(recommendations_router)
app.include_router(alerts_router)
app.include_router(chat_router)
app.include_router(ws_router)


# ── Health & root ─────────────────────────────────────────────────────────
@app.get("/health", tags=["ops"])
async def health() -> dict:
    """Liveness probe — always returns 200 quickly."""
    return {
        "status": "ok",
        "service": "trafficcopilot-api",
        "environment": settings.environment,
        "version": "1.0.0",
    }


@app.get("/health/ready", tags=["ops"])
async def ready() -> dict:
    """
    Readiness probe — checks Kafka producer and Redis connectivity.
    Returns 200 when ready, 503 when any dependency is unavailable.
    """
    from fastapi.responses import JSONResponse

    checks: dict[str, str] = {}
    all_ok = True

    try:
        from src.integrations.kafka.producer import get_producer
        await get_producer()
        checks["kafka"] = "ok"
    except Exception as exc:
        checks["kafka"] = f"unavailable: {exc}"
        all_ok = False

    try:
        from src.integrations.redis.client import get_redis
        redis = await get_redis()
        await redis.ping()
        checks["redis"] = "ok"
    except Exception as exc:
        checks["redis"] = f"unavailable: {exc}"
        all_ok = False

    payload = {"status": "ready" if all_ok else "degraded", "checks": checks}
    return JSONResponse(status_code=200 if all_ok else 503, content=payload)


@app.get("/", include_in_schema=False)
async def root() -> dict:
    return {"message": "TrafficCopilot API", "docs": "/docs", "health": "/health"}
