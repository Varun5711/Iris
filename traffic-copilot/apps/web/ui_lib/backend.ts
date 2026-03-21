// Backend API client — proxies to FastAPI at NEXT_PUBLIC_BACKEND_URL
const BACKEND =
  typeof window !== "undefined"
    ? (process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000")
    : (process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000");

async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(`${BACKEND}${path}`, {
    headers: { "Content-Type": "application/json" },
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`Backend ${res.status}: ${path}`);
  return res.json();
}

async function apiPost<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BACKEND}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`Backend ${res.status}: ${path}`);
  return res.json();
}

// ── Incidents ──────────────────────────────────────────────────────────────
export type IncidentStatus = "active" | "monitoring" | "resolved" | "false_alarm";
export interface BackendIncident {
  id: string;
  status: IncidentStatus;
  severity: "low" | "medium" | "high" | "critical";
  description?: string;
  location_lat?: number;
  location_lon?: number;
  corridor_id?: string;
  reporter_id?: string;
  created_at: string;
  updated_at: string;
  detection_confidence?: number;
}
export interface BackendSegment {
  osm_way_id: number;
  delay_seconds: number;
  congestion_pct: number;
}
export interface BackendIncidentSnapshot {
  incident: BackendIncident;
  affected_segments: BackendSegment[];
  event_count: number;
  last_updated: string;
}

export const getIncidents = (status: IncidentStatus = "active", limit = 50) =>
  apiGet<BackendIncident[]>(`/incidents/?status=${status}&limit=${limit}`);

export const getIncident = (id: string) =>
  apiGet<BackendIncidentSnapshot>(`/incidents/${id}`);

export const getIncidentMapData = (id: string) =>
  apiGet<GeoJSON.FeatureCollection>(`/incidents/${id}/map-data`);

// ── Recommendations ────────────────────────────────────────────────────────
export interface SignalAction {
  intersection_id: string;
  action: string;
  expected_impact: string;
  confidence: number;
}
export interface DiversionWaypoint {
  name: string;
  lat: number;
  lng: number;
}
export interface DiversionPlan {
  route_description: string;
  estimated_extra_minutes: number;
  traffic_redistribution_pct: number;
  confidence: number;
  evidence_refs: string[];
  waypoints: DiversionWaypoint[];
}
export interface CopilotResponse {
  incident_summary: string;
  signal_actions: SignalAction[];
  diversion_plan?: DiversionPlan;
  alert_drafts: Array<{ channel: string; message: string; char_count: number }>;
  narrative: string;
  conversational_answer?: string;
  overall_confidence: number;
  review_required: boolean;
  blocked_reason?: string;
  evidence_refs: string[];
}
export interface BackendRecommendation {
  id: string;
  incident_id: string;
  rec_type: string;
  action: string;
  location?: string;
  expected_impact?: string;
  confidence?: number;
  blocked_reason?: string;
  review_required: boolean;
  status: "pending" | "approved" | "rejected" | "executed" | "expired";
  created_at: string;
  copilot_response?: CopilotResponse;
}

export const getRecommendations = (incidentId: string) =>
  apiGet<BackendRecommendation[]>(`/recommendations/${incidentId}`);

export const approveRecommendation = (recId: string, officerId = "officer-web") =>
  apiPost(`/recommendations/${recId}/approve`, { officer_id: officerId });

export const rejectRecommendation = (recId: string, officerId = "officer-web") =>
  apiPost(`/recommendations/${recId}/reject`, { officer_id: officerId });

// ── Chat ───────────────────────────────────────────────────────────────────
export const chatWithCopilot = (incidentId: string, question: string, officerId = "officer-web") =>
  apiPost<BackendRecommendation>(`/chat/`, {
    incident_id: incidentId,
    question,
    officer_id: officerId,
  });

// ── Alerts ─────────────────────────────────────────────────────────────────
export interface BackendAlert {
  id: string;
  recommendation_id: string;
  channel: string;
  draft_text: string;
  status: string;
  created_at: string;
}

export const getAlerts = (incidentId: string) =>
  apiGet<BackendAlert[]>(`/alerts/${incidentId}`);

export const publishAlert = (alertId: string, officerId = "officer-web") =>
  apiPost(`/alerts/${alertId}/publish`, { officer_id: officerId });

// ── Helpers ────────────────────────────────────────────────────────────────
export function getBackendWsUrl(incidentId: string): string {
  const base = BACKEND.replace(/^http/, "ws");
  return `${base}/ws/${incidentId}`;
}
