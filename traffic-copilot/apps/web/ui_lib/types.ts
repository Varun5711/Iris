export interface Incident {
  id: string;
  title: string;
  severity: "critical" | "high" | "moderate" | "low";
  location: string;
  lat: number;
  lng: number;
  detectedAt: string;
  status: "active" | "resolved" | "investigating";
  impactRadius: string;
  delayEstimate: string;
  description: string;
}

export interface LogEntry {
  id: string;
  type: "ai_autonomy" | "admin_override" | "system" | "critical" | "ai_inference";
  title: string;
  description: string;
  timestamp: string;
  actor: string;
  metadata?: Record<string, string>;
}

export interface AnalyticsData {
  vehicleCount: number;
  avgSpeed: number;
  incidentCount: number;
  signalEfficiency: number;
  responseTime: number;
  trafficTrend: { time: string; count: number }[];
  districtSpeeds: { district: string; speed: number }[];
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: string;
}

export interface AlertAction {
  incidentId: string;
  action: "approve" | "reject";
  timestamp: string;
}
