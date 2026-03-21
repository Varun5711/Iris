"use client";

import { useEffect, useState } from "react";
import dynamic from "next/dynamic";
import type { Incident } from "@/lib/types";
import type { MapMarker } from "@/components/map/MapboxMap";

const MapboxMap = dynamic(() => import("@/components/map/MapboxMap"), { ssr: false });

export default function IncidentsPage() {
  const [incident, setIncident] = useState<Incident | null>(null);
  const [actionState, setActionState] = useState<"idle" | "loading" | "approved" | "rejected">("idle");
  const [actionMsg, setActionMsg] = useState("");

  useEffect(() => {
    fetch("/api/incidents")
      .then((r) => r.json())
      .then((data: Incident[]) => {
        const critical = data.find((i) => i.severity === "critical") ?? data[0];
        setIncident(critical);
      })
      .catch(() => {});
  }, []);

  const handleAction = async (action: "approve" | "reject") => {
    if (!incident || actionState === "loading") return;
    setActionState("loading");
    try {
      const res = await fetch(`/api/alerts/${incident.id}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action, incidentId: incident.id }),
      });
      const data = await res.json();
      setActionState(action === "approve" ? "approved" : "rejected");
      setActionMsg(data.message);
    } catch {
      setActionState("idle");
      setActionMsg("Failed to submit. Please try again.");
    }
  };

  const markers: MapMarker[] = incident
    ? [{ id: incident.id, lat: incident.lat, lng: incident.lng, type: "incident", severity: incident.severity, label: incident.id, popup: incident.title }]
    : [];

  const detectedMinutesAgo = incident
    ? Math.floor((Date.now() - new Date(incident.detectedAt).getTime()) / 60000)
    : 0;

  return (
    <main className="min-h-screen bg-surface p-8 pt-24 pb-12">
      {/* Page Header */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-6 mb-10">
        <div>
          <nav className="flex items-center gap-2 text-xs font-medium text-on-surface-variant mb-3">
            <span className="hover:text-primary cursor-pointer transition-colors">Incidents</span>
            <span className="material-symbols-outlined text-[14px]">chevron_right</span>
            <span className="text-primary font-semibold">{incident?.id ?? "INC-8821"}</span>
          </nav>
          <h1 className="text-4xl font-extrabold tracking-tight text-on-surface mb-2">
            {incident?.title ?? "Loading..."}
          </h1>
          <div className="flex flex-wrap items-center gap-4 text-sm">
            <span className="flex items-center gap-1.5 font-semibold text-on-surface">
              <span className="material-symbols-outlined text-sm text-primary">location_on</span>
              {incident?.location ?? "—"}
            </span>
            <span className="w-1.5 h-1.5 rounded-full bg-outline-variant"></span>
            <span className="flex items-center gap-1.5 text-on-surface-variant">
              <span className="material-symbols-outlined text-sm">schedule</span>
              Detected {detectedMinutesAgo}m ago
            </span>
            <span
              className={`px-3 py-1 font-bold rounded-full text-[10px] uppercase tracking-wider ${
                incident?.severity === "critical"
                  ? "bg-error-container text-on-error-container"
                  : incident?.severity === "high"
                  ? "bg-[#D97706]/20 text-[#D97706]"
                  : "bg-tertiary-container/20 text-tertiary"
              }`}
            >
              {incident?.severity ?? "High"} Severity
            </span>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <button className="px-6 py-2.5 rounded-full font-bold text-sm text-primary hover:bg-primary/5 transition-colors">
            Export Report
          </button>
          <button className="px-8 py-2.5 rounded-full signature-gradient text-white font-bold text-sm shadow-md active:scale-95 transition-all">
            Initiate Protocol
          </button>
        </div>
      </div>

      {/* Bento Grid */}
      <div className="grid grid-cols-12 gap-6">
        {/* LEFT: Details & Timeline */}
        <div className="col-span-12 lg:col-span-3 space-y-6">
          <div className="bg-surface-container-lowest p-6 rounded-xl shadow-sm">
            <h3 className="text-xs font-bold uppercase tracking-widest text-primary mb-4">Description</h3>
            <p className="text-sm text-on-surface leading-relaxed mb-6">
              {incident?.description ?? "Loading incident data..."}
            </p>
            <div className="grid grid-cols-2 gap-4">
              <div className="bg-surface p-3 rounded-lg">
                <p className="text-[10px] text-on-surface-variant uppercase font-bold mb-1">Impact Radius</p>
                <p className="text-lg font-bold text-on-surface">{incident?.impactRadius ?? "—"}</p>
              </div>
              <div className="bg-surface p-3 rounded-lg">
                <p className="text-[10px] text-on-surface-variant uppercase font-bold mb-1">Delay Est.</p>
                <p className="text-lg font-bold text-on-surface">{incident?.delayEstimate ?? "—"}</p>
              </div>
            </div>
          </div>

          <div className="bg-surface-container-lowest p-6 rounded-xl shadow-sm">
            <h3 className="text-xs font-bold uppercase tracking-widest text-primary mb-6">Timeline of Events</h3>
            <div className="space-y-6 relative before:absolute before:left-[11px] before:top-2 before:bottom-2 before:w-[2px] before:bg-surface-container">
              <div className="relative pl-8">
                <div className="absolute left-0 top-1 w-[24px] h-[24px] bg-white border-4 border-primary rounded-full z-10"></div>
                <p className="text-[11px] font-bold text-primary uppercase">Now</p>
                <p className="text-sm font-semibold text-on-surface">Queue length exceeded 800m</p>
              </div>
              <div className="relative pl-8">
                <div className="absolute left-[6px] top-1.5 w-3 h-3 bg-surface-container rounded-full z-10"></div>
                <p className="text-[11px] font-bold text-on-surface-variant uppercase">-8 min</p>
                <p className="text-sm text-on-surface-variant">Congestion spillback to side streets</p>
              </div>
              <div className="relative pl-8">
                <div className="absolute left-[6px] top-1.5 w-3 h-3 bg-surface-container rounded-full z-10"></div>
                <p className="text-[11px] font-bold text-on-surface-variant uppercase">-{detectedMinutesAgo} min</p>
                <p className="text-sm text-on-surface-variant">Initial surge detected</p>
              </div>
            </div>
          </div>
        </div>

        {/* CENTER: Live Map */}
        <div className="col-span-12 lg:col-span-6 h-[600px] relative rounded-xl overflow-hidden">
          {incident ? (
            <MapboxMap
              center={[incident.lng, incident.lat]}
              zoom={15}
              markers={markers}
              className="w-full h-full"
              style="mapbox://styles/mapbox/light-v11"
            />
          ) : (
            <div className="w-full h-full bg-surface-container-low flex items-center justify-center">
              <span className="material-symbols-outlined text-4xl text-on-surface-variant animate-pulse">map</span>
            </div>
          )}

          <div className="absolute top-4 left-4 flex flex-col gap-2 z-10">
            <div className="bg-white/90 backdrop-blur-md p-3 rounded-lg shadow-xl">
              <p className="text-[10px] font-bold uppercase text-on-surface-variant mb-2">Map Layers</p>
              <div className="flex gap-2">
                <button className="w-8 h-8 rounded bg-primary text-white flex items-center justify-center shadow-sm">
                  <span className="material-symbols-outlined text-sm">traffic</span>
                </button>
                <button className="w-8 h-8 rounded bg-white text-on-surface flex items-center justify-center border border-outline-variant/20">
                  <span className="material-symbols-outlined text-sm">videocam</span>
                </button>
                <button className="w-8 h-8 rounded bg-white text-on-surface flex items-center justify-center border border-outline-variant/20">
                  <span className="material-symbols-outlined text-sm">sensors</span>
                </button>
              </div>
            </div>
          </div>

          <div className="absolute bottom-4 left-4 right-4 z-10 bg-white/90 backdrop-blur-md p-4 rounded-xl shadow-2xl flex items-center justify-between border border-white">
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 rounded-lg bg-error-container/20 flex items-center justify-center">
                <span className="material-symbols-outlined text-error" style={{ fontVariationSettings: "'FILL' 1" }}>emergency_share</span>
              </div>
              <div>
                <p className="text-xs font-bold text-on-surface">{incident?.location ?? "Loading..."}</p>
                <p className="text-xs text-on-surface-variant">
                  Status: <span className={`font-bold ${incident?.status === "active" ? "text-error" : "text-primary"}`}>{incident?.status === "active" ? "Critical Delay" : incident?.status ?? "—"}</span>
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-[10px] font-bold text-on-surface-variant bg-surface-container px-2 py-1 rounded">
                LAT: {incident?.lat.toFixed(4) ?? "—"}
              </span>
              <span className="text-[10px] font-bold text-on-surface-variant bg-surface-container px-2 py-1 rounded">
                LNG: {incident?.lng.toFixed(4) ?? "—"}
              </span>
            </div>
          </div>
        </div>

        {/* RIGHT: AI Recommendations */}
        <div className="col-span-12 lg:col-span-3 space-y-6">
          <div className="bg-surface-container-lowest p-6 rounded-xl shadow-sm border-b-4 border-secondary-container">
            <div className="flex items-center gap-2 mb-6">
              <div className="w-8 h-8 bg-secondary-container rounded-full flex items-center justify-center">
                <span className="material-symbols-outlined text-primary text-sm" style={{ fontVariationSettings: "'FILL' 1" }}>smart_toy</span>
              </div>
              <h3 className="text-sm font-bold text-on-surface">IRIS AI Recommendations</h3>
            </div>
            <div className="space-y-6">
              <div className="p-4 bg-surface rounded-xl border-l-4 border-primary">
                <p className="text-[10px] font-bold text-primary uppercase mb-1">Signal Strategy</p>
                <p className="text-sm font-semibold text-on-surface mb-2">Adjust Cycle Pattern A-42</p>
                <p className="text-xs text-on-surface-variant mb-3">Increase green-time for Northbound flow by 15s to flush the exit queue.</p>
                <div className="flex items-center gap-2">
                  <span className="text-[10px] bg-primary-fixed text-on-primary-fixed px-2 py-0.5 rounded font-bold">High Impact</span>
                  <span className="text-[10px] text-on-surface-variant">Est. recovery: 12m</span>
                </div>
              </div>
              <div className="p-4 bg-surface rounded-xl border-l-4 border-primary">
                <p className="text-[10px] font-bold text-primary uppercase mb-1">Diversion Route</p>
                <p className="text-sm font-semibold text-on-surface mb-2">Activate VMS Signs Sector 4</p>
                <p className="text-xs text-on-surface-variant mb-3">Redirect non-essential traffic to alternate Route 7 bypass.</p>
                <div className="flex items-center gap-2">
                  <span className="text-[10px] bg-secondary-container text-on-secondary-container px-2 py-0.5 rounded font-bold">Moderate</span>
                  <span className="text-[10px] text-on-surface-variant">Impact: -20% Vol.</span>
                </div>
              </div>
              <div className="pt-4 border-t border-surface-container">
                <div className="flex justify-between items-end mb-2">
                  <p className="text-[10px] font-bold text-on-surface-variant uppercase">Confidence Score</p>
                  <p className="text-lg font-bold text-primary">94%</p>
                </div>
                <div className="w-full h-1.5 bg-surface-container rounded-full overflow-hidden">
                  <div className="h-full bg-primary rounded-full w-[94%]"></div>
                </div>
              </div>
            </div>

            {/* Action Buttons */}
            {actionState === "idle" || actionState === "loading" ? (
              <div className="grid grid-cols-2 gap-3 mt-8">
                <button
                  onClick={() => handleAction("reject")}
                  disabled={actionState === "loading"}
                  className="py-3 rounded-full bg-white border border-outline-variant/30 text-error font-bold text-sm hover:bg-error/5 transition-colors disabled:opacity-50"
                >
                  {actionState === "loading" ? "..." : "Reject"}
                </button>
                <button
                  onClick={() => handleAction("approve")}
                  disabled={actionState === "loading"}
                  className="py-3 rounded-full signature-gradient text-white font-bold text-sm shadow-lg active:scale-95 transition-all disabled:opacity-50"
                >
                  {actionState === "loading" ? "..." : "Approve"}
                </button>
              </div>
            ) : (
              <div className={`mt-8 p-4 rounded-xl text-sm font-medium text-center ${actionState === "approved" ? "bg-primary-container/20 text-primary" : "bg-error-container/20 text-error"}`}>
                <span className="material-symbols-outlined text-base align-middle mr-1" style={{ fontVariationSettings: "'FILL' 1" }}>
                  {actionState === "approved" ? "check_circle" : "cancel"}
                </span>
                {actionMsg}
                <button onClick={() => { setActionState("idle"); setActionMsg(""); }} className="block text-xs mt-2 text-on-surface-variant underline mx-auto">Reset</button>
              </div>
            )}
          </div>

          {/* Affected Assets */}
          <div className="bg-surface-container-lowest p-5 rounded-xl shadow-sm">
            <h4 className="text-[10px] font-bold uppercase text-on-surface-variant mb-4">Affected Assets</h4>
            <div className="space-y-3">
              {[
                { icon: "traffic", label: "Signals 101-A, 101-B" },
                { icon: "screenshot_monitor", label: "VMS Panel 04, 05" },
                { icon: "camera_outdoor", label: "CCTV Cam 22-North" },
              ].map(({ icon, label }) => (
                <div key={label} className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="material-symbols-outlined text-lg text-on-surface-variant">{icon}</span>
                    <span className="text-xs font-medium text-on-surface">{label}</span>
                  </div>
                  <span className="w-2 h-2 rounded-full bg-primary"></span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}
