import { NextResponse } from "next/server";

function generateTrend() {
  const base = [250, 280, 320, 290, 310, 420, 560, 680, 720, 690, 650, 610];
  return base.map((v, i) => ({
    time: `${String(i * 2).padStart(2, "0")}:00`,
    count: v + Math.floor(Math.random() * 40 - 20),
  }));
}

export async function GET() {
  const data = {
    vehicleCount: 137 + Math.floor(Math.random() * 20 - 10),
    avgSpeed: 35 + Math.floor(Math.random() * 6 - 3),
    incidentCount: 4,
    signalEfficiency: 94.2,
    responseTime: 6.8,
    trafficTrend: generateTrend(),
    districtSpeeds: [
      { district: "Central Hub", speed: 34 + Math.floor(Math.random() * 6 - 3) },
      { district: "Northern Gateway", speed: 52 + Math.floor(Math.random() * 6 - 3) },
      { district: "West End Terminal", speed: 28 + Math.floor(Math.random() * 6 - 3) },
      { district: "South Parkway", speed: 48 + Math.floor(Math.random() * 6 - 3) },
    ],
  };
  return NextResponse.json(data);
}
