import { NextResponse } from "next/server";

const BACKEND = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";

function generateTrend() {
  const base = [250, 280, 320, 290, 310, 420, 560, 680, 720, 690, 650, 610];
  return base.map((v, i) => ({
    time: `${String(i * 2).padStart(2, "0")}:00`,
    count: v + Math.floor(Math.random() * 40 - 20),
  }));
}

export async function GET() {
  let incidentCount = 4;
  let avgCongestion = 52;
  let avgDelay = 18;
  let totalSegments = 0;
  let criticalSegments = 0;
  let backendOnline = false;

  try {
    const res = await fetch(`${BACKEND}/incidents/?status=active&limit=50`, {
      cache: "no-store",
      signal: AbortSignal.timeout(3000),
    });
    if (res.ok) {
      const incidents = await res.json();
      incidentCount = incidents.length;
      backendOnline = true;

      // Fetch first incident's segments for congestion data
      if (incidents.length > 0) {
        try {
          const snap = await fetch(`${BACKEND}/incidents/${incidents[0].id}`, {
            cache: "no-store",
            signal: AbortSignal.timeout(3000),
          });
          if (snap.ok) {
            const snapData = await snap.json();
            const segs = snapData.affected_segments ?? [];
            totalSegments = segs.length;
            criticalSegments = segs.filter((s: { congestion_pct: number }) => s.congestion_pct > 70).length;
            if (segs.length > 0) {
              avgCongestion = Math.round(
                segs.reduce((a: number, s: { congestion_pct: number }) => a + s.congestion_pct, 0) / segs.length
              );
              avgDelay = Math.round(
                segs.reduce((a: number, s: { delay_seconds: number }) => a + s.delay_seconds, 0) / segs.length
              );
            }
          }
        } catch {}
      }
    }
  } catch {}

  const vehicleCount = 137 + Math.floor(Math.random() * 20 - 10);
  const avgSpeed = Math.max(10, 55 - avgCongestion * 0.4 + Math.random() * 4 - 2);
  const signalEfficiency = Math.max(60, 98 - incidentCount * 1.5 - avgCongestion * 0.05);
  const trafficDensity = Math.min(100, avgCongestion + Math.floor(Math.random() * 10));

  return NextResponse.json({
    // Core KPIs
    vehicleCount,
    avgSpeed: Math.round(avgSpeed * 10) / 10,
    incidentCount,
    signalEfficiency: Math.round(signalEfficiency * 10) / 10,
    responseTime: 6.8,

    // Extended sensor metrics (from backend corridor data)
    avgCongestion,
    avgDelay,
    trafficDensity,
    totalSegments,
    criticalSegments,
    backendOnline,

    // Chart data
    trafficTrend: generateTrend(),
    districtSpeeds: [
      { district: "CG Road", speed: Math.max(10, 34 - (avgCongestion - 50) * 0.2) | 0 },
      { district: "SG Highway", speed: 52 + Math.floor(Math.random() * 4 - 2) },
      { district: "Ashram Road", speed: Math.max(8, 28 - (avgCongestion - 50) * 0.15) | 0 },
      { district: "SP Ring Road", speed: 48 + Math.floor(Math.random() * 4 - 2) },
    ],

    // Sensor metrics for dashboard
    sensorMetrics: {
      occupancy_pct: Math.min(95, avgCongestion + 5),
      free_flow_speed: 65,
      current_speed: Math.round(avgSpeed),
      volume_per_hour: vehicleCount * 60,
      headway_seconds: Math.round(3600 / (vehicleCount * 2)),
      lane_utilization: Math.min(100, avgCongestion * 1.2) | 0,
    },
  });
}
