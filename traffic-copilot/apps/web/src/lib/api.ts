/**
 * TrafficCopilot REST API client
 *
 * All functions are async and return the parsed JSON response.
 * Throws an ApiError on non-2xx responses.
 */

const BASE_URL = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";

// ── Error type ────────────────────────────────────────────────────────────────

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly detail: string,
    message?: string
  ) {
    super(message ?? `API error ${status}: ${detail}`);
    this.name = "ApiError";
  }
}

// ── Shared types ──────────────────────────────────────────────────────────────

export type IncidentSeverity = 1 | 2 | 3;
export type IncidentStatus = "open" | "updating" | "closed";
export type RecommendationStatus = "pending" | "approved" | "rejected" | "expired";
export type AlertChannel = "vms" | "radio" | "social" | "push";

export interface Incident {
  id: string;
  corridor_id: string;
  description: string;
  severity: IncidentSeverity;
  status: IncidentStatus;
  location_lat: number;
  location_lon: number;
  lanes_blocked: number;
  created_at: string;
  updated_at: string;
}

export interface RecommendedAction {
  id: string;
  action_type: "signal_plan" | "diversion" | "alert" | "lane_closure";
  title: string;
  description: string;
  sop_reference: string;
  confidence: number;
  status: RecommendationStatus;
}

export interface Recommendation {
  id: string;
  incident_id: string;
  summary: string;
  actions: RecommendedAction[];
  fallback_mode: boolean;
  created_at: string;
}

export interface PublicAlert {
  id: string;
  incident_id: string;
  channel: AlertChannel;
  message: string;
  status: "draft" | "approved" | "published";
  created_at: string;
  published_at?: string;
}

export interface CreateIncidentPayload {
  corridor_id: string;
  description: string;
  severity: IncidentSeverity;
  location_lat: number;
  location_lon: number;
  lanes_blocked?: number;
}

export interface AskQuestionPayload {
  incident_id: string;
  question: string;
  officer_id: string;
}

export interface AskQuestionResponse {
  answer: string;
  sources: string[];
  confidence: number;
}

// ── Internal fetch wrapper ────────────────────────────────────────────────────

async function _request<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${BASE_URL}${path}`;

  const response = await fetch(url, {
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
      ...options.headers,
    },
    ...options,
  });

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = (await response.json()) as { detail?: string };
      if (body.detail) detail = body.detail;
    } catch {
      // swallow JSON parse error; use statusText
    }
    throw new ApiError(response.status, detail);
  }

  // 204 No Content
  if (response.status === 204) return undefined as unknown as T;

  return response.json() as Promise<T>;
}

// ── Incidents ─────────────────────────────────────────────────────────────────

/**
 * Create a new traffic incident.
 */
export async function createIncident(
  payload: CreateIncidentPayload
): Promise<Incident> {
  return _request<Incident>("/incidents", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

/**
 * Fetch a single incident by ID.
 */
export async function getIncident(incidentId: string): Promise<Incident> {
  return _request<Incident>(`/incidents/${incidentId}`);
}

// ── Recommendations ───────────────────────────────────────────────────────────

/**
 * Fetch all recommendations for a given incident.
 */
export async function getRecommendations(
  incidentId: string
): Promise<Recommendation[]> {
  return _request<Recommendation[]>(
    `/incidents/${incidentId}/recommendations`
  );
}

/**
 * Approve an individual recommended action.
 *
 * @param recommendationId  The recommendation bundle ID.
 * @param actionId          The specific action ID within the bundle.
 * @param officerId         The officer approving the action.
 * @param notes             Optional officer notes.
 */
export async function approveRecommendation(
  recommendationId: string,
  actionId: string,
  officerId: string,
  notes?: string
): Promise<RecommendedAction> {
  return _request<RecommendedAction>(
    `/recommendations/${recommendationId}/actions/${actionId}/approve`,
    {
      method: "POST",
      body: JSON.stringify({ officer_id: officerId, notes }),
    }
  );
}

/**
 * Reject an individual recommended action.
 *
 * @param recommendationId  The recommendation bundle ID.
 * @param actionId          The specific action ID within the bundle.
 * @param officerId         The officer rejecting the action.
 * @param reason            Required rejection reason.
 */
export async function rejectRecommendation(
  recommendationId: string,
  actionId: string,
  officerId: string,
  reason: string
): Promise<RecommendedAction> {
  return _request<RecommendedAction>(
    `/recommendations/${recommendationId}/actions/${actionId}/reject`,
    {
      method: "POST",
      body: JSON.stringify({ officer_id: officerId, reason }),
    }
  );
}

// ── Q&A ───────────────────────────────────────────────────────────────────────

/**
 * Ask a natural-language question about an active incident.
 * The LLM answers using RAG over SOP documents and incident context.
 */
export async function askQuestion(
  payload: AskQuestionPayload
): Promise<AskQuestionResponse> {
  return _request<AskQuestionResponse>("/copilot/ask", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

// ── Alerts ────────────────────────────────────────────────────────────────────

/**
 * Fetch all public alerts for a given incident.
 */
export async function getAlerts(incidentId: string): Promise<PublicAlert[]> {
  return _request<PublicAlert[]>(`/incidents/${incidentId}/alerts`);
}

/**
 * Publish an approved alert to its target channel.
 * The alert must already be in `approved` status.
 *
 * @param alertId    The alert ID to publish.
 * @param officerId  The officer authorising publication.
 */
export async function publishAlert(
  alertId: string,
  officerId: string
): Promise<PublicAlert> {
  return _request<PublicAlert>(`/alerts/${alertId}/publish`, {
    method: "POST",
    body: JSON.stringify({ officer_id: officerId }),
  });
}
