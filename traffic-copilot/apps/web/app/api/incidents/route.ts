import { NextResponse } from "next/server";

const BACKEND = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";

// Fallback mock data when backend is unavailable
const MOCK = [
  {
    id: "00000000-0000-0000-0000-000000000001",
    title: "Major Traffic Congestion: HWY 101 North",
    severity: "critical",
    location: "Central District, Sector 4B",
    lat: 40.7589,
    lng: -73.9851,
    detectedAt: new Date(Date.now() - 14 * 60000).toISOString(),
    status: "active",
    impactRadius: "1.2 km",
    delayEstimate: "+18m",
    description: "45% increase in traffic volume detected at HWY 101 Northbound. Secondary congestion on Oak St.",
    congestion_pct: 78,
    delay_seconds: 1080,
  },
  {
    id: "00000000-0000-0000-0000-000000000002",
    title: "Signal Malfunction: Exit 12",
    severity: "high",
    location: "Northern Gateway, Exit 12",
    lat: 40.7689,
    lng: -73.9651,
    detectedAt: new Date(Date.now() - 52 * 60000).toISOString(),
    status: "active",
    impactRadius: "0.4 km",
    delayEstimate: "+7m",
    description: "Traffic signal malfunction at Exit 12. Manual control active.",
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
      lat: (i.location_lat as number) ?? 40.7589,
      lng: (i.location_lon as number) ?? -73.9851,
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
