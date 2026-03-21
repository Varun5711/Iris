"use client";

import { useEffect, useState, useCallback } from "react";
import type { LogEntry } from "@/ui_lib/types";

const TYPE_CONFIG: Record<string, { label: string; icon: string; color: string; bg: string }> = {
  ai_autonomy: { label: "AI Autonomy", icon: "smart_toy", color: "text-primary", bg: "bg-primary-container/20" },
  admin_override: { label: "Admin Override", icon: "admin_panel_settings", color: "text-tertiary", bg: "bg-tertiary-container/20" },
  system: { label: "System", icon: "dns", color: "text-on-surface-variant", bg: "bg-surface-container-high" },
  critical: { label: "Critical", icon: "error", color: "text-error", bg: "bg-error-container/20" },
  ai_inference: { label: "AI Inference", icon: "psychology", color: "text-primary", bg: "bg-secondary-container/30" },
};

function timeAgo(isoString: string) {
  const diff = Math.floor((Date.now() - new Date(isoString).getTime()) / 60000);
  if (diff < 1) return "just now";
  if (diff < 60) return `${diff}m ago`;
  const hrs = Math.floor(diff / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

export default function LogsPage() {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [filter, setFilter] = useState("all");
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState("");

  const load = useCallback(async () => {
    try {
      const res = await fetch("/api/logs");
      const data = await res.json();
      setLogs(data);
      setLastUpdated(new Date().toLocaleTimeString());
    } catch {
      // keep last
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    const iv = setInterval(load, 30000);
    return () => clearInterval(iv);
  }, [load]);

  const filtered = logs.filter((l) => {
    const matchType = filter === "all" || l.type === filter;
    const matchSearch =
      !search ||
      l.title.toLowerCase().includes(search.toLowerCase()) ||
      l.description.toLowerCase().includes(search.toLowerCase()) ||
      l.actor.toLowerCase().includes(search.toLowerCase());
    return matchType && matchSearch;
  });

  return (
    <main className="min-h-screen bg-surface pt-24">
      <div className="max-w-6xl mx-auto p-8">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-6 mb-10">
          <div>
            <h2 className="text-3xl font-extrabold text-on-surface tracking-tight">System Activity Log</h2>
            <p className="text-on-surface-variant mt-1 text-sm">
              Audit trail of all AI actions, operator overrides, and system events.
              {lastUpdated && <span className="ml-2 text-primary font-semibold">· Updated {lastUpdated}</span>}
            </p>
          </div>
          <div className="flex gap-3">
            <button onClick={() => load()} className="px-4 py-2 text-sm font-bold text-primary hover:bg-primary/5 rounded-full flex items-center gap-2 transition-colors">
              <span className="material-symbols-outlined text-sm">refresh</span> Refresh
            </button>
            <button className="px-6 py-2 text-sm font-bold text-white signature-gradient rounded-full shadow-md">
              Export Log
            </button>
          </div>
        </div>

        {/* Search & Filters */}
        <div className="flex flex-col md:flex-row gap-4 mb-8">
          <div className="flex-1 flex items-center gap-3 bg-surface-container-lowest rounded-xl px-4 py-3 shadow-sm">
            <span className="material-symbols-outlined text-on-surface-variant">search</span>
            <input
              className="flex-1 bg-transparent outline-none text-sm placeholder:text-on-surface-variant/50"
              placeholder="Search logs by title, actor, or description..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
            {search && (
              <button onClick={() => setSearch("")} className="text-on-surface-variant hover:text-primary transition-colors">
                <span className="material-symbols-outlined text-sm">close</span>
              </button>
            )}
          </div>
          <div className="flex gap-2 flex-wrap">
            {["all", "ai_autonomy", "ai_inference", "admin_override", "critical", "system"].map((t) => (
              <button
                key={t}
                onClick={() => setFilter(t)}
                className={`px-4 py-2 rounded-full text-xs font-bold transition-all ${
                  filter === t
                    ? "bg-primary text-white shadow-sm"
                    : "bg-surface-container-lowest text-on-surface-variant hover:bg-surface-container-low"
                }`}
              >
                {t === "all" ? "All Events" : TYPE_CONFIG[t]?.label ?? t}
              </button>
            ))}
          </div>
        </div>

        {/* Log Stats */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
          {[
            { label: "Total Events", value: logs.length, icon: "list_alt", color: "text-primary" },
            { label: "AI Actions", value: logs.filter((l) => l.type.startsWith("ai")).length, icon: "smart_toy", color: "text-primary" },
            { label: "Critical", value: logs.filter((l) => l.type === "critical").length, icon: "error", color: "text-error" },
            { label: "Overrides", value: logs.filter((l) => l.type === "admin_override").length, icon: "admin_panel_settings", color: "text-tertiary" },
          ].map(({ label, value, icon, color }) => (
            <div key={label} className="bg-surface-container-lowest p-4 rounded-xl shadow-sm flex items-center gap-3">
              <span className={`material-symbols-outlined ${color}`}>{icon}</span>
              <div>
                <p className="text-lg font-bold text-on-surface">{value}</p>
                <p className="text-[10px] font-bold text-on-surface-variant uppercase">{label}</p>
              </div>
            </div>
          ))}
        </div>

        {/* Log Entries */}
        {loading ? (
          <div className="space-y-4">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="h-24 bg-surface-container-lowest rounded-xl animate-pulse"></div>
            ))}
          </div>
        ) : filtered.length === 0 ? (
          <div className="text-center py-16 text-on-surface-variant">
            <span className="material-symbols-outlined text-4xl mb-2">search_off</span>
            <p className="font-medium">No log entries match your filters.</p>
          </div>
        ) : (
          <div className="relative space-y-0">
            <div className="absolute left-[27px] top-8 bottom-8 w-[2px] bg-surface-container-low"></div>
            {filtered.map((log, idx) => {
              const cfg = TYPE_CONFIG[log.type] ?? TYPE_CONFIG.system;
              return (
                <div key={log.id} className="relative pl-16 pb-8">
                  {/* Timeline dot */}
                  <div className={`absolute left-0 top-1 w-[56px] flex justify-end pr-4`}>
                    <div className={`w-8 h-8 rounded-full flex items-center justify-center ${cfg.bg} shrink-0 ring-4 ring-surface`}>
                      <span className={`material-symbols-outlined text-[16px] ${cfg.color}`} style={{ fontVariationSettings: "'FILL' 1" }}>{cfg.icon}</span>
                    </div>
                  </div>

                  <div className="bg-surface-container-lowest rounded-xl p-5 shadow-sm hover:shadow-md transition-shadow group">
                    <div className="flex items-start justify-between gap-4 mb-2">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${cfg.bg} ${cfg.color}`}>
                          {cfg.label}
                        </span>
                        <span className="text-[10px] font-bold text-on-surface-variant">{log.id}</span>
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        <span className="text-[10px] text-on-surface-variant">{timeAgo(log.timestamp)}</span>
                        <button className="opacity-0 group-hover:opacity-100 transition-opacity text-on-surface-variant hover:text-primary">
                          <span className="material-symbols-outlined text-sm">more_vert</span>
                        </button>
                      </div>
                    </div>
                    <h4 className="font-bold text-on-surface mb-1">{log.title}</h4>
                    <p className="text-sm text-on-surface-variant leading-relaxed">{log.description}</p>
                    <div className="flex items-center gap-4 mt-3 text-[10px] font-bold text-on-surface-variant">
                      <span className="flex items-center gap-1">
                        <span className="material-symbols-outlined text-sm">person</span>
                        {log.actor}
                      </span>
                      <span className="flex items-center gap-1">
                        <span className="material-symbols-outlined text-sm">schedule</span>
                        {new Date(log.timestamp).toLocaleString()}
                      </span>
                    </div>
                    {log.metadata && Object.keys(log.metadata).length > 0 && (
                      <div className="flex flex-wrap gap-2 mt-3">
                        {Object.entries(log.metadata).map(([k, v]) => (
                          <span key={k} className="text-[9px] font-bold px-2 py-0.5 bg-surface rounded-full text-on-surface-variant border border-outline-variant/20">
                            {k}: {v}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </main>
  );
}
