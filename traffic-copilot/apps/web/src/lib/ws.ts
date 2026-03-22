/**
 * WebSocket client for /ws/{incident_id}
 *
 * Maintains a single WebSocket connection per incident. Automatically
 * reconnects with exponential back-off when the connection drops.
 *
 * Exports:
 *   connectToIncident(incidentId, onMessage) → WebSocket
 *   disconnect()
 */

const _httpBase =
  (typeof process !== "undefined" && process.env.NEXT_PUBLIC_BACKEND_URL) ||
  "http://localhost:8000";
const WS_BASE = _httpBase.replace(/^http/, "ws");

const RECONNECT_BASE_MS = 1_000;
const RECONNECT_MAX_MS = 30_000;
const RECONNECT_JITTER_MS = 500;

export interface WSMessage {
  event_type: "state_updated" | "recommendation_ready" | "approval_actioned";
  incident_id: string;
  data: Record<string, unknown>;
}

// ── Internal state ────────────────────────────────────────────────────────────

let _socket: WebSocket | null = null;
let _incidentId: string | null = null;
let _onMessage: ((msg: WSMessage) => void) | null = null;
let _reconnectTimer: ReturnType<typeof setTimeout> | null = null;
let _attemptCount = 0;
let _manuallyDisconnected = false;

// ── Helpers ───────────────────────────────────────────────────────────────────

function _clearReconnectTimer(): void {
  if (_reconnectTimer !== null) {
    clearTimeout(_reconnectTimer);
    _reconnectTimer = null;
  }
}

function _reconnectDelay(): number {
  const exponential = RECONNECT_BASE_MS * Math.pow(2, _attemptCount);
  const capped = Math.min(exponential, RECONNECT_MAX_MS);
  const jitter = Math.random() * RECONNECT_JITTER_MS;
  return capped + jitter;
}

function _open(): WebSocket {
  const url = `${WS_BASE}/ws/${_incidentId}`;
  const ws = new WebSocket(url);

  ws.onopen = () => {
    _attemptCount = 0;
    console.debug(`[TrafficCopilot WS] connected → ${url}`);
  };

  ws.onmessage = (event: MessageEvent) => {
    try {
      const msg = JSON.parse(event.data as string) as WSMessage;
      _onMessage?.(msg);
    } catch (err) {
      console.warn("[TrafficCopilot WS] failed to parse message", err);
    }
  };

  ws.onerror = (event) => {
    console.warn("[TrafficCopilot WS] error", event);
  };

  ws.onclose = (event) => {
    console.debug(
      `[TrafficCopilot WS] closed (code=${event.code}, clean=${event.wasClean})`
    );

    if (_manuallyDisconnected) return;

    _attemptCount += 1;
    const delay = _reconnectDelay();
    console.debug(
      `[TrafficCopilot WS] reconnecting in ${Math.round(delay)}ms (attempt ${_attemptCount})`
    );
    _reconnectTimer = setTimeout(() => {
      if (!_manuallyDisconnected && _incidentId) {
        _socket = _open();
      }
    }, delay);
  };

  return ws;
}

// ── Public API ────────────────────────────────────────────────────────────────

/**
 * Open (or re-use) a WebSocket connection to the given incident channel.
 *
 * If a connection to a *different* incident is already open, it is closed
 * before establishing the new one.
 *
 * @param incidentId  The UUID of the incident to subscribe to.
 * @param onMessage   Callback invoked with each validated WSMessage.
 * @returns           The underlying WebSocket instance.
 */
export function connectToIncident(
  incidentId: string,
  onMessage: (msg: WSMessage) => void
): WebSocket {
  // Reuse if already connected to the same incident
  if (
    _socket !== null &&
    _incidentId === incidentId &&
    (_socket.readyState === WebSocket.OPEN ||
      _socket.readyState === WebSocket.CONNECTING)
  ) {
    _onMessage = onMessage;
    return _socket;
  }

  // Close existing connection if switching incidents
  if (_socket !== null) {
    _manuallyDisconnected = true;
    _clearReconnectTimer();
    _socket.close(1000, "switching incident");
    _socket = null;
  }

  _incidentId = incidentId;
  _onMessage = onMessage;
  _attemptCount = 0;
  _manuallyDisconnected = false;

  _socket = _open();
  return _socket;
}

/**
 * Close the current WebSocket connection and suppress automatic reconnection.
 */
export function disconnect(): void {
  _manuallyDisconnected = true;
  _clearReconnectTimer();

  if (_socket !== null) {
    _socket.close(1000, "client disconnect");
    _socket = null;
  }

  _incidentId = null;
  _onMessage = null;
  _attemptCount = 0;
}
