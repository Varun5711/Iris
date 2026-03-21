"use client";

import { useEffect, useRef, useState } from "react";
import dynamic from "next/dynamic";
import type { Incident } from "@/lib/types";
import type { MapMarker, MapboxHandle, GeoJSONLayerDef } from "@/components/map/MapboxMap";
import type { BackendRecommendation, CopilotResponse, SignalAction, DiversionPlan } from "@/lib/backend";
import { useSettings } from "@/lib/settings-context";

const MapboxMap = dynamic(() => import("@/components/map/MapboxMap"), { ssr: false });

const ROUTE_COLORS = ["#3B82F6", "#10B981", "#8B5CF6", "#F59E0B", "#EC4899"];

export default function IncidentsPage() {
  const { settings } = useSettings();
  const mapRef = useRef<MapboxHandle | null>(null);

  const [incident, setIncident] = useState<Incident | null>(null);
  const [recommendations, setRecommendations] = useState<BackendRecommendation[]>([]);
  const [copilot, setCopilot] = useState<CopilotResponse | null>(null);
  const [activeRouteIdx, setActiveRouteIdx] = useState(0);
  const [actionState, setActionState] = useState<"idle" | "loading" | "approved" | "rejected">("idle");
  const [actionMsg, setActionMsg] = useState("");
  const [backendLive, setBackendLive] = useState(false);

  // Fetch incident
  useEffect(() => {
    fetch("/api/incidents")
      .then((r) => r.json())
      .then((data: Incident[]) => {
        const critical = data.find((i) => i.severity === "critical") ?? data[0];
        setIncident(critical ?? null);
      })
      .catch(() => {});
  }, []);

  // Fetch recommendations when incident changes
  useEffect(() => {
    if (!incident) return;
    fetch(`${process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000"}/recommendations/${incident.id}`, {
      signal: AbortSignal.timeout(4000),
    })
      .then((r) => r.json())
      .then((recs: BackendRecommendation[]) => {
        setRecommendations(recs);
        setBackendLive(true);
        // Use first rec's copilot_response
        const first = recs.find((r) => r.copilot_response) ?? recs[0];
        if (first?.copilot_response) setCopilot(first.copilot_response);
      })
      .catch(() => {
        // Use mock copilot data when backend is offline
        setCopilot({
          incident_summary: `${incident.title} — Active incident requiring immediate signal coordination.`,
          signal_actions: [
            { intersection_id: "INT-7th-Comal", action: "Extend green phase by +18s on northbound approach", expected_impact: "Queue reduction ~40%", confidence: 0.92 },
            { intersection_id: "INT-Madison-42nd", action: "Reduce cycle length from 90s to 72s", expected_impact: "Throughput +22%", confidence: 0.87 },
            { intersection_id: "INT-Broadway-34th", action: "Activate pedestrian hold during peak flush", expected_impact: "Vehicle throughput +15%", confidence: 0.84 },
          ],
          diversion_plan: {
            route_description: "Via Kings Highway bypass — avoids congested corridor entirely",
            estimated_extra_minutes: 7,
            traffic_redistribution_pct: 34,
            confidence: 0.91,
            evidence_refs: ["osm:graph", "hist:peak"],
            waypoints: [
              { name: "On-ramp Broadway", lat: incident.lat + 0.002, lng: incident.lng - 0.003 },
              { name: "Kings Hwy Junction", lat: incident.lat + 0.008, lng: incident.lng - 0.006 },
              { name: "Exit Flatbush Ave", lat: incident.lat + 0.014, lng: incident.lng - 0.002 },
            ],
          },
          alert_drafts: [],
          narrative: "IRIS recommends coordinated signal re-timing with diversion activation.",
          overall_confidence: 0.91,
          review_required: true,
          evidence_refs: ["osm:manhattan", "groq:llm"],
        });
      });
  }, [incident]);

  // Add GeoJSON layers when copilot data arrives
  useEffect(() => {
    if (!copilot || !incident) return;
    const map = mapRef.current;
    if (!map) return;

    // Diversion route layer from waypoints
    if (copilot.diversion_plan?.waypoints && copilot.diversion_plan.waypoints.length >= 2) {
      const waypoints = copilot.diversion_plan.waypoints;
      const color = ROUTE_COLORS[activeRouteIdx % ROUTE_COLORS.length];
      const layerDef: GeoJSONLayerDef = {
        id: "diversion-route-0",
        sourceId: "diversion-route-0-src",
        data: {
          type: "FeatureCollection",
          features: [{
            type: "Feature",
            geometry: {
              type: "LineString",
              coordinates: waypoints.map((w) => [w.lng, w.lat]),
            },
            properties: { route: "primary" },
          }],
        },
        layerType: "line",
        paint: {
          "line-color": color,
          "line-width": 5,
          "line-dasharray": [2, 1],
          "line-opacity": 0.9,
        },
      };
      if (settings.mapLayers.diversionRoutes) map.addGeoJSONLayer(layerDef);
    }

    // Signal action circles
    if (copilot.signal_actions?.length) {
      const features = copilot.signal_actions.map((sa, i) => ({
        type: "Feature" as const,
        geometry: {
          type: "Point" as const,
          coordinates: [
            incident.lng + (i - 1) * 0.003,
            incident.lat + (i % 2 === 0 ? 0.002 : -0.002),
          ],
        },
        properties: { intersection: sa.intersection_id, action: sa.action },
      }));
      const signalLayerDef: GeoJSONLayerDef = {
        id: "signal-circles",
        sourceId: "signal-circles-src",
        data: { type: "FeatureCollection", features },
        layerType: "circle",
        paint: {
          "circle-radius": 10,
          "circle-color": "#EAB308",
          "circle-stroke-width": 2,
          "circle-stroke-color": "#fff",
          "circle-opacity": 0.9,
        },
      };
      if (settings.mapLayers.signals) map.addGeoJSONLayer(signalLayerDef);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [copilot, incident]);

  // Sync map layer visibility with settings
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    map.setLayerVisibility("diversion-route-0", settings.mapLayers.diversionRoutes);
    map.setLayerVisibility("signal-circles", settings.mapLayers.signals);
  }, [settings.mapLayers]);

  const handleAction = async (action: "approve" | "reject") => {
    if (!incident || actionState === "loading") return;
    setActionState("loading");
    try {
      const recId = recommendations[0]?.id;
      const endpoint = recId
        ? `${process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000"}/recommendations/${recId}/${action}`
        : `/api/alerts/${incident.id}`;
      const res = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ officer_id: "officer-web", action, incidentId: incident.id }),
      });
      const data = await res.json();
      setActionState(action === "approve" ? "approved" : "rejected");
      setActionMsg(data.message ?? (action === "approve" ? "Recommendation approved and queued for execution." : "Recommendation rejected."));
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

  const signalActions: SignalAction[] = copilot?.signal_actions ?? [];
  const diversionPlan: DiversionPlan | undefined = copilot?.diversion_plan;
  const overallConfidence = copilot?.overall_confidence ?? 0.91;

  return (
    <main className="min-h-screen bg-surface p-8 pt-24 pb-12">
      {/* Page Header */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-6 mb-10">
        <div>
          <nav className="flex items-center gap-2 text-xs font-medium text-on-surface-variant mb-3">
            <span className="hover:text-primary cursor-pointer transition-colors">Incidents</span>
            <span className="material-symbols-outlined text-[14px]">chevron_right</span>
            <span className="text-primary font-semibold">{incident?.id ?? "INC-8821"}</span>
            {backendLive && (
              <span className="ml-2 px-2 py-0.5 bg-primary/10 text-primary text-[10px] font-bold rounded-full">BACKEND LIVE</span>
            )}
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
            <span className={`px-3 py-1 font-bold rounded-full text-[10px] uppercase tracking-wider ${
              incident?.severity === "critical"
                ? "bg-error-container text-on-error-container"
                : incident?.severity === "high"
                ? "bg-[#D97706]/20 text-[#D97706]"
                : "bg-tertiary-container/20 text-tertiary"
            }`}>
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
        {/* LEFT: Details & Signal Actions */}
        <div className="col-span-12 lg:col-span-3 space-y-6">
          <div className="bg-surface-container-lowest p-6 rounded-xl shadow-sm">
            <h3 className="text-xs font-bold uppercase tracking-widest text-primary mb-4">Description</h3>
            <p className="text-sm text-on-surface leading-relaxed mb-6">
              {copilot?.incident_summary ?? incident?.description ?? "Loading incident data..."}
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

          {/* Signal Re-timing Actions */}
          {signalActions.length > 0 && (
            <div className="bg-surface-container-lowest p-6 rounded-xl shadow-sm">
              <h3 className="text-xs font-bold uppercase tracking-widest text-[#EAB308] mb-4 flex items-center gap-2">
                <span className="material-symbols-outlined text-sm" style={{ fontVariationSettings: "'FILL' 1" }}>traffic</span>
                Signal Re-timing Plan
              </h3>
              <div className="space-y-4">
                {signalActions.map((sa, i) => (
                  <div key={i} className="p-3 bg-[#EAB308]/5 border border-[#EAB308]/20 rounded-lg">
                    <p className="text-[10px] font-extrabold text-[#EAB308] uppercase mb-1">{sa.intersection_id}</p>
                    <p className="text-xs font-semibold text-on-surface mb-1">{sa.action}</p>
                    <div className="flex items-center justify-between">
                      <p className="text-[10px] text-on-surface-variant">{sa.expected_impact}</p>
                      <span className="text-[10px] font-bold text-primary bg-primary/10 px-1.5 py-0.5 rounded">
                        {Math.round(sa.confidence * 100)}%
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Timeline */}
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
        <div className="col-span-12 lg:col-span-6 space-y-4">
          <div className="h-[500px] relative rounded-xl overflow-hidden">
            {incident ? (
              <MapboxMap
                ref={mapRef}
                center={[incident.lng, incident.lat]}
                zoom={15}
                markers={markers}
                className="w-full h-full"
                styleUrl="mapbox://styles/mapbox/light-v11"
                onMapReady={(h) => { mapRef.current = h; }}
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
                  <button
                    onClick={() => mapRef.current?.setLayerVisibility("diversion-route-0", true)}
                    className="w-8 h-8 rounded bg-primary text-white flex items-center justify-center shadow-sm"
                    title="Show diversion route"
                  >
                    <span className="material-symbols-outlined text-sm">alt_route</span>
                  </button>
                  <button
                    onClick={() => mapRef.current?.setLayerVisibility("signal-circles", true)}
                    className="w-8 h-8 rounded bg-[#EAB308] text-white flex items-center justify-center border border-outline-variant/20"
                    title="Show signal actions"
                  >
                    <span className="material-symbols-outlined text-sm">traffic</span>
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
                    Status: <span className={`font-bold ${incident?.status === "active" ? "text-error" : "text-primary"}`}>
                      {incident?.status === "active" ? "Critical Delay" : incident?.status ?? "—"}
                    </span>
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

          {/* Diversion Route Panel */}
          {diversionPlan && (
            <div className="bg-surface-container-lowest p-5 rounded-xl shadow-sm">
              <div className="flex items-center gap-2 mb-4">
                <span className="w-3 h-3 rounded-full" style={{ backgroundColor: ROUTE_COLORS[activeRouteIdx] }}></span>
                <h4 className="text-sm font-bold text-on-surface">Diversion Route — Activation Sequence</h4>
                <span className="ml-auto text-[10px] font-bold px-2 py-0.5 bg-primary/10 text-primary rounded-full">
                  {Math.round(diversionPlan.confidence * 100)}% confidence
                </span>
              </div>
              <p className="text-xs text-on-surface-variant mb-4">{diversionPlan.route_description}</p>
              <div className="grid grid-cols-3 gap-3 mb-4">
                <div className="bg-surface p-3 rounded-lg">
                  <p className="text-[10px] text-on-surface-variant uppercase font-bold mb-1">Extra Time</p>
                  <p className="text-base font-extrabold text-on-surface">+{diversionPlan.estimated_extra_minutes}m</p>
                </div>
                <div className="bg-surface p-3 rounded-lg">
                  <p className="text-[10px] text-on-surface-variant uppercase font-bold mb-1">Traffic Shift</p>
                  <p className="text-base font-extrabold text-primary">{diversionPlan.traffic_redistribution_pct}%</p>
                </div>
                <div className="bg-surface p-3 rounded-lg">
                  <p className="text-[10px] text-on-surface-variant uppercase font-bold mb-1">Waypoints</p>
                  <p className="text-base font-extrabold text-on-surface">{diversionPlan.waypoints.length}</p>
                </div>
              </div>
              {/* Activation sequence */}
              <div className="flex gap-2 overflow-x-auto pb-1">
                {diversionPlan.waypoints.map((wp, i) => (
                  <div key={i} className="flex items-center gap-1 flex-shrink-0">
                    <div className="flex flex-col items-center">
                      <div className="w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-extrabold text-white" style={{ backgroundColor: ROUTE_COLORS[activeRouteIdx] }}>
                        {i + 1}
                      </div>
                      <p className="text-[9px] text-on-surface-variant mt-1 text-center max-w-[60px]">{wp.name}</p>
                    </div>
                    {i < diversionPlan.waypoints.length - 1 && (
                      <span className="material-symbols-outlined text-sm text-on-surface-variant mt-[-12px]">arrow_forward</span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
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
            <div className="space-y-4">
              {signalActions.slice(0, 2).map((sa, i) => (
                <div key={i} className="p-4 bg-surface rounded-xl border-l-4 border-primary">
                  <p className="text-[10px] font-bold text-primary uppercase mb-1">Signal Strategy</p>
                  <p className="text-sm font-semibold text-on-surface mb-2">{sa.intersection_id}</p>
                  <p className="text-xs text-on-surface-variant mb-3">{sa.action}</p>
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] bg-primary-fixed text-on-primary-fixed px-2 py-0.5 rounded font-bold">
                      {Math.round(sa.confidence * 100)}% conf.
                    </span>
                    <span className="text-[10px] text-on-surface-variant">{sa.expected_impact}</span>
                  </div>
                </div>
              ))}

              {diversionPlan && (
                <div className="p-4 bg-surface rounded-xl border-l-4 border-[#3B82F6]">
                  <p className="text-[10px] font-bold text-[#3B82F6] uppercase mb-1">Diversion Route</p>
                  <p className="text-sm font-semibold text-on-surface mb-2">{diversionPlan.route_description.slice(0, 60)}{diversionPlan.route_description.length > 60 ? "…" : ""}</p>
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] bg-secondary-container text-on-secondary-container px-2 py-0.5 rounded font-bold">Active</span>
                    <span className="text-[10px] text-on-surface-variant">-{diversionPlan.traffic_redistribution_pct}% Vol.</span>
                  </div>
                </div>
              )}

              {!signalActions.length && !diversionPlan && (
                <>
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
                </>
              )}

              <div className="pt-4 border-t border-surface-container">
                <div className="flex justify-between items-end mb-2">
                  <p className="text-[10px] font-bold text-on-surface-variant uppercase">Overall Confidence</p>
                  <p className="text-lg font-bold text-primary">{Math.round(overallConfidence * 100)}%</p>
                </div>
                <div className="w-full h-1.5 bg-surface-container rounded-full overflow-hidden">
                  <div className="h-full bg-primary rounded-full" style={{ width: `${Math.round(overallConfidence * 100)}%` }}></div>
                </div>
                {copilot?.review_required && (
                  <p className="text-[10px] text-[#D97706] mt-2 flex items-center gap-1">
                    <span className="material-symbols-outlined text-[12px]">warning</span>
                    Human review required
                  </p>
                )}
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
              {signalActions.length > 0
                ? signalActions.map((sa) => (
                    <div key={sa.intersection_id} className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className="material-symbols-outlined text-lg text-[#EAB308]">traffic</span>
                        <span className="text-xs font-medium text-on-surface">{sa.intersection_id}</span>
                      </div>
                      <span className="w-2 h-2 rounded-full bg-[#EAB308]"></span>
                    </div>
                  ))
                : [
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

          {/* Narrative */}
          {copilot?.narrative && (
            <div className="bg-primary/5 p-5 rounded-xl">
              <p className="text-[10px] font-bold uppercase text-primary mb-2">IRIS Narrative</p>
              <p className="text-xs text-on-surface leading-relaxed">{copilot.narrative}</p>
            </div>
          )}
        </div>
      </div>
    </main>
  );
}
