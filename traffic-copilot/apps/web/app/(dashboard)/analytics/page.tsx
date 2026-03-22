"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import type { AnalyticsData } from "@/ui_lib/types";

export default function AnalyticsPage() {
  const router = useRouter();
  const [data, setData] = useState<AnalyticsData | null>(null);
  const [timeRange, setTimeRange] = useState("Last 24 Hours");
  const [lastUpdated, setLastUpdated] = useState("");

  const load = useCallback(async () => {
    try {
      const res = await fetch("/api/analytics");
      const d = await res.json();
      setData(d);
      setLastUpdated(new Date().toLocaleTimeString());
    } catch {}
  }, []);

  useEffect(() => {
    load();
    const iv = setInterval(load, 20000);
    return () => clearInterval(iv);
  }, [load]);

  const trend = data?.trafficTrend ?? [];
  const maxCount = Math.max(...trend.map((t) => t.count), 1);

  const buildPath = (filled: boolean) => {
    if (!trend.length) return "";
    const w = 800;
    const h = 250;
    const pts = trend.map((t, i) => {
      const x = (i / (trend.length - 1)) * w;
      const y = h - (t.count / maxCount) * h * 0.9;
      return `${x},${y}`;
    });
    if (filled) {
      return `M${pts[0]} ${pts.slice(1).map((p) => `L${p}`).join(" ")} L${w},${h} L0,${h} Z`;
    }
    return `M${pts[0]} ${pts.slice(1).map((p) => `L${p}`).join(" ")}`;
  };

  const maxSpeed = Math.max(...(data?.districtSpeeds.map((d) => d.speed) ?? [60]));

  return (
    <main className="min-h-screen bg-surface p-8 pt-24">
      <div className="flex items-end justify-between mb-8">
        <div>
          <h3 className="text-3xl font-extrabold text-on-surface tracking-tight mb-1">District Analytics</h3>
          <p className="text-on-surface-variant text-sm font-medium">
            System-wide performance · Last updated: {lastUpdated || "Loading..."}
          </p>
        </div>
        <div className="flex gap-3">
          <button onClick={() => load()} className="px-5 py-2 text-sm font-semibold text-primary hover:bg-primary/5 rounded-full transition-all flex items-center gap-2">
            <span className="material-symbols-outlined text-base">refresh</span> Refresh
          </button>
          <button className="px-6 py-2 text-sm font-semibold text-white signature-gradient rounded-full shadow-md hover:brightness-110 active:scale-95 transition-all">
            Export Report
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        <div className="bg-surface-container-lowest p-6 rounded-xl shadow-sm">
          <div className="flex justify-between items-start mb-4">
            <span className="p-2 bg-primary-container/20 text-primary rounded-lg material-symbols-outlined">emergency</span>
            <span className="text-xs font-bold text-primary flex items-center gap-1">
              <span className="material-symbols-outlined text-sm">trending_down</span> 12%
            </span>
          </div>
          <p className="text-xs font-bold text-on-surface-variant uppercase tracking-wider">Total Incidents (Week)</p>
          <h4 className="text-3xl font-bold text-on-surface">{data?.incidentCount ?? 4}</h4>
          <div className="mt-4 h-1 w-full bg-surface-container rounded-full overflow-hidden">
            <div className="h-full bg-primary rounded-full w-[65%]"></div>
          </div>
        </div>

        <div className="bg-surface-container-lowest p-6 rounded-xl shadow-sm">
          <div className="flex justify-between items-start mb-4">
            <span className="p-2 bg-secondary-container text-on-secondary-container rounded-lg material-symbols-outlined">timer</span>
            <span className="text-xs font-bold text-primary flex items-center gap-1">
              <span className="material-symbols-outlined text-sm">arrow_downward</span> 2.4m
            </span>
          </div>
          <p className="text-xs font-bold text-on-surface-variant uppercase tracking-wider">Avg Response Time</p>
          <h4 className="text-3xl font-bold text-on-surface">{data?.responseTime ?? 6.8} <span className="text-sm font-medium opacity-50">min</span></h4>
          <div className="mt-4 flex gap-1 h-1">
            {[...Array(5)].map((_, i) => (
              <div key={i} className={`flex-1 rounded-full ${i < 3 ? "bg-primary" : "bg-surface-container"}`}></div>
            ))}
          </div>
        </div>

        <div className="bg-surface-container-lowest p-6 rounded-xl shadow-sm">
          <div className="flex justify-between items-start mb-4">
            <span className="p-2 bg-tertiary-container/20 text-tertiary rounded-lg material-symbols-outlined">traffic</span>
            <span className="text-xs font-bold text-on-surface-variant flex items-center gap-1">
              <span className="material-symbols-outlined text-sm">remove</span> Stable
            </span>
          </div>
          <p className="text-xs font-bold text-on-surface-variant uppercase tracking-wider">Signal Efficiency</p>
          <h4 className="text-3xl font-bold text-on-surface">{data?.signalEfficiency ?? 94.2}%</h4>
          <div className="mt-4 h-1 w-full bg-surface-container rounded-full overflow-hidden">
            <div className="h-full bg-tertiary rounded-full" style={{ width: `${data?.signalEfficiency ?? 94}%` }}></div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Traffic Trends Chart */}
        <div className="lg:col-span-2 bg-surface-container-lowest rounded-xl shadow-sm p-6">
          <div className="flex justify-between items-center mb-8">
            <div>
              <h5 className="font-bold text-on-surface">Traffic Trends</h5>
              <p className="text-xs text-on-surface-variant">Vehicle counts — live data</p>
            </div>
            <select
              className="bg-surface border-0 text-xs font-bold rounded-full px-4 py-2 ring-1 ring-outline-variant/10 focus:outline-none"
              value={timeRange}
              onChange={(e) => setTimeRange(e.target.value)}
            >
              <option>Last 24 Hours</option>
              <option>Last 7 Days</option>
            </select>
          </div>
          <div className="relative h-64 w-full">
            {trend.length > 0 ? (
              <svg className="w-full h-full overflow-visible" preserveAspectRatio="none" viewBox="0 0 800 250">
                <defs>
                  <linearGradient id="chartGradient2" x1="0" x2="0" y1="0" y2="1">
                    <stop offset="0%" stopColor="#2a6c0d" stopOpacity="0.15" />
                    <stop offset="100%" stopColor="#2a6c0d" stopOpacity="0" />
                  </linearGradient>
                </defs>
                <path d={buildPath(true)} fill="url(#chartGradient2)" />
                <path d={buildPath(false)} fill="none" stroke="#2a6c0d" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            ) : (
              <div className="w-full h-full bg-surface-container rounded-lg animate-pulse"></div>
            )}
          </div>
          <div className="flex justify-between mt-4 text-[10px] font-bold text-on-surface-variant tracking-wider uppercase">
            {trend.filter((_, i) => i % Math.floor(trend.length / 4 || 1) === 0).map((t) => (
              <span key={t.time}>{t.time}</span>
            ))}
          </div>
        </div>

        {/* Speed by District */}
        <div className="bg-surface-container-lowest rounded-xl shadow-sm p-6">
          <h5 className="font-bold text-on-surface mb-1">Avg Speed by District</h5>
          <p className="text-xs text-on-surface-variant mb-6">Kilometers per hour (km/h)</p>
          <div className="space-y-6">
            {(data?.districtSpeeds ?? [
              { district: "CG Road", speed: 34 },
              { district: "SG Highway", speed: 52 },
              { district: "Ashram Road", speed: 28 },
              { district: "SP Ring Road", speed: 48 },
            ]).map(({ district, speed }) => (
              <div key={district} className="space-y-1">
                <div className="flex justify-between text-[10px] font-bold">
                  <span className="text-on-surface-variant uppercase">{district}</span>
                  <span className={speed < 35 ? "text-error" : "text-primary"}>{speed} km/h</span>
                </div>
                <div className="h-2 w-full bg-surface rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all duration-500 ${speed < 35 ? "bg-error" : "bg-primary"}`}
                    style={{ width: `${(speed / maxSpeed) * 100}%` }}
                  ></div>
                </div>
              </div>
            ))}
          </div>
          <div className="mt-8 p-4 bg-secondary-container rounded-lg">
            <div className="flex items-start gap-3">
              <span className="material-symbols-outlined text-on-secondary-container">lightbulb</span>
              <div>
                <p className="text-xs font-bold text-on-secondary-container">Optimization Tip</p>
                <p className="text-[10px] text-on-secondary-container/80 mt-1">
                  {data
                    ? `${[...data.districtSpeeds].sort((a, b) => a.speed - b.speed)[0]?.district} has lowest speed. Signal adjustment recommended.`
                    : "Loading..."}
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* AI Copilot Insight */}
        <div className="lg:col-span-2 bg-surface-container-lowest rounded-xl shadow-sm border-b-4 border-secondary-container relative overflow-hidden flex flex-col md:flex-row">
          <div className="p-8 md:w-2/3">
            <div className="flex items-center gap-2 mb-4">
              <span className="material-symbols-outlined text-primary">auto_awesome</span>
              <h5 className="text-sm font-bold text-on-surface uppercase tracking-widest">IRIS Intelligence Insight</h5>
            </div>
            <p className="text-lg font-medium text-on-surface mb-4 leading-relaxed">
              Anomalous traffic pattern detected on{" "}
              <span className="text-primary font-bold underline decoration-primary/30">Kings Highway</span>. Current congestion is 22% higher than seasonal average.
            </p>
            <div className="flex gap-4">
              <button
                onClick={() => router.push("/incidents")}
                className="text-xs font-bold py-2 px-4 rounded-full bg-surface ring-1 ring-outline-variant/20 hover:bg-surface-container-high transition-all"
              >
                Show Details
              </button>
              <button
                onClick={() => router.push("/map")}
                className="text-xs font-bold py-2 px-4 rounded-full text-white signature-gradient transition-all"
              >
                Optimize Route
              </button>
            </div>
          </div>
          <div className="md:w-1/3 bg-secondary-container/20 flex items-center justify-center p-8">
            <div className="w-32 h-32 rounded-full border-4 border-white shadow-lg bg-white flex items-center justify-center">
              <span className="material-symbols-outlined text-5xl text-primary font-light">psychology</span>
            </div>
          </div>
        </div>

        {/* Live Metrics */}
        <div className="bg-surface-container-lowest rounded-xl shadow-sm p-6 flex flex-col justify-between">
          <div>
            <h5 className="font-bold text-on-surface mb-1">Live Metrics</h5>
            <p className="text-xs text-on-surface-variant mb-6">Real-time KPIs</p>
          </div>
          <div className="space-y-4">
            {[
              { icon: "directions_car", label: "Vehicle Count", value: `${data?.vehicleCount ?? "—"}`, color: "text-primary" },
              { icon: "speed", label: "Avg Speed", value: `${data?.avgSpeed ?? "—"} MPH`, color: "text-primary" },
              { icon: "warning", label: "Active Incidents", value: `${data?.incidentCount ?? "—"}`, color: "text-error" },
            ].map(({ icon, label, value, color }) => (
              <div key={label} className="flex items-center justify-between p-3 bg-surface rounded-lg">
                <div className="flex items-center gap-3">
                  <span className={`material-symbols-outlined ${color}`}>{icon}</span>
                  <span className="text-sm font-medium text-on-surface">{label}</span>
                </div>
                <span className={`text-xl font-bold ${color}`}>{value}</span>
              </div>
            ))}
          </div>
          <button
            onClick={() => router.push("/map")}
            className="mt-6 w-full py-2.5 text-xs font-bold text-white signature-gradient rounded-full hover:brightness-110 transition-all"
          >
            View Live Map
          </button>
        </div>
      </div>

      <footer className="mt-12 flex justify-between items-center text-[10px] font-bold text-on-surface-variant uppercase tracking-[0.2em] opacity-50">
        <div>© 2024 IRIS Civil Solutions</div>
        <div className="flex gap-4">
          <a className="hover:text-primary transition-colors" href="#">Documentation</a>
          <a className="hover:text-primary transition-colors" href="#">Privacy</a>
        </div>
      </footer>
    </main>
  );
}
