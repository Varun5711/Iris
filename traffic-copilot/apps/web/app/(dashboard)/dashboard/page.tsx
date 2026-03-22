"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import dynamic from "next/dynamic";
import Link from "next/link";
import { useSettings } from "@/ui_lib/settings-context";
import type { MapMarker, MapboxHandle } from "@/components/map/MapboxMap";

const MapboxMap = dynamic(() => import("@/components/map/MapboxMap"), { ssr: false });
const MAPBOX_TOKEN = process.env.NEXT_PUBLIC_MAPBOX_TOKEN ?? "";

interface SensorMetrics {
  occupancy_pct: number;
  free_flow_speed: number;
  current_speed: number;
  volume_per_hour: number;
  headway_seconds: number;
  lane_utilization: number;
}

interface AnalyticsData {
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
  sensorMetrics: SensorMetrics;
}

function MiniChart({ data, color = "#2A6C0D" }: { data: number[]; color?: string }) {
  const max = Math.max(...data, 1);
  const min = Math.min(...data);
  const h = 48; const w = 120;
  const pts = data.map((v, i) => {
    const x = (i / (data.length - 1)) * w;
    const y = h - ((v - min) / (max - min || 1)) * h;
    return `${x},${y}`;
  });
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="w-full h-12" preserveAspectRatio="none">
      <defs>
        <linearGradient id={`mg-${color.replace("#","")}`} x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.3" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      <polygon points={`${pts[0]} ${pts.slice(1).join(" ")} ${w},${h} 0,${h}`} fill={`url(#mg-${color.replace("#","")})`} />
      <polyline points={pts.join(" ")} fill="none" stroke={color} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

// Ahmedabad camera anchor points
const CAMERA_MARKERS: MapMarker[] = [
  { id: "CAM-AMD-01", lat: 23.0269, lng: 72.5855, type: "camera", label: "CAM-CG-01", popup: "CG Road / Swastik" },
  { id: "CAM-AMD-02", lat: 23.0395, lng: 72.5039, type: "camera", label: "CAM-SGH-01", popup: "SG Highway" },
];

export default function DashboardPage() {
  const { settings } = useSettings();
  const mapRef = useRef<MapboxHandle | null>(null);
  const [analytics, setAnalytics] = useState<AnalyticsData | null>(null);
  const [lastUpdated, setLastUpdated] = useState("");
  const [searchValue, setSearchValue] = useState("");
  const [searchResults, setSearchResults] = useState<{ place_name: string; center: [number, number] }[]>([]);
  const [searchOpen, setSearchOpen] = useState(false);
  const [activeIncidentId, setActiveIncidentId] = useState<string | null>(null);
  const [incidentMarkers, setIncidentMarkers] = useState<MapMarker[]>([]);

  const load = useCallback(async () => {
    try {
      const res = await fetch("/api/analytics");
      setAnalytics(await res.json());
      setLastUpdated(new Date().toLocaleTimeString());
    } catch {}
  }, []);

  // Fetch incidents — set copilot context + build dynamic map markers
  useEffect(() => {
    fetch("/api/incidents").then(r => r.json()).then((incidents: { id: string; lat?: number; lng?: number; severity?: string; title?: string; description?: string }[]) => {
      if (incidents?.[0]?.id) setActiveIncidentId(incidents[0].id);
      const markers: MapMarker[] = incidents.slice(0, 10).map(inc => ({
        id: inc.id,
        lat: inc.lat ?? 23.0269,
        lng: inc.lng ?? 72.5855,
        type: "incident" as const,
        severity: (inc.severity === "medium" ? "moderate" : inc.severity) as "critical" | "high" | "moderate" | "low" | undefined,
        label: inc.id.slice(0, 8),
        popup: inc.title ?? inc.description ?? "Incident",
      }));
      setIncidentMarkers(markers);
    }).catch(() => {});
  }, []);

  const handleSearch = async (q: string) => {
    setSearchValue(q);
    if (q.length < 3) { setSearchResults([]); setSearchOpen(false); return; }
    try {
      const res = await fetch(`https://api.mapbox.com/geocoding/v5/mapbox.places/${encodeURIComponent(q)}.json?access_token=${MAPBOX_TOKEN}&limit=4`);
      const data = await res.json();
      const results = (data.features ?? []).map((f: Record<string, unknown>) => ({ place_name: f.place_name as string, center: f.center as [number, number] }));
      setSearchResults(results);
      setSearchOpen(results.length > 0);
    } catch {}
  };

  useEffect(() => {
    load();
    const iv = setInterval(load, 15000);
    return () => clearInterval(iv);
  }, [load]);

  const countData = analytics?.trafficTrend.map((t) => t.count) ?? [250, 280, 310, 290, 330, 420, 560, 620, 590, 540, 580, 610];
  const speedData = analytics?.trafficTrend.map((t) => (t.count * 0.05 + 20)) ?? [30, 32, 35, 34, 36, 33, 35, 38, 35, 33, 34, 35];
  const densityData = analytics?.trafficTrend.map((t) => Math.min(100, t.count / 7)) ?? [];

  // Combine dynamic incident markers + static camera anchors, filter by settings
  const markers: MapMarker[] = [
    ...(settings.mapLayers.incidents ? incidentMarkers : []),
    ...(settings.dataSources.cctv || settings.dataSources.trafficCamera ? CAMERA_MARKERS : []),
  ];

  return (
    <main className="h-screen flex flex-col overflow-hidden pt-16 bg-surface">
      {/* Breadcrumb bar */}
      <div className="flex items-center justify-between px-6 py-3 bg-white border-b border-outline-variant/10 shrink-0">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <span className="material-symbols-outlined text-primary text-lg">location_on</span>
            <div>
              <p className="font-bold text-sm text-on-surface">Ahmedabad Command</p>
              <p className={`text-[10px] font-semibold ${analytics?.backendOnline ? "text-primary" : "text-on-surface-variant"}`}>
                {analytics?.backendOnline ? "● Backend Live" : "○ Simulation Mode"} · {lastUpdated || "Loading..."}
              </p>
            </div>
          </div>
          <div className="flex gap-1 ml-4">
            <button className="px-4 py-1.5 text-xs font-bold text-white bg-primary rounded-full">Overview</button>
            <Link href="/map"><button className="px-4 py-1.5 text-xs font-medium text-on-surface-variant hover:bg-surface-container-low rounded-full transition-colors">Live Map</button></Link>
            <Link href="/settings"><button className="px-4 py-1.5 text-xs font-medium text-on-surface-variant hover:bg-surface-container-low rounded-full transition-colors">Settings</button></Link>
          </div>
        </div>
        <button onClick={load} className="flex items-center gap-1 text-[10px] text-on-surface-variant hover:text-primary transition-colors">
          <span className="material-symbols-outlined text-sm">sync</span> Refresh
        </button>
      </div>

      {/* Location bar */}
      <div className="flex items-center gap-8 px-6 py-2 bg-surface border-b border-outline-variant/5 shrink-0 text-xs">
        <div className="flex items-center gap-2">
          <span className="font-bold text-on-surface-variant uppercase text-[10px]">Location</span>
          <span className="font-semibold text-on-surface">CG Road / Swastik</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="font-bold text-on-surface-variant uppercase text-[10px]">Substation</span>
          <span className="font-semibold text-on-surface">Segment ID: 7C2</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="font-bold text-on-surface-variant uppercase text-[10px]">OSM Graph</span>
          <span className="font-semibold text-on-surface">Ahmedabad, India</span>
        </div>
      </div>

      <div className="flex-1 flex overflow-hidden">
        {/* LEFT: Live Map */}
        <div className="flex-1 relative min-w-0">
          <MapboxMap
            ref={mapRef}
            center={[72.5855, 23.0269]}
            zoom={13}
            styleUrl="mapbox://styles/mapbox/light-v11"
            markers={markers}
            className="w-full h-full"
            onMapReady={(h) => { mapRef.current = h; }}
          />
          {/* Functional Search Bar */}
          <div className="absolute top-4 left-4 z-10 w-60">
            <div className="relative">
              <div className="bg-white rounded-lg shadow-lg p-1.5 flex items-center gap-2">
                <span className="material-symbols-outlined text-on-surface-variant text-sm ml-1">search</span>
                <input
                  className="flex-1 bg-transparent border-none text-xs outline-none text-on-surface placeholder:text-on-surface-variant/50 py-1"
                  placeholder="Search segments..."
                  value={searchValue}
                  onChange={(e) => handleSearch(e.target.value)}
                  onFocus={() => searchResults.length > 0 && setSearchOpen(true)}
                />
                {searchValue && (
                  <button onClick={() => { setSearchValue(""); setSearchResults([]); setSearchOpen(false); }} className="text-on-surface-variant">
                    <span className="material-symbols-outlined text-sm">close</span>
                  </button>
                )}
              </div>
              {searchOpen && searchResults.length > 0 && (
                <div className="absolute top-full left-0 right-0 mt-1 bg-white rounded-lg shadow-xl overflow-hidden z-20">
                  {searchResults.map((r, i) => (
                    <button key={i} onClick={() => { mapRef.current?.flyTo(r.center, 15); setSearchValue(r.place_name); setSearchOpen(false); }}
                      className="w-full text-left px-3 py-2 hover:bg-surface-container-low transition-colors flex items-center gap-2 border-b border-outline-variant/10 last:border-0">
                      <span className="material-symbols-outlined text-primary text-sm">location_on</span>
                      <span className="text-xs text-on-surface leading-tight truncate">{r.place_name}</span>
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
          {/* Zoom Controls */}
          <div className="absolute top-4 right-4 z-10 flex flex-col bg-white rounded-lg shadow-lg">
            <button onClick={() => mapRef.current?.zoomIn()} className="p-2 hover:bg-surface-container-low rounded-t-lg transition-colors text-on-surface-variant">
              <span className="material-symbols-outlined text-sm">add</span>
            </button>
            <div className="w-6 h-px bg-outline-variant/20 mx-auto"></div>
            <button onClick={() => mapRef.current?.zoomOut()} className="p-2 hover:bg-surface-container-low rounded-b-lg transition-colors text-on-surface-variant">
              <span className="material-symbols-outlined text-sm">remove</span>
            </button>
          </div>
        </div>

        {/* RIGHT: Traffic Insights Panel */}
        <div className="w-[440px] shrink-0 flex flex-col overflow-y-auto bg-surface border-l border-outline-variant/10">
          {/* Panel Header */}
          <div className="flex items-center justify-between px-5 pt-4 pb-2 shrink-0">
            <h2 className="font-bold text-sm text-on-surface">Traffic Insights</h2>
            <div className="flex items-center gap-2">
              <span className="text-[10px] text-on-surface-variant">Last 3 Hours</span>
              <span className="text-[10px] text-on-surface-variant">Northbound</span>
              <Link href="/map">
                <button className="px-3 py-1 text-[10px] font-bold text-white bg-primary rounded-full hover:brightness-110">View Map</button>
              </Link>
            </div>
          </div>

          {/* Primary KPIs */}
          <div className="grid grid-cols-2 gap-3 px-4 pb-3">
            <div className="bg-surface-container-lowest rounded-xl p-4">
              <div className="flex items-center justify-between mb-1">
                <span className="text-[10px] font-bold text-on-surface-variant uppercase flex items-center gap-1">
                  <span className="material-symbols-outlined text-sm">directions_car</span> Vehicle Count
                </span>
              </div>
              <div className="flex items-end gap-1 mt-1">
                <span className="text-3xl font-bold text-on-surface">{analytics?.vehicleCount ?? 137}</span>
                <span className="text-xs font-semibold text-on-surface-variant mb-1">VEH</span>
              </div>
              <MiniChart data={countData} color="#2A6C0D" />
              <div className="flex justify-between mt-1 text-[9px] font-bold text-on-surface-variant">
                <span>AVG</span><span>MAX</span><span>MIN</span>
              </div>
            </div>

            <div className="bg-surface-container-lowest rounded-xl p-4">
              <div className="flex items-center justify-between mb-1">
                <span className="text-[10px] font-bold text-on-surface-variant uppercase flex items-center gap-1">
                  <span className="material-symbols-outlined text-sm">speed</span> Avg Speed
                </span>
              </div>
              <div className="flex items-end gap-1 mt-1">
                <span className="text-3xl font-bold text-on-surface">{analytics?.avgSpeed ?? 35}</span>
                <span className="text-xs font-semibold text-on-surface-variant mb-1">KM/H</span>
              </div>
              <MiniChart data={speedData} color="#EAB308" />
              <div className="flex justify-between mt-1 text-[9px] font-bold text-on-surface-variant">
                <span>AVG</span><span>NORM</span><span>MIN</span>
              </div>
            </div>
          </div>

          {/* Extended sensor metrics */}
          <div className="grid grid-cols-2 gap-3 px-4 pb-3">
            <div className="bg-surface-container-lowest rounded-xl p-4">
              <span className="text-[10px] font-bold text-on-surface-variant uppercase">Traffic Density</span>
              <div className="flex items-end gap-1 mt-1">
                <span className="text-2xl font-bold text-on-surface">{analytics?.trafficDensity ?? analytics?.avgCongestion ?? 52}</span>
                <span className="text-xs text-on-surface-variant mb-0.5">%</span>
              </div>
              <div className="mt-2 h-1.5 w-full bg-surface-container rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all ${(analytics?.trafficDensity ?? 52) > 70 ? "bg-error" : "bg-primary"}`}
                  style={{ width: `${analytics?.trafficDensity ?? 52}%` }}
                ></div>
              </div>
              {densityData.length > 0 && <MiniChart data={densityData} color={analytics && analytics.trafficDensity > 70 ? "#BA1A1A" : "#2A6C0D"} />}
            </div>

            <div className="bg-surface-container-lowest rounded-xl p-4">
              <span className="text-[10px] font-bold text-on-surface-variant uppercase">Lane Utilization</span>
              <div className="flex items-end gap-1 mt-1">
                <span className="text-2xl font-bold text-on-surface">{analytics?.sensorMetrics?.lane_utilization ?? 63}</span>
                <span className="text-xs text-on-surface-variant mb-0.5">%</span>
              </div>
              <div className="mt-2 space-y-1">
                {[...Array(3)].map((_, i) => (
                  <div key={i} className="h-1.5 w-full bg-surface-container rounded-full overflow-hidden">
                    <div className="h-full bg-primary rounded-full" style={{ width: `${Math.min(100, (analytics?.sensorMetrics?.lane_utilization ?? 63) * (1 - i * 0.15))}%` }}></div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Events + CTECC */}
          <div className="grid grid-cols-2 gap-3 px-4 pb-3">
            <div className="bg-surface-container-lowest rounded-xl p-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-[10px] font-bold text-on-surface-variant uppercase flex items-center gap-1">
                  <span className="material-symbols-outlined text-sm">warning</span> Events
                </span>
                <div className="flex gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-error"></span>
                  <span className="w-1.5 h-1.5 rounded-full bg-primary"></span>
                  <span className="w-1.5 h-1.5 rounded-full bg-outline-variant"></span>
                </div>
              </div>
              <p className="text-[9px] text-on-surface-variant mb-2">Active incidents: {analytics?.incidentCount ?? 4}</p>
              <div className="space-y-1.5">
                <div className="flex items-center gap-1.5">
                  <span className="material-symbols-outlined text-error text-sm" style={{ fontVariationSettings: "'FILL' 1" }}>warning</span>
                  <span className="text-[10px] text-on-surface">Accidents: {analytics?.criticalSegments ?? 2}</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="material-symbols-outlined text-primary text-sm">cloud</span>
                  <span className="text-[10px] text-on-surface">Avg Delay: {analytics?.avgDelay ? `${Math.round(analytics.avgDelay / 60)}m` : "18m"}</span>
                </div>
              </div>
              <div className="mt-2 flex gap-1">
                {[...Array(5)].map((_, i) => (
                  <div key={i} className={`h-1.5 flex-1 rounded-full ${i < Math.ceil((analytics?.criticalSegments ?? 2) / 2) ? "bg-error" : "bg-surface-container-high"}`}></div>
                ))}
              </div>
            </div>

            <div className="bg-surface-container-lowest rounded-xl p-4">
              <div className="mb-2">
                <span className="text-[10px] font-bold text-on-surface-variant uppercase flex items-center gap-1">
                  <span className="material-symbols-outlined text-sm">corporate_fare</span> CTECC
                </span>
              </div>
              <p className="text-[9px] text-on-surface-variant mb-2">Active dispatch</p>
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] text-on-surface">Medical Dept.</span>
                  <span className="px-2 py-0.5 bg-surface-container-high text-on-surface-variant text-[9px] font-bold rounded">In Progress</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-[10px] text-on-surface">Police Dept.</span>
                  <span className="px-2 py-0.5 bg-primary text-white text-[9px] font-bold rounded">Dispatched</span>
                </div>
              </div>
            </div>
          </div>

          {/* Sensor metrics detail */}
          {analytics?.sensorMetrics && (
            <div className="px-4 pb-3">
              <div className="bg-surface-container-lowest rounded-xl p-4">
                <p className="text-[10px] font-bold text-on-surface-variant uppercase mb-3">Sensor Telemetry</p>
                <div className="grid grid-cols-3 gap-2">
                  {[
                    { label: "Occupancy", value: `${analytics.sensorMetrics.occupancy_pct | 0}%` },
                    { label: "Vol/hr", value: `${(analytics.sensorMetrics.volume_per_hour / 1000).toFixed(1)}k` },
                    { label: "Headway", value: `${analytics.sensorMetrics.headway_seconds}s` },
                  ].map(({ label, value }) => (
                    <div key={label} className="bg-surface rounded-lg p-2 text-center">
                      <p className="text-[9px] font-bold text-on-surface-variant uppercase">{label}</p>
                      <p className="text-sm font-bold text-on-surface">{value}</p>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Live Video Feed */}
          <div className="px-4 pb-3">
            <div className="bg-surface-container-lowest rounded-xl overflow-hidden">
              <div className="relative h-32 bg-slate-900">
                <img src="https://images.unsplash.com/photo-1477959858617-67f85cf4f1df?w=600&q=80" alt="feed" className="w-full h-full object-cover opacity-90" />
                <div className="absolute top-2 left-2 flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse"></span>
                  <span className="text-[9px] font-bold text-white uppercase">LIVE · CAM-042 · CG Road</span>
                </div>
              </div>
              <div className="px-3 py-2"><p className="text-[10px] font-bold text-on-surface-variant uppercase">Live Video Feed</p></div>
            </div>
          </div>

          {/* AI Copilot */}
          <AICopilot incidentId={activeIncidentId} />
        </div>
      </div>
    </main>
  );
}

function AICopilot({ incidentId }: { incidentId: string | null }) {
  const [messages, setMessages] = useState<{ role: "user" | "assistant"; content: string }[]>([
    { role: "assistant", content: "IRIS AI ready. Ask about signal timing, diversion routes, or incident status." },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);

  const send = async () => {
    if (!input.trim() || loading) return;
    const q = input.trim();
    setInput("");
    setMessages((p) => [...p, { role: "user" as const, content: q }]);
    setLoading(true);
    try {
      // Use backend /chat/ directly if incident ID available (returns conversational_answer)
      const BACKEND = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";
      if (incidentId) {
        try {
          const backendRes = await fetch(`${BACKEND}/chat/`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ incident_id: incidentId, question: q, officer_id: "officer-web" }),
            signal: AbortSignal.timeout(15000),
          });
          if (backendRes.ok) {
            const rec = await backendRes.json();
            const answer = rec.copilot_response?.conversational_answer ?? rec.expected_impact ?? rec.action ?? "Processed.";
            if (rec.copilot_response?.blocked_reason === "llm_unavailable") {
              setMessages((p) => [...p, { role: "assistant", content: "AI engine rate-limited. Retrying via fallback..." }]);
            } else {
              setMessages((p) => [...p, { role: "assistant", content: answer }]);
              setLoading(false);
              return;
            }
          }
        } catch { /* fall through to Groq fallback */ }
      }

      // Groq fallback via /api/chat SSE stream
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ messages: [...messages, { role: "user", content: q }] }),
      });
      const ct = res.headers.get("content-type") ?? "";
      if (ct.includes("application/json")) {
        const d = await res.json();
        setMessages((p) => [...p, { role: "assistant" as const, content: d.answer ?? "Processed." }]);
      } else {
        const reader = res.body?.getReader();
        const decoder = new TextDecoder();
        let full = "";
        setMessages((p) => [...p, { role: "assistant" as const, content: "" }]);
        if (reader) {
          while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            const lines = decoder.decode(value).split("\n").filter((l) => l.startsWith("data: "));
            for (const line of lines) {
              const data = line.slice(6);
              if (data === "[DONE]") continue;
              try {
                full += JSON.parse(data).choices?.[0]?.delta?.content ?? "";
                setMessages((p) => { const u = [...p]; u[u.length - 1] = { role: "assistant", content: full }; return u; });
              } catch {}
            }
          }
        }
      }
    } catch {
      setMessages((p) => [...p, { role: "assistant" as const, content: "Error. Please try again." }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="px-4 pb-4 flex-1 flex flex-col min-h-0">
      <div className="bg-surface-container-lowest rounded-xl flex flex-col">
        <div className="flex items-center gap-2 px-4 pt-3 pb-2">
          <div className="w-5 h-5 rounded bg-secondary-container flex items-center justify-center">
            <span className="material-symbols-outlined text-[12px] text-primary" style={{ fontVariationSettings: "'FILL' 1" }}>smart_toy</span>
          </div>
          <span className="text-xs font-bold text-on-surface">AI Copilot</span>
          {loading && <span className="ml-auto w-2 h-2 rounded-full bg-primary animate-pulse"></span>}
        </div>
        <div className="px-4 pb-2 space-y-1.5 max-h-28 overflow-y-auto">
          {messages.map((m, i) => (
            <div key={i} className={`text-xs rounded-lg px-2 py-1.5 ${m.role === "user" ? "bg-primary/10 text-on-surface ml-6" : "bg-surface text-on-surface-variant"}`}>
              {m.content || <span className="animate-pulse">▍</span>}
            </div>
          ))}
        </div>
        <div className="px-3 pb-3">
          <div className="flex items-center gap-2 bg-surface rounded-lg border border-outline-variant/20 px-3 py-2">
            <input className="flex-1 text-xs bg-transparent outline-none placeholder:text-on-surface-variant/50" placeholder="Ask Copilot..." value={input} onChange={(e) => setInput(e.target.value)} onKeyDown={(e) => e.key === "Enter" && send()} />
            <button onClick={send} disabled={loading} className="text-primary hover:bg-primary/10 p-0.5 rounded transition-colors disabled:opacity-50">
              <span className="material-symbols-outlined text-sm" style={{ fontVariationSettings: "'FILL' 1" }}>send</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
