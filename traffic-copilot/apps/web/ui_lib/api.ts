import type { Incident, LogEntry, AnalyticsData, AlertAction } from "./types";

const BASE = "";

export async function fetchIncidents(): Promise<Incident[]> {
  const res = await fetch(`${BASE}/api/incidents`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch incidents");
  return res.json();
}

export async function fetchLogs(): Promise<LogEntry[]> {
  const res = await fetch(`${BASE}/api/logs`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch logs");
  return res.json();
}

export async function fetchAnalytics(): Promise<AnalyticsData> {
  const res = await fetch(`${BASE}/api/analytics`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch analytics");
  return res.json();
}

export async function postAlertAction(payload: AlertAction): Promise<{ success: boolean }> {
  const res = await fetch(`${BASE}/api/alerts/${payload.incidentId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error("Failed to submit action");
  return res.json();
}
