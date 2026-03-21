"use client";

import { useEffect, useState, useCallback } from "react";
import dynamic from "next/dynamic";
import Link from "next/link";
import type { AnalyticsData } from "@/lib/types";
import type { MapMarker } from "@/components/map/MapboxMap";

const MapboxMap = dynamic(() => import("@/components/map/MapboxMap"), { ssr: false });

const INCIDENT_MARKERS: MapMarker[] = [
  { id: "INC-8821", lat: 40.7589, lng: -73.9851, type: "incident", severity: "critical", label: "INC-8821", popup: "HWY 101 North Congestion — Critical" },
  { id: "INC-8820", lat: 40.7689, lng: -73.9651, type: "incident", severity: "high", label: "INC-8820", popup: "Signal Malfunction Exit 12 — High" },
  { id: "CAM-042", lat: 40.7529, lng: -73.9773, type: "camera", label: "CAM-042", popup: "5th Ave & Broadway — Live" },
  { id: "CAM-018", lat: 40.7440, lng: -74.0021, type: "camera", label: "CAM-018", popup: "West End Terminal — Live" },
];

function MiniChart({ data, color = "#2A6C0D" }: { data: number[]; color?: string }) {
  const max = Math.max(...data);
  const min = Math.min(...data);
  const h = 48;
  const w = 120;
  const points = data.map((v, i) => {
    const x = (i / (data.length - 1)) * w;
    const y = h - ((v - min) / (max - min || 1)) * h;
    return `${x},${y}`;
  });
  const polyline = points.join(" ");
  const area = `${points[0]} ${points.slice(1).join(" ")} ${w},${h} 0,${h}`;
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="w-full h-12" preserveAspectRatio="none">
      <defs>
        <linearGradient id="mini-grad" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.3" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      <polygon points={area} fill="url(#mini-grad)" />
      <polyline points={polyline} fill="none" stroke={color} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export default function DashboardPage() {
  const [analytics, setAnalytics] = useState<AnalyticsData | null>(null);
  const [lastUpdated, setLastUpdated] = useState<string>("");

  const loadAnalytics = useCallback(async () => {
    try {
      const res = await fetch("/api/analytics");
      const data = await res.json();
      setAnalytics(data);
      setLastUpdated(new Date().toLocaleTimeString());
    } catch {
      // keep last data
    }
  }, []);

  useEffect(() => {
    loadAnalytics();
    const iv = setInterval(loadAnalytics, 15000);
    return () => clearInterval(iv);
  }, [loadAnalytics]);

  const speedData = analytics?.trafficTrend.map((t) => t.count * 0.05 + 25) ?? [30, 32, 35, 34, 36, 33, 35, 38, 35, 33, 34, 35];
  const countData = analytics?.trafficTrend.map((t) => t.count) ?? [250, 280, 310, 290, 330, 420, 560, 620, 590, 540, 580, 610];

  return (
    <main className="h-screen flex flex-col overflow-hidden pt-16 bg-surface">
      {/* Top breadcrumb bar */}
      <div className="flex items-center justify-between px-6 py-3 bg-surface-container-lowest border-b border-outline-variant/10 shrink-0">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <span className="material-symbols-outlined text-primary text-lg">location_on</span>
            <div>
              <p className="font-bold text-sm text-on-surface">Central Austin</p>
              <p className="text-[10px] text-primary font-semibold">Online · Update: 00-02</p>
            </div>
          </div>
          <div className="flex gap-1 ml-4">
            <button className="px-4 py-1.5 text-xs font-bold text-white bg-primary rounded-full">Overview</button>
            <Link href="/map"><button className="px-4 py-1.5 text-xs font-medium text-on-surface-variant hover:bg-surface-container-low rounded-full transition-colors">Device Map</button></Link>
            <Link href="/settings"><button className="px-4 py-1.5 text-xs font-medium text-on-surface-variant hover:bg-surface-container-low rounded-full transition-colors">Settings</button></Link>
          </div>
        </div>
        <div className="flex items-center gap-2 text-[10px] text-on-surface-variant">
          <span className="material-symbols-outlined text-sm">sync</span>
          {lastUpdated ? `Updated ${lastUpdated}` : "Loading..."}
        </div>
      </div>

      {/* Location info bar */}
      <div className="flex items-center gap-8 px-6 py-2 bg-surface shrink-0">
        <div className="flex items-center gap-2">
          <span className="text-[10px] font-bold text-on-surface-variant uppercase tracking-wider">Location</span>
          <span className="text-xs font-semibold text-on-surface">East 7th</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[10px] font-bold text-on-surface-variant uppercase tracking-wider">Substation</span>
          <span className="text-xs font-semibold text-on-surface">7th & Comal (Segment ID:7C2)</span>
        </div>
      </div>

      {/* Main content: map left + insights right */}
      <div className="flex-1 flex overflow-hidden">
        {/* LEFT: Live Map */}
        <div className="flex-1 relative min-w-0">
          <MapboxMap
            center={[-97.7431, 30.2672]}
            zoom={13}
            markers={INCIDENT_MARKERS}
            className="w-full h-full"
            style="mapbox://styles/mapbox/light-v11"
          />
          {/* Map search overlay */}
          <div className="absolute top-4 left-4 z-10">
            <div className="bg-white rounded-lg shadow-lg p-1.5 flex items-center gap-2 w-56">
              <span className="material-symbols-outlined text-on-surface-variant text-sm ml-1">search</span>
              <input className="flex-1 text-xs bg-transparent outline-none placeholder:text-on-surface-variant/50" placeholder="Search segments..." />
            </div>
          </div>
          {/* Zoom controls */}
          <div className="absolute bottom-6 right-4 z-10 flex flex-col bg-white rounded-lg shadow-lg overflow-hidden">
            <button className="p-2 hover:bg-surface-container-low transition-colors"><span className="material-symbols-outlined text-sm text-on-surface-variant">add</span></button>
            <div className="h-px bg-outline-variant/20"></div>
            <button className="p-2 hover:bg-surface-container-low transition-colors"><span className="material-symbols-outlined text-sm text-on-surface-variant">remove</span></button>
          </div>
        </div>

        {/* RIGHT: Traffic Insights Panel */}
        <div className="w-[420px] shrink-0 flex flex-col overflow-y-auto bg-surface border-l border-outline-variant/10">
          {/* Header */}
          <div className="flex items-center justify-between px-5 pt-4 pb-2">
            <h2 className="font-bold text-sm text-on-surface">Traffic Insights</h2>
            <div className="flex items-center gap-2">
              <button className="text-[10px] text-on-surface-variant font-medium hover:text-primary transition-colors">Last 3 Hours</button>
              <button className="text-[10px] text-on-surface-variant font-medium hover:text-primary transition-colors">Northbound</button>
              <Link href="/map">
                <button className="px-3 py-1 text-[10px] font-bold text-white bg-primary rounded-full hover:brightness-110 transition-all">View Map</button>
              </Link>
            </div>
          </div>

          {/* KPI Cards Row */}
          <div className="grid grid-cols-2 gap-3 px-4 pb-3">
            {/* Vehicle Count */}
            <div className="bg-surface-container-lowest rounded-xl p-4">
              <div className="flex items-center justify-between mb-1">
                <div className="flex items-center gap-1.5">
                  <span className="material-symbols-outlined text-on-surface-variant text-base">directions_car</span>
                  <span className="text-[10px] font-bold text-on-surface-variant uppercase">Vehicle Count</span>
                </div>
                <span className="material-symbols-outlined text-on-surface-variant/40 text-sm cursor-pointer">settings</span>
              </div>
              <div className="flex items-end gap-2 mt-2">
                <span className="text-3xl font-bold text-on-surface">{analytics?.vehicleCount ?? 137}</span>
                <span className="text-sm font-semibold text-on-surface-variant mb-1">VEH</span>
              </div>
              <div className="mt-2">
                <MiniChart data={countData} color="#2A6C0D" />
              </div>
              <div className="flex justify-between mt-1 text-[9px] font-bold text-on-surface-variant">
                <span>— Average</span>
                <span>— Max</span>
                <span>— Min</span>
              </div>
            </div>

            {/* Speed */}
            <div className="bg-surface-container-lowest rounded-xl p-4">
              <div className="flex items-center justify-between mb-1">
                <div className="flex items-center gap-1.5">
                  <span className="material-symbols-outlined text-on-surface-variant text-base">speed</span>
                  <span className="text-[10px] font-bold text-on-surface-variant uppercase">Speed</span>
                </div>
                <span className="material-symbols-outlined text-on-surface-variant/40 text-sm cursor-pointer">settings</span>
              </div>
              <div className="flex items-end gap-2 mt-2">
                <span className="text-3xl font-bold text-on-surface">{analytics?.avgSpeed ?? 35}</span>
                <span className="text-sm font-semibold text-on-surface-variant mb-1">MPH</span>
              </div>
              <div className="mt-2">
                <MiniChart data={speedData} color="#EAB308" />
              </div>
              <div className="flex justify-between mt-1 text-[9px] font-bold text-on-surface-variant">
                <span>— Average</span>
                <span>— Normal</span>
                <span>— Min</span>
              </div>
            </div>
          </div>

          {/* Events + CTECC Row */}
          <div className="grid grid-cols-2 gap-3 px-4 pb-3">
            {/* Events */}
            <div className="bg-surface-container-lowest rounded-xl p-4">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-1.5">
                  <span className="material-symbols-outlined text-on-surface-variant text-base">warning</span>
                  <span className="text-[10px] font-bold text-on-surface-variant uppercase">Events</span>
                </div>
                <div className="flex gap-1">
                  <span className="w-2 h-2 rounded-full bg-error"></span>
                  <span className="w-2 h-2 rounded-full bg-primary"></span>
                  <span className="w-2 h-2 rounded-full bg-outline-variant"></span>
                </div>
              </div>
              <p className="text-[9px] text-on-surface-variant mb-2">Last update: 00:02 · Event ID: TC-21</p>
              <div className="space-y-1.5">
                <div className="flex items-center gap-1.5">
                  <span className="material-symbols-outlined text-error text-sm" style={{ fontVariationSettings: "'FILL' 1" }}>warning</span>
                  <span className="text-[10px] text-on-surface">Accident Occurred: Yes</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="material-symbols-outlined text-primary text-sm">cloud</span>
                  <span className="text-[10px] text-on-surface">Weather Condition: Rain</span>
                </div>
              </div>
              <div className="mt-2 flex gap-1">
                {[...Array(5)].map((_, i) => (
                  <div key={i} className={`h-1.5 flex-1 rounded-full ${i < 3 ? "bg-error" : "bg-surface-container-high"}`}></div>
                ))}
              </div>
            </div>

            {/* CTECC */}
            <div className="bg-surface-container-lowest rounded-xl p-4">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-1.5">
                  <span className="material-symbols-outlined text-on-surface-variant text-base">corporate_fare</span>
                  <span className="text-[10px] font-bold text-on-surface-variant uppercase">CTECC</span>
                </div>
              </div>
              <p className="text-[9px] text-on-surface-variant mb-2">Last update: 00:02 · Event ID: TC-21</p>
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] text-on-surface">Medical Department</span>
                  <span className="px-2 py-0.5 bg-surface-container-high text-on-surface-variant text-[9px] font-bold rounded">In Progress</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-[10px] text-on-surface">Police Department</span>
                  <span className="px-2 py-0.5 bg-primary text-white text-[9px] font-bold rounded">Dispatched</span>
                </div>
              </div>
            </div>
          </div>

          {/* Live Video Feed */}
          <div className="px-4 pb-3">
            <div className="bg-surface-container-lowest rounded-xl overflow-hidden">
              <div className="relative h-36 bg-slate-900">
                <img
                  src="https://lh3.googleusercontent.com/aida-public/AB6AXuDbuoLeNYnnqiAmzOxu8enM5UXNHhQe4EWbzM5FPoQ4jc3MpxRMdTLxoy4HUohnCwqtmoTM3UuFnHIjQZ1pgYkic9IHboqicYJcDD7wTmPhgRq5eP1f4ZPTPSAuinfDeIv1JFAs2WYCrsdCmbkipgUcLO7EJ7tTRUjErLW9aZYWr8GQEIMOBFVJ5sDKAwrz-EghzFxdF7wICxIgW0tXS5RG7emhROOwvJJX5qFCEdBcRKg9k8aOB6scC49Vq0fVovBTaxqnxqCW_1nh"
                  alt="Live feed"
                  className="w-full h-full object-cover opacity-90"
                />
                <div className="absolute top-2 left-2 flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse"></span>
                  <span className="text-[9px] font-bold text-white uppercase">LIVE · CAM-R42 · East 7th Ave</span>
                </div>
                <div className="absolute bottom-2 left-2">
                  <span className="text-[9px] font-bold text-white/70">TIMESTAMP: 2024-05-20 22:14:08</span>
                </div>
              </div>
              <div className="p-3">
                <p className="text-[10px] font-bold text-on-surface-variant uppercase">Live Video Feed</p>
              </div>
            </div>
          </div>

          {/* AI Copilot */}
          <AICopilot />
        </div>
      </div>
    </main>
  );
}

function AICopilot() {
  const [messages, setMessages] = useState<{ role: "user" | "assistant"; content: string }[]>([
    { role: "assistant", content: "I recommend re-timing the signals at 7th and Comal. A 'Smart Diversion' on Line 7 is also available." },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);

  const send = async () => {
    if (!input.trim() || loading) return;
    const userMsg = input.trim();
    setInput("");
    setMessages((p) => [...p, { role: "user", content: userMsg }]);
    setLoading(true);

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ messages: [...messages, { role: "user", content: userMsg }] }),
      });

      const reader = res.body?.getReader();
      const decoder = new TextDecoder();
      let assistantMsg = "";
      setMessages((p) => [...p, { role: "assistant", content: "" }]);

      if (reader) {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          const chunk = decoder.decode(value);
          const lines = chunk.split("\n").filter((l) => l.startsWith("data: "));
          for (const line of lines) {
            const data = line.slice(6);
            if (data === "[DONE]") continue;
            try {
              const parsed = JSON.parse(data);
              const delta = parsed.choices?.[0]?.delta?.content || "";
              assistantMsg += delta;
              setMessages((p) => {
                const updated = [...p];
                updated[updated.length - 1] = { role: "assistant", content: assistantMsg };
                return updated;
              });
            } catch {
              // skip malformed
            }
          }
        }
      }
    } catch {
      setMessages((p) => [...p, { role: "assistant", content: "Connection error. Please try again." }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="px-4 pb-4 flex-1 flex flex-col">
      <div className="bg-surface-container-lowest rounded-xl flex flex-col flex-1">
        <div className="flex items-center gap-2 px-4 pt-4 pb-2">
          <div className="w-6 h-6 rounded bg-secondary-container flex items-center justify-center">
            <span className="material-symbols-outlined text-[14px] text-primary" style={{ fontVariationSettings: "'FILL' 1" }}>smart_toy</span>
          </div>
          <span className="text-xs font-bold text-on-surface">AI Copilot</span>
        </div>
        <div className="px-4 pb-2 space-y-2 max-h-36 overflow-y-auto">
          {messages.map((m, i) => (
            <div key={i} className={`text-xs rounded-lg px-3 py-2 ${m.role === "user" ? "bg-primary-container/20 text-on-surface ml-4" : "bg-surface text-on-surface-variant"}`}>
              {m.content || <span className="animate-pulse">▍</span>}
            </div>
          ))}
        </div>
        <div className="px-3 pb-3 mt-auto">
          <div className="flex items-center gap-2 bg-surface rounded-lg border border-outline-variant/20 px-3 py-2">
            <input
              className="flex-1 text-xs bg-transparent outline-none placeholder:text-on-surface-variant/50"
              placeholder="Ask Copilot: Suggest diversion routes, optimize signals..."
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && send()}
            />
            <button onClick={send} disabled={loading} className="p-1 text-primary hover:bg-primary/10 rounded transition-colors">
              <span className="material-symbols-outlined text-sm" style={{ fontVariationSettings: "'FILL' 1" }}>send</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
