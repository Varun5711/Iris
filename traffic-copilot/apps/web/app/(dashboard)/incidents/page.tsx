"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import dynamic from "next/dynamic";
import type { Incident } from "@/ui_lib/types";
import type {
  MapMarker,
  MapboxHandle,
  GeoJSONLayerDef,
} from "@/components/map/MapboxMap";
import type {
  BackendRecommendation,
  CopilotResponse,
  SignalAction,
  DiversionPlan,
  BackendAlert,
} from "@/ui_lib/backend";
import { useSettings } from "@/ui_lib/settings-context";
import { connectToIncident } from "@/src/lib/ws";

const MapboxMap = dynamic(() => import("@/components/map/MapboxMap"), {
  ssr: false,
});

const BACKEND = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";
const ROUTE_COLORS = ["#3B82F6", "#10B981", "#8B5CF6", "#F59E0B", "#EC4899"];

export default function IncidentsPage() {
  const { settings } = useSettings();
  const mapRef = useRef<MapboxHandle | null>(null);

  const [incident, setIncident] = useState<Incident | null>(null);
  const [recommendations, setRecommendations] = useState<
    BackendRecommendation[]
  >([]);
  const [copilot, setCopilot] = useState<CopilotResponse | null>(null);
  const [mapGeoData, setMapGeoData] =
    useState<GeoJSON.FeatureCollection | null>(null);
  const [alerts, setAlerts] = useState<BackendAlert[]>([]);
  const [activeRouteIdx, setActiveRouteIdx] = useState(0);
  const [actionState, setActionState] = useState<
    "idle" | "loading" | "approved" | "rejected"
  >("idle");
  const [actionMsg, setActionMsg] = useState("");
  const [backendLive, setBackendLive] = useState(false);
  // Field report modal (audio + image tabs)
  const [voiceOpen, setVoiceOpen] = useState(false);
  const [reportTab, setReportTab] = useState<"audio" | "image">("audio");
  const [voiceFile, setVoiceFile] = useState<File | null>(null);
  const [voiceLoading, setVoiceLoading] = useState(false);
  const [voiceMsg, setVoiceMsg] = useState("");
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [imagePreview, setImagePreview] = useState<string | null>(null);
  const [imageLoading, setImageLoading] = useState(false);
  const [imageMsg, setImageMsg] = useState("");
  const [imageDragOver, setImageDragOver] = useState(false);
  const [allIncidents, setAllIncidents] = useState<Incident[]>([]);
  const [mapReady, setMapReady] = useState(false);
  const [dataLoading, setDataLoading] = useState(false);

  // IRIS Assistant chat — scoped to the current incident
  const [chatMessages, setChatMessages] = useState<
    { role: "user" | "assistant"; content: string }[]
  >([]);
  const [chatInput, setChatInput] = useState("");
  const [chatLoading, setChatLoading] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);

  const sendChat = useCallback(async () => {
    if (!chatInput.trim() || !incident || chatLoading) return;
    const q = chatInput.trim();
    setChatInput("");
    const userMsg = { role: "user" as const, content: q };
    setChatMessages((p) => [
      ...p,
      userMsg,
      { role: "assistant", content: "…" },
    ]);
    setChatLoading(true);
    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          incidentId: incident.id,
          question: q,
          officerId: "officer-web",
        }),
      });
      const d = await res.json();
      const answer =
        d.answer ??
        d.copilot_response?.conversational_answer ??
        "Unable to process.";
      setChatMessages((p) => [
        ...p.slice(0, -1),
        { role: "assistant", content: answer },
      ]);
    } catch {
      setChatMessages((p) => [
        ...p.slice(0, -1),
        { role: "assistant", content: "Connection error. Please try again." },
      ]);
    } finally {
      setChatLoading(false);
      setTimeout(
        () => chatEndRef.current?.scrollIntoView({ behavior: "smooth" }),
        50,
      );
    }
  }, [chatInput, incident, chatLoading]);

  // Clear chat when incident changes
  useEffect(() => {
    setChatMessages([]);
  }, [incident?.id]);

  const loadIncidentData = useCallback(async (inc: Incident) => {
    setDataLoading(true);
    try {
      // 1. Recommendations
      const recRes = await fetch(`${BACKEND}/recommendations/${inc.id}`, {
        signal: AbortSignal.timeout(6000),
      });
      if (recRes.ok) {
        const recs: BackendRecommendation[] = await recRes.json();
        setRecommendations(recs);
        setBackendLive(true);
        // Prefer composite rec (has signal_actions + diversion_plan), fall back to any with copilot_response
        const first =
          recs.find((r) => r.rec_type === "composite" && r.copilot_response) ??
          recs.find((r) => r.copilot_response?.signal_actions?.length) ??
          recs.find((r) => r.copilot_response) ??
          recs[0];
        if (first?.copilot_response) setCopilot(first.copilot_response);
      }
    } catch {}

    try {
      // 2. Real OSM A*-routed map data
      const mapRes = await fetch(`${BACKEND}/incidents/${inc.id}/map-data`, {
        signal: AbortSignal.timeout(8000),
      });
      if (mapRes.ok) setMapGeoData(await mapRes.json());
    } catch {}

    try {
      // 3. Draft alerts
      const alertRes = await fetch(`${BACKEND}/alerts/${inc.id}`, {
        signal: AbortSignal.timeout(4000),
      });
      if (alertRes.ok) setAlerts(await alertRes.json());
    } catch {}

    setDataLoading(false);
  }, []);

  // Fetch all incidents — auto-select most critical
  useEffect(() => {
    fetch("/api/incidents")
      .then((r) => r.json())
      .then((data: Incident[]) => {
        setAllIncidents(data);
        const critical = data.find((i) => i.severity === "critical") ?? data[0];
        if (critical) setIncident(critical);
      })
      .catch(() => {});
  }, []);

  // Load all data when incident is set.
  // Also reset mapReady so the false→true transition always re-fires the layer effect,
  // preventing a race where mapGeoData arrives while the new map isn't ready yet.
  useEffect(() => {
    if (!incident) return;
    setMapReady(false);
    setMapGeoData(null);
    loadIncidentData(incident);
  }, [incident, loadIncidentData]);

  // Wire WebSocket — auto-refresh when recommendation arrives
  useEffect(() => {
    if (!incident) return;
    const ws = connectToIncident(incident.id, (msg) => {
      if (
        msg.event_type === "recommendation_ready" ||
        msg.event_type === "state_updated"
      ) {
        loadIncidentData(incident);
      }
    });
    return () => ws.close();
  }, [incident, loadIncidentData]);

  // Add GeoJSON layers from real OSM A* map-data — waits for both data AND map to be ready
  useEffect(() => {
    if (!mapGeoData || !incident || !mapReady) return;
    const map = mapRef.current;
    if (!map) return;

    const features = mapGeoData.features ?? [];

    // Diversion route(s) — same rendering as live map page (no coord filter, identical paint)
    const diversionFeatures = features.filter(
      (f) => f.properties?.feature_type === "diversion_route",
    );
    diversionFeatures.forEach((feat, i) => {
      if (!settings.mapLayers.diversionRoutes) return;
      const color = ROUTE_COLORS[i % ROUTE_COLORS.length];
      const layerId = `diversion-route-${i}`;
      map.addGeoJSONLayer({
        id: layerId,
        sourceId: `${layerId}-src`,
        data: { type: "FeatureCollection", features: [feat] },
        layerType: "line",
        paint: {
          "line-color": color,
          "line-width": i === 0 ? 5 : 3.5,
          "line-opacity": i === 0 ? 0.95 : 0.75,
          "line-dasharray": [4, 2],
        },
        layout: { "line-cap": "round", "line-join": "round" },
      });
    });

    // Affected road segments (orange)
    const affectedFeatures = features.filter(
      (f) => f.properties?.feature_type === "affected_segment",
    );
    if (affectedFeatures.length > 0 && settings.mapLayers.affectedSegments) {
      map.addGeoJSONLayer({
        id: "affected-segments",
        sourceId: "affected-segments-src",
        data: { type: "FeatureCollection", features: affectedFeatures },
        layerType: "line",
        layout: { "line-join": "round", "line-cap": "round" },
        paint: {
          "line-color": "#FF4500",
          "line-width": 6,
          "line-opacity": 0.85,
        },
      });
    }

    // Signal action points (yellow)
    const signalFeatures = features.filter(
      (f) => f.properties?.feature_type === "signal_action",
    );
    if (signalFeatures.length > 0 && settings.mapLayers.signals) {
      map.addGeoJSONLayer({
        id: "signal-circles",
        sourceId: "signal-circles-src",
        data: { type: "FeatureCollection", features: signalFeatures },
        layerType: "circle",
        paint: {
          "circle-radius": 10,
          "circle-color": "#EAB308",
          "circle-stroke-width": 2,
          "circle-stroke-color": "#fff",
          "circle-opacity": 0.9,
        },
      });
    }

    // Fly to incident point
    const incidentPoint = features.find(
      (f) => f.properties?.feature_type === "incident_point",
    );
    if (incidentPoint && incidentPoint.geometry.type === "Point") {
      const [lon, lat] = (incidentPoint.geometry as GeoJSON.Point).coordinates;
      map.flyTo([lon, lat], 14);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mapGeoData, incident, mapReady]);

  // Fallback: when backend has no A* diversion route, use Mapbox Directions API with copilot waypoints
  // This gives real road-following routes even when the OSM graph is sparse
  useEffect(() => {
    const noAStarRoute = !(mapGeoData?.features ?? []).some(
      (f) => f.properties?.feature_type === "diversion_route",
    );
    if (!noAStarRoute || !copilot || !incident || !mapReady) return;
    const map = mapRef.current;
    if (!map) return;
    const waypoints = copilot.diversion_plan?.waypoints;
    if (!waypoints || waypoints.length < 2) return;
    if (!settings.mapLayers.diversionRoutes) return;

    const token = process.env.NEXT_PUBLIC_MAPBOX_TOKEN;
    if (!token) return;

    const coords = waypoints.map((w) => `${w.lng},${w.lat}`).join(";");
    (async () => {
      try {
        const res = await fetch(
          `https://api.mapbox.com/directions/v5/mapbox/driving/${coords}?geometries=geojson&overview=full&access_token=${token}`,
          { signal: AbortSignal.timeout(6000) },
        );
        if (!res.ok) return;
        const data = await res.json();
        const geometry = data.routes?.[0]?.geometry;
        if (!geometry) return;
        map.addGeoJSONLayer({
          id: "diversion-route-0",
          sourceId: "diversion-route-0-src",
          data: {
            type: "FeatureCollection",
            features: [{ type: "Feature", geometry, properties: {} }],
          },
          layerType: "line",
          paint: {
            "line-color": ROUTE_COLORS[0],
            "line-width": 5,
            "line-opacity": 0.95,
            "line-dasharray": [4, 2],
          },
          layout: { "line-cap": "round", "line-join": "round" },
        });
      } catch {}
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [copilot, incident, mapGeoData, mapReady]);

  // Sync layer visibility with settings
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    map.setLayerVisibility(
      "diversion-route-0",
      settings.mapLayers.diversionRoutes,
    );
    map.setLayerVisibility("affected-segments", settings.mapLayers.affectedSegments);
    map.setLayerVisibility("signal-circles", settings.mapLayers.signals);
  }, [settings.mapLayers]);

  // Approve / reject recommendation
  // Prefer the recommendation that the alerts are linked to (not just the newest one, which may be a chat rec)
  const handleAction = async (action: "approve" | "reject") => {
    if (!incident || actionState === "loading") return;
    setActionState("loading");
    try {
      // Find the rec linked to alerts first, then any non-chat rec, then fall back to newest
      const alertLinkedRecId = alerts[0]?.recommendation_id;
      const recId =
        (alertLinkedRecId &&
          recommendations.find((r) => r.id === alertLinkedRecId)?.id) ||
        recommendations.find((r) => r.rec_type !== "chat")?.id ||
        recommendations[0]?.id;
      if (!recId) throw new Error("No recommendation to action");
      const endpoint = `${BACKEND}/recommendations/${recId}/${action}`;
      const res = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ officer_id: "officer-web" }),
      });
      const data = await res.json();
      if (!res.ok) {
        // 409 means already approved/rejected — treat approve-on-approved as success
        if (res.status === 409 && action === "approve") {
          setActionState("approved");
          setActionMsg("Recommendation already approved.");
          return;
        }
        throw new Error(data.detail ?? `HTTP ${res.status}`);
      }
      setActionState(action === "approve" ? "approved" : "rejected");
      setActionMsg(
        data.message ??
          (action === "approve"
            ? "Recommendation approved."
            : "Recommendation rejected."),
      );
    } catch (err) {
      setActionState("idle");
      setActionMsg(`Failed: ${String(err)}`);
    }
  };

  // Publish a single alert
  const publishAlert = async (alertId: string) => {
    try {
      const res = await fetch(`${BACKEND}/alerts/${alertId}/publish`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ officer_id: "officer-web" }),
      });
      if (res.ok) {
        setAlerts((prev) =>
          prev.map((a) =>
            a.id === alertId ? { ...a, status: "published" } : a,
          ),
        );
      } else {
        const err = await res.json().catch(() => ({}));
        setActionMsg(`Publish failed: ${err.detail ?? `HTTP ${res.status}`}`);
      }
    } catch (e) {
      setActionMsg(`Publish failed: ${String(e)}`);
    }
  };

  // Voice report submission
  const submitVoiceReport = async () => {
    if (!voiceFile) return;
    setVoiceLoading(true);
    setVoiceMsg("");
    try {
      const fd = new FormData();
      fd.append("audio", voiceFile);
      fd.append("officer_id", "officer-web");
      const res = await fetch(`${BACKEND}/incidents/voice-report`, {
        method: "POST",
        body: fd,
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setVoiceMsg(
        `✓ Incident created — severity: ${data.severity}, corridor: ${data.corridor_id ?? "unknown"}`,
      );
      setVoiceFile(null);
    } catch (err) {
      setVoiceMsg(`Failed: ${String(err)}`);
    } finally {
      setVoiceLoading(false);
    }
  };

  // Image report submission — POST /incidents/{id}/vision
  const submitImageReport = async () => {
    if (!imageFile || !incident) return;
    setImageLoading(true);
    setImageMsg("");
    try {
      const fd = new FormData();
      fd.append("image", imageFile);
      fd.append("officer_id", "officer-web");
      const res = await fetch(`${BACKEND}/incidents/${incident.id}/vision`, {
        method: "POST",
        body: fd,
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail ?? `HTTP ${res.status}`);
      }
      const data = await res.json();
      const label = data.top_label ?? "unknown";
      const conf = data.confidence != null
        ? ` (${Math.round(data.confidence * 100)}% confidence)`
        : "";
      const detected = data.incident_detected ? "incident detected" : "no incident detected";
      setImageMsg(`✓ Vision analysis complete — ${label}${conf} · ${detected}`);
      setImageFile(null);
      setImagePreview(null);
    } catch (err) {
      setImageMsg(`Failed: ${String(err)}`);
    } finally {
      setImageLoading(false);
    }
  };

  // Image file picker helper
  const handleImageFile = (file: File) => {
    setImageFile(file);
    const reader = new FileReader();
    reader.onload = (e) => setImagePreview(e.target?.result as string);
    reader.readAsDataURL(file);
  };

  // Switch active incident — clears all state so new incident loads fresh
  const selectIncident = useCallback((inc: Incident) => {
    setMapReady(false);
    setDataLoading(true); // show loading overlay immediately
    setIncident(inc);
    setMapGeoData(null);
    setCopilot(null);
    setRecommendations([]);
    setAlerts([]);
    setActionState("idle");
    setActionMsg("");
  }, []);

  const markers: MapMarker[] = incident
    ? [
        {
          id: incident.id,
          lat: incident.lat,
          lng: incident.lng,
          type: "incident",
          severity: incident.severity,
          label: incident.id,
          popup: incident.title,
        },
      ]
    : [];

  const detectedMinutesAgo = incident
    ? Math.floor((Date.now() - new Date(incident.detectedAt).getTime()) / 60000)
    : 0;

  const signalActions: SignalAction[] = copilot?.signal_actions ?? [];
  const diversionPlan: DiversionPlan | undefined = copilot?.diversion_plan;
  const overallConfidence = copilot?.overall_confidence ?? 0.91;

  // True if map-data contains at least one diversion route
  const hasAStarRoute = (mapGeoData?.features ?? []).some(
    (f) => f.properties?.feature_type === "diversion_route",
  );

  const channelColor: Record<string, string> = {
    vms: "#3B82F6",
    radio: "#10B981",
    social: "#8B5CF6",
  };
  const channelLabel: Record<string, string> = {
    vms: "VMS Board",
    radio: "Radio Broadcast",
    social: "Social Media",
  };

  const sevColor: Record<string, string> = {
    critical: "#BA1A1A",
    high: "#D97706",
    moderate: "#EAB308",
    low: "#2A6C0D",
  };

  return (
    <main className="h-screen flex overflow-hidden pt-16 bg-surface">
      {/* ── LEFT: Incidents List Sidebar ── */}
      <div className="w-72 shrink-0 flex flex-col border-r border-outline-variant/10 bg-white overflow-y-auto">
        <div className="px-4 py-4 border-b border-outline-variant/10 shrink-0">
          <p className="text-[10px] font-bold uppercase tracking-widest text-on-surface-variant">
            Active Incidents
          </p>
          <p className="text-xs text-on-surface-variant mt-0.5">
            {allIncidents.length} incident{allIncidents.length !== 1 ? "s" : ""}{" "}
            live
          </p>
        </div>
        <div className="flex-1 divide-y divide-outline-variant/10">
          {allIncidents.length === 0 && (
            <div className="p-6 text-center text-xs text-on-surface-variant animate-pulse">
              Loading incidents…
            </div>
          )}
          {allIncidents.map((inc) => {
            const isActive = inc.id === incident?.id;
            return (
              <button
                key={inc.id}
                onClick={() => selectIncident(inc)}
                className={`w-full text-left px-4 py-4 transition-all hover:bg-surface-container-low/50 ${isActive ? "border-l-4 border-primary bg-primary/5" : "border-l-4 border-transparent"}`}
              >
                <div className="flex items-start gap-3">
                  <div
                    className="w-2.5 h-2.5 rounded-full shrink-0 mt-1.5"
                    style={{
                      backgroundColor: sevColor[inc.severity] ?? "#888",
                    }}
                  />
                  <div className="min-w-0">
                    <p
                      className="text-[10px] font-bold uppercase tracking-wide mb-0.5"
                      style={{ color: sevColor[inc.severity] ?? "#888" }}
                    >
                      {inc.severity}
                    </p>
                    <p className="text-xs font-semibold text-on-surface leading-snug line-clamp-2 mb-1">
                      {inc.title}
                    </p>
                    <div className="flex items-center gap-1.5">
                      <span className="material-symbols-outlined text-[11px] text-on-surface-variant">
                        location_on
                      </span>
                      <span className="text-[10px] text-on-surface-variant truncate">
                        {inc.location}
                      </span>
                    </div>
                    <div className="flex items-center gap-1.5 mt-0.5">
                      <span className="text-[10px] text-on-surface-variant font-mono">
                        {inc.lat.toFixed(4)}°N, {inc.lng.toFixed(4)}°E
                      </span>
                    </div>
                    {isActive && (
                      <span className="mt-1.5 inline-flex items-center gap-1 text-[9px] font-bold text-primary">
                        <span className="w-1.5 h-1.5 rounded-full bg-primary animate-pulse" />
                        VIEWING
                      </span>
                    )}
                  </div>
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {/* ── RIGHT: Incident Detail ── */}
      <div className="flex-1 overflow-y-auto p-8 pb-12">
        {/* Field Report Modal */}
        {voiceOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
            <div className="bg-white rounded-2xl shadow-2xl p-8 w-full max-w-md">
              <h2 className="text-lg font-bold text-on-surface mb-1">
                Field Incident Report
              </h2>
              <p className="text-xs text-on-surface-variant mb-5">
                Submit an audio recording or photo from the field. AI will extract incident details automatically.
              </p>

              {/* Tabs */}
              <div className="flex gap-1 mb-6 bg-surface-container rounded-xl p-1">
                <button
                  onClick={() => setReportTab("audio")}
                  className={`flex-1 flex items-center justify-center gap-1.5 py-2 rounded-lg text-xs font-semibold transition-all ${reportTab === "audio" ? "bg-white shadow text-primary" : "text-on-surface-variant hover:text-on-surface"}`}
                >
                  <span className="material-symbols-outlined text-[15px]">mic</span>
                  Audio
                </button>
                <button
                  onClick={() => setReportTab("image")}
                  className={`flex-1 flex items-center justify-center gap-1.5 py-2 rounded-lg text-xs font-semibold transition-all ${reportTab === "image" ? "bg-white shadow text-primary" : "text-on-surface-variant hover:text-on-surface"}`}
                >
                  <span className="material-symbols-outlined text-[15px]">add_a_photo</span>
                  Photo
                </button>
              </div>

              {/* Audio tab */}
              {reportTab === "audio" && (
                <>
                  <p className="text-xs text-on-surface-variant mb-3">
                    Upload an audio recording (mp3 / wav / mp4 / ogg). AssemblyAI transcribes it and Groq extracts incident details.
                  </p>
                  <input
                    type="file"
                    accept="audio/*,video/mp4"
                    onChange={(e) => setVoiceFile(e.target.files?.[0] ?? null)}
                    className="w-full text-sm text-on-surface-variant mb-4 file:mr-3 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-primary/10 file:text-primary"
                  />
                  {voiceMsg && (
                    <p className={`text-xs mb-4 font-medium ${voiceMsg.startsWith("✓") ? "text-primary" : "text-error"}`}>
                      {voiceMsg}
                    </p>
                  )}
                  <div className="flex gap-3">
                    <button
                      onClick={() => { setVoiceOpen(false); setVoiceMsg(""); setVoiceFile(null); }}
                      className="flex-1 py-2.5 rounded-full border border-outline-variant text-sm font-semibold text-on-surface"
                    >
                      Cancel
                    </button>
                    <button
                      onClick={submitVoiceReport}
                      disabled={!voiceFile || voiceLoading}
                      className="flex-1 py-2.5 rounded-full signature-gradient text-white text-sm font-bold disabled:opacity-50"
                    >
                      {voiceLoading ? "Processing…" : "Submit Report"}
                    </button>
                  </div>
                </>
              )}

              {/* Image tab */}
              {reportTab === "image" && (
                <>
                  {/* Drag & drop zone */}
                  <div
                    onDragOver={(e) => { e.preventDefault(); setImageDragOver(true); }}
                    onDragLeave={() => setImageDragOver(false)}
                    onDrop={(e) => {
                      e.preventDefault();
                      setImageDragOver(false);
                      const file = e.dataTransfer.files?.[0];
                      if (file && file.type.startsWith("image/")) handleImageFile(file);
                    }}
                    onClick={() => document.getElementById("image-file-input")?.click()}
                    className={`relative w-full h-40 rounded-xl border-2 border-dashed flex flex-col items-center justify-center cursor-pointer transition-all mb-4 ${imageDragOver ? "border-primary bg-primary/5" : "border-outline-variant hover:border-primary/50 hover:bg-surface-container-low"}`}
                  >
                    {imagePreview ? (
                      <>
                        <img src={imagePreview} alt="Preview" className="absolute inset-0 w-full h-full object-cover rounded-xl opacity-80" />
                        <button
                          onClick={(e) => { e.stopPropagation(); setImageFile(null); setImagePreview(null); }}
                          className="absolute top-2 right-2 z-10 w-6 h-6 rounded-full bg-black/60 text-white flex items-center justify-center hover:bg-black/80 transition-colors"
                        >
                          <span className="material-symbols-outlined text-[13px]">close</span>
                        </button>
                        <div className="relative z-10 bg-black/50 text-white text-xs px-3 py-1 rounded-full">
                          {imageFile?.name}
                        </div>
                      </>
                    ) : (
                      <>
                        <span className="material-symbols-outlined text-[32px] text-on-surface-variant mb-2">add_a_photo</span>
                        <p className="text-xs text-on-surface-variant font-medium">Drop an image or click to browse</p>
                        <p className="text-[10px] text-on-surface-variant/60 mt-0.5">JPG, PNG, WEBP</p>
                      </>
                    )}
                  </div>
                  <input
                    id="image-file-input"
                    type="file"
                    accept="image/*"
                    className="hidden"
                    onChange={(e) => { const f = e.target.files?.[0]; if (f) handleImageFile(f); }}
                  />

                  {/* ViT info badge */}
                  <div className="flex items-center gap-2 mb-4 px-3 py-2 bg-surface-container rounded-lg">
                    <span className="material-symbols-outlined text-[14px] text-primary">psychology</span>
                    <p className="text-[10px] text-on-surface-variant leading-snug">
                      Analyzed by <span className="font-semibold text-on-surface">HuggingFace ViT</span> — classifies the scene and attaches vision context to the active incident.
                    </p>
                  </div>

                  {imageMsg && (
                    <p className={`text-xs mb-4 font-medium ${imageMsg.startsWith("✓") ? "text-primary" : "text-error"}`}>
                      {imageMsg}
                    </p>
                  )}
                  <div className="flex gap-3">
                    <button
                      onClick={() => { setVoiceOpen(false); setImageMsg(""); setImageFile(null); setImagePreview(null); }}
                      className="flex-1 py-2.5 rounded-full border border-outline-variant text-sm font-semibold text-on-surface"
                    >
                      Cancel
                    </button>
                    <button
                      onClick={submitImageReport}
                      disabled={!imageFile || imageLoading || !incident}
                      className="flex-1 py-2.5 rounded-full signature-gradient text-white text-sm font-bold disabled:opacity-50"
                    >
                      {imageLoading ? "Analyzing…" : "Submit Photo"}
                    </button>
                  </div>
                </>
              )}
            </div>
          </div>
        )}

        {/* Page Header */}
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-6 mb-10">
          <div>
            <nav className="flex items-center gap-2 text-xs font-medium text-on-surface-variant mb-3">
              <span className="hover:text-primary cursor-pointer transition-colors">
                Incidents
              </span>
              <span className="material-symbols-outlined text-[14px]">
                chevron_right
              </span>
              <span className="text-primary font-semibold">
                {incident?.id ?? "INC-8821"}
              </span>
              {backendLive && (
                <span className="ml-2 px-2 py-0.5 bg-primary/10 text-primary text-[10px] font-bold rounded-full">
                  BACKEND LIVE
                </span>
              )}
              {hasAStarRoute && (
                <span className="px-2 py-0.5 bg-[#3399ff]/10 text-[#3399ff] text-[10px] font-bold rounded-full">
                  A* ROUTING
                </span>
              )}
              {mapGeoData && !hasAStarRoute && !dataLoading && (
                <span className="px-2 py-0.5 bg-[#D97706]/10 text-[#D97706] text-[10px] font-bold rounded-full">
                  MAPBOX FALLBACK
                </span>
              )}
            </nav>
            <h1 className="text-4xl font-extrabold tracking-tight text-on-surface mb-2">
              {incident?.title ?? "Loading..."}
            </h1>
            <div className="flex flex-wrap items-center gap-4 text-sm">
              <span className="flex items-center gap-1.5 font-semibold text-on-surface">
                <span className="material-symbols-outlined text-sm text-primary">
                  location_on
                </span>
                {incident?.location ?? "—"}
              </span>
              <span className="w-1.5 h-1.5 rounded-full bg-outline-variant"></span>
              <span className="flex items-center gap-1.5 text-on-surface-variant">
                <span className="material-symbols-outlined text-sm">
                  schedule
                </span>
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
            <button
              onClick={() => { setVoiceOpen(true); setReportTab("audio"); setVoiceMsg(""); setImageMsg(""); }}
              className="px-5 py-2.5 rounded-full font-bold text-sm bg-primary/10 text-primary hover:bg-primary/20 transition-colors flex items-center gap-2"
            >
              <span className="material-symbols-outlined text-sm">add_a_photo</span>
              Field Report
            </button>
            <button className="px-6 py-2.5 rounded-full font-bold text-sm text-primary hover:bg-primary/5 transition-colors">
              Export Report
            </button>
          </div>
        </div>

        {/* Bento Grid */}
        <div className="grid grid-cols-12 gap-6">
          {/* LEFT: Details & Signal Actions */}
          <div className="col-span-12 lg:col-span-3 space-y-6">
            <div className="bg-surface-container-lowest p-6 rounded-xl shadow-sm">
              <h3 className="text-xs font-bold uppercase tracking-widest text-primary mb-4">
                Description
              </h3>
              <p className="text-sm text-on-surface leading-relaxed mb-6">
                {copilot?.incident_summary ??
                  incident?.description ??
                  "Loading incident data..."}
              </p>
              <div className="grid grid-cols-2 gap-4">
                <div className="bg-surface p-3 rounded-lg">
                  <p className="text-[10px] text-on-surface-variant uppercase font-bold mb-1">
                    Impact Radius
                  </p>
                  <p className="text-lg font-bold text-on-surface">
                    {incident?.impactRadius ?? "—"}
                  </p>
                </div>
                <div className="bg-surface p-3 rounded-lg">
                  <p className="text-[10px] text-on-surface-variant uppercase font-bold mb-1">
                    Delay Est.
                  </p>
                  <p className="text-lg font-bold text-on-surface">
                    {incident?.delayEstimate ?? "—"}
                  </p>
                </div>
              </div>
            </div>

            {/* Signal Re-timing Actions */}
            {signalActions.length > 0 && (
              <div className="bg-surface-container-lowest p-6 rounded-xl shadow-sm">
                <h3 className="text-xs font-bold uppercase tracking-widest text-[#EAB308] mb-4 flex items-center gap-2">
                  <span
                    className="material-symbols-outlined text-sm"
                    style={{ fontVariationSettings: "'FILL' 1" }}
                  >
                    traffic
                  </span>
                  Signal Re-timing Plan
                </h3>
                <div className="space-y-4">
                  {signalActions.map((sa, i) => (
                    <div
                      key={i}
                      className="p-3 bg-[#EAB308]/5 border border-[#EAB308]/20 rounded-lg"
                    >
                      <p className="text-[10px] font-extrabold text-[#EAB308] uppercase mb-1">
                        {sa.intersection_id}
                      </p>
                      <p className="text-xs font-semibold text-on-surface mb-1">
                        {sa.action}
                      </p>
                      <div className="flex items-center justify-between">
                        <p className="text-[10px] text-on-surface-variant">
                          {sa.expected_impact}
                        </p>
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
              <h3 className="text-xs font-bold uppercase tracking-widest text-primary mb-6">
                Timeline of Events
              </h3>
              <div className="space-y-6 relative before:absolute before:left-[11px] before:top-2 before:bottom-2 before:w-[2px] before:bg-surface-container">
                <div className="relative pl-8">
                  <div className="absolute left-0 top-1 w-[24px] h-[24px] bg-white border-4 border-primary rounded-full z-10"></div>
                  <p className="text-[11px] font-bold text-primary uppercase">
                    Now
                  </p>
                  <p className="text-sm font-semibold text-on-surface">
                    Queue length exceeded 800m
                  </p>
                </div>
                <div className="relative pl-8">
                  <div className="absolute left-[6px] top-1.5 w-3 h-3 bg-surface-container rounded-full z-10"></div>
                  <p className="text-[11px] font-bold text-on-surface-variant uppercase">
                    -8 min
                  </p>
                  <p className="text-sm text-on-surface-variant">
                    Congestion spillback to side streets
                  </p>
                </div>
                <div className="relative pl-8">
                  <div className="absolute left-[6px] top-1.5 w-3 h-3 bg-surface-container rounded-full z-10"></div>
                  <p className="text-[11px] font-bold text-on-surface-variant uppercase">
                    -{detectedMinutesAgo} min
                  </p>
                  <p className="text-sm text-on-surface-variant">
                    Initial surge detected
                  </p>
                </div>
              </div>
            </div>
          </div>

          {/* CENTER: Live Map */}
          <div className="col-span-12 lg:col-span-6 space-y-4">
            <div className="h-[500px] relative rounded-xl overflow-hidden">
              {incident ? (
                <MapboxMap
                  key={incident.id}
                  ref={mapRef}
                  center={[incident.lng, incident.lat]}
                  zoom={15}
                  markers={markers}
                  className="w-full h-full"
                  styleUrl="mapbox://styles/mapbox/light-v11"
                  onMapReady={(h) => {
                    mapRef.current = h;
                    setMapReady(true);
                  }}
                />
              ) : (
                <div className="w-full h-full bg-surface-container-low flex items-center justify-center">
                  <span className="material-symbols-outlined text-4xl text-on-surface-variant animate-pulse">
                    map
                  </span>
                </div>
              )}

              {/* Loading overlay — shown while fetching map-data / recommendations */}
              {dataLoading && (
                <div className="absolute inset-0 z-20 bg-white/60 backdrop-blur-sm flex flex-col items-center justify-center gap-3 rounded-xl">
                  <div className="w-10 h-10 rounded-full border-4 border-primary border-t-transparent animate-spin" />
                  <p className="text-xs font-bold text-primary uppercase tracking-widest">
                    Computing A* Route…
                  </p>
                  <p className="text-[10px] text-on-surface-variant">
                    Fetching map data &amp; recommendations
                  </p>
                </div>
              )}

              <div className="absolute top-4 left-4 flex flex-col gap-2 z-10">
                <div className="bg-white/90 backdrop-blur-md p-3 rounded-lg shadow-xl">
                  <p className="text-[10px] font-bold uppercase text-on-surface-variant mb-2">
                    Map Layers
                  </p>
                  <div className="flex gap-2">
                    <button
                      onClick={() =>
                        mapRef.current?.setLayerVisibility(
                          "diversion-route-0",
                          true,
                        )
                      }
                      className="w-8 h-8 rounded bg-primary text-white flex items-center justify-center shadow-sm"
                      title="Show diversion route"
                    >
                      <span className="material-symbols-outlined text-sm">
                        alt_route
                      </span>
                    </button>
                    <button
                      onClick={() =>
                        mapRef.current?.setLayerVisibility(
                          "signal-circles",
                          true,
                        )
                      }
                      className="w-8 h-8 rounded bg-[#EAB308] text-white flex items-center justify-center border border-outline-variant/20"
                      title="Show signal actions"
                    >
                      <span className="material-symbols-outlined text-sm">
                        traffic
                      </span>
                    </button>
                    <button className="w-8 h-8 rounded bg-white text-on-surface flex items-center justify-center border border-outline-variant/20">
                      <span className="material-symbols-outlined text-sm">
                        sensors
                      </span>
                    </button>
                  </div>
                </div>
              </div>

              {/* A* route status pill — shown when data loaded but no valid route yet */}
              {mapGeoData && !hasAStarRoute && !dataLoading && (
                <div className="absolute top-4 right-4 z-10 flex items-center gap-2 bg-[#D97706]/10 border border-[#D97706]/30 text-[#D97706] px-3 py-1.5 rounded-full text-[10px] font-bold backdrop-blur-sm">
                  <span className="material-symbols-outlined text-[13px]">
                    pending
                  </span>
                  Using Mapbox road routing (OSM graph unavailable)
                </div>
              )}

              <div className="absolute bottom-4 left-4 right-4 z-10 bg-white/90 backdrop-blur-md p-4 rounded-xl shadow-2xl flex items-center justify-between border border-white">
                <div className="flex items-center gap-4">
                  <div className="w-12 h-12 rounded-lg bg-error-container/20 flex items-center justify-center">
                    <span
                      className="material-symbols-outlined text-error"
                      style={{ fontVariationSettings: "'FILL' 1" }}
                    >
                      emergency_share
                    </span>
                  </div>
                  <div>
                    <p className="text-xs font-bold text-on-surface">
                      {incident?.location ?? "Loading..."}
                    </p>
                    <p className="text-xs text-on-surface-variant">
                      Status:{" "}
                      <span
                        className={`font-bold ${incident?.status === "active" ? "text-error" : "text-primary"}`}
                      >
                        {incident?.status === "active"
                          ? "Critical Delay"
                          : (incident?.status ?? "—")}
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
                  <span
                    className="w-3 h-3 rounded-full"
                    style={{ backgroundColor: ROUTE_COLORS[activeRouteIdx] }}
                  ></span>
                  <h4 className="text-sm font-bold text-on-surface">
                    Diversion Route — Activation Sequence
                  </h4>
                  <span className="ml-auto text-[10px] font-bold px-2 py-0.5 bg-primary/10 text-primary rounded-full">
                    {Math.round((diversionPlan.confidence ?? 0) * 100)}%
                    confidence
                  </span>
                </div>
                <p className="text-xs text-on-surface-variant mb-4">
                  {diversionPlan.route_description}
                </p>
                <div className="grid grid-cols-3 gap-3 mb-4">
                  <div className="bg-surface p-3 rounded-lg">
                    <p className="text-[10px] text-on-surface-variant uppercase font-bold mb-1">
                      Extra Time
                    </p>
                    <p className="text-base font-extrabold text-on-surface">
                      +{diversionPlan.estimated_extra_minutes}m
                    </p>
                  </div>
                  <div className="bg-surface p-3 rounded-lg">
                    <p className="text-[10px] text-on-surface-variant uppercase font-bold mb-1">
                      Traffic Shift
                    </p>
                    <p className="text-base font-extrabold text-primary">
                      {diversionPlan.traffic_redistribution_pct}%
                    </p>
                  </div>
                  <div className="bg-surface p-3 rounded-lg">
                    <p className="text-[10px] text-on-surface-variant uppercase font-bold mb-1">
                      Road Nodes
                    </p>
                    <p className="text-base font-extrabold text-on-surface">
                      {mapGeoData?.features.find(
                        (f) => f.properties?.feature_type === "diversion_route",
                      )?.properties?.coordinate_count ??
                        diversionPlan.waypoints.length}
                    </p>
                  </div>
                </div>
                {/* Activation sequence */}
                <div className="flex gap-2 overflow-x-auto pb-1">
                  {diversionPlan.waypoints.map((wp, i) => (
                    <div
                      key={i}
                      className="flex items-center gap-1 flex-shrink-0"
                    >
                      <div className="flex flex-col items-center">
                        <div
                          className="w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-extrabold text-white"
                          style={{
                            backgroundColor: ROUTE_COLORS[activeRouteIdx],
                          }}
                        >
                          {i + 1}
                        </div>
                        <p className="text-[9px] text-on-surface-variant mt-1 text-center max-w-[60px]">
                          {wp.name}
                        </p>
                      </div>
                      {i < diversionPlan.waypoints.length - 1 && (
                        <span className="material-symbols-outlined text-sm text-on-surface-variant mt-[-12px]">
                          arrow_forward
                        </span>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Alerts Panel */}
            {alerts.length > 0 && (
              <div className="bg-surface-container-lowest p-5 rounded-xl shadow-sm">
                <h4 className="text-xs font-bold uppercase tracking-widest text-on-surface-variant mb-4 flex items-center gap-2">
                  <span className="material-symbols-outlined text-sm">
                    campaign
                  </span>
                  Public Alerts
                </h4>
                <div className="space-y-3">
                  {alerts.map((alert) => (
                    <div
                      key={alert.id}
                      className="p-3 rounded-lg border"
                      style={{
                        borderColor: `${channelColor[alert.channel] ?? "#888"}33`,
                      }}
                    >
                      <div className="flex items-center justify-between mb-2">
                        <span
                          className="text-[10px] font-bold px-2 py-0.5 rounded-full text-white"
                          style={{
                            backgroundColor:
                              channelColor[alert.channel] ?? "#888",
                          }}
                        >
                          {channelLabel[alert.channel] ??
                            alert.channel.toUpperCase()}
                        </span>
                        {alert.status === "published" ? (
                          <span className="text-[10px] font-bold text-primary flex items-center gap-1">
                            <span className="material-symbols-outlined text-[12px]">
                              check_circle
                            </span>
                            Published
                          </span>
                        ) : (
                          <button
                            onClick={() => publishAlert(alert.id)}
                            className="text-[10px] font-bold px-3 py-1 rounded-full bg-primary text-white hover:bg-primary/80 transition-colors"
                          >
                            Publish
                          </button>
                        )}
                      </div>
                      <p className="text-xs text-on-surface leading-relaxed">
                        {alert.draft_text}
                      </p>
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
                  <span
                    className="material-symbols-outlined text-primary text-sm"
                    style={{ fontVariationSettings: "'FILL' 1" }}
                  >
                    smart_toy
                  </span>
                </div>
                <h3 className="text-sm font-bold text-on-surface">
                  TrafficCopilot AI
                </h3>
              </div>
              <div className="space-y-4">
                {signalActions.slice(0, 2).map((sa, i) => (
                  <div
                    key={i}
                    className="p-4 bg-surface rounded-xl border-l-4 border-primary"
                  >
                    <p className="text-[10px] font-bold text-primary uppercase mb-1">
                      Signal Strategy
                    </p>
                    <p className="text-sm font-semibold text-on-surface mb-2">
                      {sa.intersection_id}
                    </p>
                    <p className="text-xs text-on-surface-variant mb-3">
                      {sa.action}
                    </p>
                    <div className="flex items-center gap-2">
                      <span className="text-[10px] bg-primary-fixed text-on-primary-fixed px-2 py-0.5 rounded font-bold">
                        {Math.round(sa.confidence * 100)}% conf.
                      </span>
                      <span className="text-[10px] text-on-surface-variant">
                        {sa.expected_impact}
                      </span>
                    </div>
                  </div>
                ))}

                {diversionPlan && (
                  <div className="p-4 bg-surface rounded-xl border-l-4 border-[#3B82F6]">
                    <p className="text-[10px] font-bold text-[#3B82F6] uppercase mb-1">
                      Diversion Route
                    </p>
                    <p className="text-sm font-semibold text-on-surface mb-2">
                      {diversionPlan.route_description.slice(0, 60)}
                      {diversionPlan.route_description.length > 60 ? "…" : ""}
                    </p>
                    <div className="flex items-center gap-2">
                      <span className="text-[10px] bg-secondary-container text-on-secondary-container px-2 py-0.5 rounded font-bold">
                        Active
                      </span>
                      <span className="text-[10px] text-on-surface-variant">
                        -{diversionPlan.traffic_redistribution_pct}% Vol.
                      </span>
                    </div>
                  </div>
                )}

                {!signalActions.length && !diversionPlan && (
                  <div className="p-4 bg-surface rounded-xl border-l-4 border-primary">
                    <p className="text-[10px] font-bold text-primary uppercase mb-1">
                      Status
                    </p>
                    <p className="text-sm text-on-surface-variant">
                      Waiting for AI recommendations…
                    </p>
                  </div>
                )}

                <div className="pt-4 border-t border-surface-container">
                  <div className="flex justify-between items-end mb-2">
                    <p className="text-[10px] font-bold text-on-surface-variant uppercase">
                      Overall Confidence
                    </p>
                    <p className="text-lg font-bold text-primary">
                      {Math.round(overallConfidence * 100)}%
                    </p>
                  </div>
                  <div className="w-full h-1.5 bg-surface-container rounded-full overflow-hidden">
                    <div
                      className="h-full bg-primary rounded-full"
                      style={{
                        width: `${Math.round(overallConfidence * 100)}%`,
                      }}
                    ></div>
                  </div>
                  {copilot?.review_required && (
                    <p className="text-[10px] text-[#D97706] mt-2 flex items-center gap-1">
                      <span className="material-symbols-outlined text-[12px]">
                        warning
                      </span>
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
                <div
                  className={`mt-8 p-4 rounded-xl text-sm font-medium text-center ${actionState === "approved" ? "bg-primary-container/20 text-primary" : "bg-error-container/20 text-error"}`}
                >
                  <span
                    className="material-symbols-outlined text-base align-middle mr-1"
                    style={{ fontVariationSettings: "'FILL' 1" }}
                  >
                    {actionState === "approved" ? "check_circle" : "cancel"}
                  </span>
                  {actionMsg}
                  <button
                    onClick={() => {
                      setActionState("idle");
                      setActionMsg("");
                    }}
                    className="block text-xs mt-2 text-on-surface-variant underline mx-auto"
                  >
                    Reset
                  </button>
                </div>
              )}
            </div>

            {/* Affected Assets */}
            <div className="bg-surface-container-lowest p-5 rounded-xl shadow-sm">
              <h4 className="text-[10px] font-bold uppercase text-on-surface-variant mb-4">
                Affected Assets
              </h4>
              <div className="space-y-3">
                {signalActions.length > 0
                  ? signalActions.map((sa) => (
                      <div
                        key={sa.intersection_id}
                        className="flex items-center justify-between"
                      >
                        <div className="flex items-center gap-2">
                          <span className="material-symbols-outlined text-lg text-[#EAB308]">
                            traffic
                          </span>
                          <span className="text-xs font-medium text-on-surface">
                            {sa.intersection_id}
                          </span>
                        </div>
                        <span className="w-2 h-2 rounded-full bg-[#EAB308]"></span>
                      </div>
                    ))
                  : [
                      { icon: "traffic", label: "Signals — pending" },
                      { icon: "screenshot_monitor", label: "VMS — pending" },
                      { icon: "camera_outdoor", label: "CCTV — pending" },
                    ].map(({ icon, label }) => (
                      <div
                        key={label}
                        className="flex items-center justify-between"
                      >
                        <div className="flex items-center gap-2">
                          <span className="material-symbols-outlined text-lg text-on-surface-variant">
                            {icon}
                          </span>
                          <span className="text-xs font-medium text-on-surface">
                            {label}
                          </span>
                        </div>
                        <span className="w-2 h-2 rounded-full bg-surface-container"></span>
                      </div>
                    ))}
              </div>
            </div>

            {/* Narrative */}
            {copilot?.narrative && (
              <div className="bg-primary/5 p-5 rounded-xl">
                <p className="text-[10px] font-bold uppercase text-primary mb-2">
                  TrafficCopilot Narrative
                </p>
                <p className="text-xs text-on-surface leading-relaxed">
                  {copilot.narrative}
                </p>
              </div>
            )}

            {/* IRIS Assistant — incident-scoped chat */}
            <div className="bg-surface-container-lowest rounded-xl shadow-sm overflow-hidden">
              <div className="flex items-center gap-2 px-4 py-3 border-b border-surface-container">
                <div className="w-6 h-6 rounded-full signature-gradient flex items-center justify-center">
                  <span
                    className="material-symbols-outlined text-[13px] text-white"
                    style={{ fontVariationSettings: "'FILL' 1" }}
                  >
                    smart_toy
                  </span>
                </div>
                <p className="text-[11px] font-bold text-on-surface">
                  IRIS Assistant
                </p>
                <span className="ml-auto text-[9px] font-bold px-1.5 py-0.5 bg-primary/10 text-primary rounded-full uppercase">
                  {incident?.corridor_id ?? "Incident"}
                </span>
              </div>

              {/* Messages */}
              <div className="h-48 overflow-y-auto p-3 space-y-2">
                {chatMessages.length === 0 && (
                  <p className="text-[11px] text-on-surface-variant text-center mt-6">
                    Ask anything about this incident…
                  </p>
                )}
                {chatMessages.map((m, i) => (
                  <div
                    key={i}
                    className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}
                  >
                    <div
                      className={`max-w-[85%] px-3 py-2 rounded-xl text-[11px] leading-relaxed ${
                        m.role === "user"
                          ? "bg-primary text-white rounded-br-none"
                          : "bg-surface-container text-on-surface rounded-bl-none"
                      }`}
                    >
                      {m.content}
                    </div>
                  </div>
                ))}
                <div ref={chatEndRef} />
              </div>

              {/* Input */}
              <div className="px-3 py-2 border-t border-surface-container flex gap-2">
                <input
                  value={chatInput}
                  onChange={(e) => setChatInput(e.target.value)}
                  onKeyDown={(e) =>
                    e.key === "Enter" && !e.shiftKey && sendChat()
                  }
                  placeholder="Ask about diversion, signals…"
                  disabled={chatLoading || !incident}
                  className="flex-1 text-[11px] bg-surface-container rounded-full px-3 py-1.5 outline-none placeholder:text-on-surface-variant disabled:opacity-50"
                />
                <button
                  onClick={sendChat}
                  disabled={chatLoading || !incident || !chatInput.trim()}
                  className="w-7 h-7 rounded-full signature-gradient flex items-center justify-center disabled:opacity-40 flex-shrink-0"
                >
                  <span className="material-symbols-outlined text-[14px] text-white">
                    send
                  </span>
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
      {/* end right detail panel */}
    </main>
  );
}
