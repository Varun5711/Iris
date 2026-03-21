import { NextResponse } from "next/server";

const incidents = [
  {
    id: "INC-8821",
    title: "Major Traffic Congestion: HWY 101 North",
    severity: "critical",
    location: "Central District, Sector 4B",
    lat: 40.7589,
    lng: -73.9851,
    detectedAt: new Date(Date.now() - 14 * 60000).toISOString(),
    status: "active",
    impactRadius: "1.2 km",
    delayEstimate: "+18m",
    description: "An unexpected 45% increase in traffic volume detected at the HWY 101 Northbound exit. Secondary congestion forming on Oak St and 5th Ave due to spill-back.",
  },
  {
    id: "INC-8820",
    title: "Signal Malfunction: Exit 12",
    severity: "high",
    location: "Northern Gateway, Exit 12",
    lat: 40.7689,
    lng: -73.9651,
    detectedAt: new Date(Date.now() - 52 * 60000).toISOString(),
    status: "investigating",
    impactRadius: "0.4 km",
    delayEstimate: "+7m",
    description: "Traffic signal malfunction causing manual traffic control at Exit 12. Officers dispatched.",
  },
  {
    id: "INC-8819",
    title: "Vehicle Breakdown: Bridge Span",
    severity: "moderate",
    location: "West End Terminal",
    lat: 40.7489,
    lng: -74.0051,
    detectedAt: new Date(Date.now() - 120 * 60000).toISOString(),
    status: "resolved",
    impactRadius: "0.2 km",
    delayEstimate: "+3m",
    description: "Stalled vehicle on bridge right lane. Recovery unit dispatched and incident cleared.",
  },
  {
    id: "INC-8818",
    title: "Pedestrian Overflow: Central Square",
    severity: "low",
    location: "Central Square Plaza",
    lat: 40.7529,
    lng: -73.9773,
    detectedAt: new Date(Date.now() - 200 * 60000).toISOString(),
    status: "resolved",
    impactRadius: "0.1 km",
    delayEstimate: "+2m",
    description: "Unusual pedestrian density due to public event. Signals adjusted automatically.",
  },
];

export async function GET() {
  // Simulate slight randomization to make it feel live
  const live = incidents.map((i) => ({
    ...i,
    detectedAt: new Date(
      new Date(i.detectedAt).getTime() + Math.floor(Math.random() * 30000)
    ).toISOString(),
  }));
  return NextResponse.json(live);
}
