import { NextResponse } from "next/server";

const BACKEND = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";

// Fallback mock data when backend is unavailable
const MOCK = [
  {
    id: "00000000-0000-0000-0000-000000000001",
    title: "CRITICAL — Pedestrian fatality at CG Road / Swastik Cross Roads",
    severity: "critical",
    location: "AMD-CGR-01",
    lat: 23.0269,
    lng: 72.5855,
    detectedAt: new Date(Date.now() - 14 * 60000).toISOString(),
    status: "active",
    impactRadius: "1.2 km",
    delayEstimate: "+18m",
    description: "Major accident at CG Road / Swastik Cross Roads. Road fully blocked.",
    congestion_pct: 78,
    delay_seconds: 1080,
  },
  {
    id: "00000000-0000-0000-0000-000000000002",
    title: "HIGH — Multi-vehicle collision at SG Highway junction",
    severity: "high",
    location: "AMD-SGH-01",
    lat: 23.0395,
    lng: 72.5039,
    detectedAt: new Date(Date.now() - 52 * 60000).toISOString(),
    status: "active",
    impactRadius: "0.4 km",
    delayEstimate: "+7m",
    description: "Multi-vehicle collision on SG Highway. Lane partially blocked.",
    congestion_pct: 45,
    delay_seconds: 420,
  },
];

export async function GET() {
  try {
    const res = await fetch(`${BACKEND}/incidents/?status=active&limit=50`, {
      cache: "no-store",
      signal: AbortSignal.timeout(3000),
    });
    if (!res.ok) throw new Error("backend error");
    const data = await res.json();

    // Normalise backend shape to our frontend shape
    const normalised = data.map((i: Record<string, unknown>) => ({
      id: i.id,
      title: `${String(i.severity ?? "").toUpperCase()} — ${i.description ?? "Incident"}`,
      severity: i.severity === "medium" ? "moderate" : i.severity,
      location: i.corridor_id ?? "Central District",
      lat: (i.location_lat as number) ?? 23.0269,
      lng: (i.location_lon as number) ?? 72.5855,
      detectedAt: i.created_at,
      status: i.status === "false_alarm" ? "resolved" : i.status,
      impactRadius: "—",
      delayEstimate: "—",
      description: i.description ?? "",
      detection_confidence: i.detection_confidence,
    }));

    return NextResponse.json(normalised);
  } catch {
    return NextResponse.json(MOCK);
  }
}
