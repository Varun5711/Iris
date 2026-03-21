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
  avgCongestion: number;
  avgDelay: number;
  trafficDensity: number;
  totalSegments: number;
  criticalSegments: number;
  backendOnline: boolean;
  trafficTrend: { time: string; count: number }[];
  districtSpeeds: { district: string; speed: number }[];
  sensorMetrics: {
    occupancy_pct: number;
    free_flow_speed: number;
    current_speed: number;
    volume_per_hour: number;
    headway_seconds: number;
    lane_utilization: number;
  };
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
