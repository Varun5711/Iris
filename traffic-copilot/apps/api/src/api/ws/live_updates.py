"""
WebSocket connection manager and FastAPI router for live incident updates.

ConnectionManager tracks per-incident rooms (sets of WebSocket connections).
The /ws/{incident_id} endpoint subscribes a client to a room and keeps the
connection alive with periodic ping messages.
"""

from __future__ import annotations

import asyncio
import json
from collections import defaultdict

import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = structlog.get_logger(__name__)

# How often to send a ping frame to keep connections alive and detect dead clients.
_PING_INTERVAL_SECONDS = 30


class ConnectionManager:
    """
    Per-incident WebSocket room manager.

    Rooms are keyed by incident_id (str).  Each room holds a set of active
    WebSocket connections.  Dead connections (those that raise an exception on
    send) are removed automatically during broadcast.
    """

    def __init__(self) -> None:
        self.rooms: dict[str, set[WebSocket]] = defaultdict(set)

    async def connect(self, incident_id: str, websocket: WebSocket) -> None:
        """Accept the WebSocket and add it to the incident room."""
        await websocket.accept()
        self.rooms[incident_id].add(websocket)
        logger.info(
            "ws: client connected",
            incident_id=incident_id,
            total_in_room=len(self.rooms[incident_id]),
        )

    async def disconnect(self, incident_id: str, websocket: WebSocket) -> None:
        """Remove the WebSocket from the incident room."""
        self.rooms[incident_id].discard(websocket)
        # Clean up empty rooms to avoid memory leaks.
        if not self.rooms[incident_id]:
            del self.rooms[incident_id]
        logger.info(
            "ws: client disconnected",
            incident_id=incident_id,
        )

    async def broadcast(self, incident_id: str, message: dict) -> None:
        """Send *message* (as JSON) to all clients in the incident room.

        Dead connections are detected during the send and removed from the room.
        """
        room = self.rooms.get(incident_id)
        if not room:
            return

        encoded = json.dumps(message, default=str)
        dead: list[WebSocket] = []

        for ws in list(room):
            try:
                await ws.send_text(encoded)
            except Exception as exc:
                logger.debug(
                    "ws: broadcast failed for client, marking dead",
                    incident_id=incident_id,
                    error=str(exc),
                )
                dead.append(ws)

        for ws in dead:
            room.discard(ws)

        if not room:
            self.rooms.pop(incident_id, None)

    async def broadcast_all(self, message: dict) -> None:
        """Broadcast *message* to ALL connected clients across all rooms."""
        encoded = json.dumps(message, default=str)
        dead_map: dict[str, list[WebSocket]] = defaultdict(list)

        for incident_id, room in list(self.rooms.items()):
            for ws in list(room):
                try:
                    await ws.send_text(encoded)
                except Exception as exc:
                    logger.debug(
                        "ws: broadcast_all failed for client, marking dead",
                        incident_id=incident_id,
                        error=str(exc),
                    )
                    dead_map[incident_id].append(ws)

        for incident_id, dead_list in dead_map.items():
            room = self.rooms.get(incident_id)
            if room:
                for ws in dead_list:
                    room.discard(ws)
                if not room:
                    self.rooms.pop(incident_id, None)

    def get_connection_count(self, incident_id: str) -> int:
        """Return the number of active connections in the given room."""
        return len(self.rooms.get(incident_id, set()))

    @property
    def total_connections(self) -> int:
        """Total number of active WebSocket connections across all rooms."""
        return sum(len(room) for room in self.rooms.values())


# ---------------------------------------------------------------------------
# Module-level singleton — imported by other modules (e.g. ws_fanout worker).
# ---------------------------------------------------------------------------

manager = ConnectionManager()

# ---------------------------------------------------------------------------
# FastAPI router
# ---------------------------------------------------------------------------

router = APIRouter(tags=["websocket"])


@router.websocket("/ws/{incident_id}")
async def websocket_endpoint(incident_id: str, websocket: WebSocket) -> None:
    """
    WebSocket endpoint for real-time incident updates.

    Clients connect to /ws/{incident_id} to subscribe to a room.
    The server sends a keep-alive ping every 30 seconds.
    Messages arrive from the ws_fanout worker via ConnectionManager.broadcast().
    """
    await manager.connect(incident_id, websocket)

    # Send an initial "connected" confirmation so the client knows the room is live.
    try:
        await websocket.send_text(
            json.dumps(
                {
                    "event_type": "connected",
                    "incident_id": incident_id,
                    "data": {"message": f"Subscribed to incident {incident_id}"},
                },
                default=str,
            )
        )
    except Exception:
        await manager.disconnect(incident_id, websocket)
        return

    # Keep-alive ping task.
    async def _ping_loop() -> None:
        while True:
            await asyncio.sleep(_PING_INTERVAL_SECONDS)
            try:
                await websocket.send_text(
                    json.dumps({"event_type": "ping", "incident_id": incident_id, "data": {}})
                )
            except Exception:
                # Connection is dead — the main loop will handle cleanup.
                return

    ping_task = asyncio.create_task(_ping_loop())

    try:
        # Wait for incoming messages (clients may send pong or other control frames).
        while True:
            try:
                raw = await websocket.receive_text()
                # Echo back pong if client sends ping.
                try:
                    msg = json.loads(raw)
                    if msg.get("event_type") == "ping":
                        await websocket.send_text(
                            json.dumps({"event_type": "pong", "incident_id": incident_id, "data": {}})
                        )
                except (json.JSONDecodeError, Exception):
                    pass
            except WebSocketDisconnect:
                break
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning(
                    "ws: unexpected error receiving message",
                    incident_id=incident_id,
                    error=str(exc),
                )
                break
    finally:
        ping_task.cancel()
        try:
            await ping_task
        except (asyncio.CancelledError, Exception):
            pass
        await manager.disconnect(incident_id, websocket)
