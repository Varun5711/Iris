"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import dynamic from "next/dynamic";
import { useSettings } from "@/ui_lib/settings-context";
import type { MapboxHandle, MapMarker } from "@/components/map/MapboxMap";
import type { BackendIncident, BackendRecommendation } from "@/ui_lib/backend";

const MapboxMap = dynamic(() => import("@/components/map/MapboxMap"), { ssr: false });

const MAPBOX_TOKEN = process.env.NEXT_PUBLIC_MAPBOX_TOKEN ?? "";

// Route palette — different color per diversion route
const ROUTE_COLORS = ["#3B82F6", "#10B981", "#8B5CF6", "#F59E0B", "#EC4899"];

const CAMERA_MARKERS: MapMarker[] = [
  { id: "CAM-042", lat: 40.7529, lng: -73.9773, type: "camera", label: "CAM-042", popup: "5th Ave & Broadway — Normal Flow" },
  { id: "CAM-018", lat: 40.7440, lng: -74.0021, type: "camera", label: "CAM-018", popup: "West End Terminal — Live" },
  { id: "CAM-031", lat: 40.7690, lng: -73.9640, type: "camera", label: "CAM-031", popup: "Northern Gate — Live" },
];

const STYLE_URLS = {
  map: "mapbox://styles/mapbox/light-v11",
  satellite: "mapbox://styles/mapbox/satellite-streets-v12",
  dark: "mapbox://styles/mapbox/dark-v11",
};

interface SearchResult { place_name: string; center: [number, number]; }
interface RouteOption { idx: number; color: string; label: string; extra_minutes: number; redistribution: number; waypoints: { name: string; lat: number; lng: number }[]; selected: boolean; }

export default function MapPage() {
  const { settings } = useSettings();
  const mapHandleRef = useRef<MapboxHandle | null>(null);
  const [mapStyle, setMapStyle] = useState<"map" | "satellite" | "dark">("map");
  const [layers, setLayers] = useState(settings.mapLayers);
  const [incidents, setIncidents] = useState<BackendIncident[]>([]);
  const [activeIncident, setActiveIncident] = useState<BackendIncident | null>(null);
  const [routeOptions, setRouteOptions] = useState<RouteOption[]>([]);
  const [searchValue, setSearchValue] = useState("");
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [searchOpen, setSearchOpen] = useState(false);
  const [showFilters, setShowFilters] = useState(false);
  const [mapReady, setMapReady] = useState(false);
  const [backendOnline, setBackendOnline] = useState(false);
  const [loading, setLoading] = useState(false);

  // Sync layer toggles from settings
  useEffect(() => { setLayers(settings.mapLayers); }, [settings.mapLayers]);

  // Apply layer visibility to map when toggle changes
  useEffect(() => {
    if (!mapReady || !mapHandleRef.current) return;
    const h = mapHandleRef.current;
    h.setLayerVisibility("affected-segments", layers.affectedSegments);
    h.setLayerVisibility("diversion-route-0", layers.diversionRoutes);
    h.setLayerVisibility("diversion-route-1", layers.diversionRoutes);
    h.setLayerVisibility("diversion-route-2", layers.diversionRoutes);
    h.setLayerVisibility("signal-circles", layers.signals);
    h.setLayerVisibility("signal-icons", layers.signals);
  }, [layers, mapReady]);

  // Load incidents from backend/API
  const loadIncidents = useCallback(async () => {
    try {
      const res = await fetch("/api/incidents");
      const data = await res.json();
      setIncidents(data);
      // Check if backend is actually online
      const backendCheck = await fetch(`${process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000"}/health`, { signal: AbortSignal.timeout(2000) });
      setBackendOnline(backendCheck.ok);
    } catch { setBackendOnline(false); }
  }, []);

  useEffect(() => {
    loadIncidents();
    const iv = setInterval(loadIncidents, 30000);
    return () => clearInterval(iv);
  }, [loadIncidents]);

  // Load map GeoJSON from backend for a specific incident
  // Uses /incidents/{id}/map-data which returns real NetworkX/OSM road-following coordinates
  const loadIncidentMapData = useCallback(async (incident: BackendIncident) => {
    if (!mapHandleRef.current) return;
    const h = mapHandleRef.current;
    setLoading(true);

    try {
      const BACKEND = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";

      // 1. Load GeoJSON FeatureCollection — contains real OSM road-following routes
      const res = await fetch(`${BACKEND}/incidents/${incident.id}/map-data`, { signal: AbortSignal.timeout(8000) });
      if (res.ok) {
        const geojson: GeoJSON.FeatureCollection = await res.json();

        // Split features by type
        const affectedFeatures = geojson.features.filter((f) => f.properties?.feature_type === "affected_segment");
        const diversionFeatures = geojson.features.filter((f) => f.properties?.feature_type === "diversion_route");
        const signalFeatures = geojson.features.filter((f) => f.properties?.feature_type === "signal_action");

        // Affected segments — orange thick line (congested roads)
        if (affectedFeatures.length > 0) {
          h.addGeoJSONLayer({
            id: "affected-segments",
            sourceId: "affected-segments-src",
            data: { type: "FeatureCollection", features: affectedFeatures },
            layerType: "line",
            paint: { "line-color": "#FF6600", "line-width": 6, "line-opacity": 0.85 },
            layout: { "line-cap": "round", "line-join": "round" },
          });
        }

        // Diversion routes — real OSM NetworkX Dijkstra road-following coordinates (50–130 nodes)
        // Rendered per-route with different colors for selection
        diversionFeatures.forEach((feature, i) => {
          const color = ROUTE_COLORS[i % ROUTE_COLORS.length];
          const layerId = `diversion-route-${i}`;
          h.addGeoJSONLayer({
            id: layerId,
            sourceId: `${layerId}-src`,
            data: { type: "FeatureCollection", features: [feature] },
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

        // Signal action circles — yellow traffic-light icons at intersections
        if (signalFeatures.length > 0) {
          h.addGeoJSONLayer({
            id: "signal-circles",
            sourceId: "signal-circles-src",
            data: { type: "FeatureCollection", features: signalFeatures },
            layerType: "circle",
            paint: { "circle-color": "#EAB308", "circle-radius": 10, "circle-stroke-color": "#fff", "circle-stroke-width": 2.5, "circle-opacity": 0.95 },
          });
        }

        // Build route options UI from diversion features (using their metadata, not waypoints)
        const routes: RouteOption[] = diversionFeatures.slice(0, 5).map((f, i) => ({
          idx: i,
          color: ROUTE_COLORS[i % ROUTE_COLORS.length],
          label: (f.properties?.description as string) || (f.properties?.route_description as string) || `Route ${i + 1} via ${(f.properties?.road_names as string[])?.[0] ?? "alternate road"}`,
          extra_minutes: (f.properties?.estimated_extra_minutes as number) ?? 5 + i * 2,
          redistribution: (f.properties?.traffic_redistribution_pct as number) ?? 30 - i * 5,
          waypoints: [],
          selected: i === 0,
        }));
        setRouteOptions(routes);
        setBackendOnline(true);
      }

      // 2. Fetch recommendations for signal action info (no route rendering — routes come from /map-data)
      const recRes = await fetch(`${BACKEND}/recommendations/${incident.id}`, { signal: AbortSignal.timeout(6000) });
      if (recRes.ok) {
        const recs: BackendRecommendation[] = await recRes.json();
        const signalActions = recs.flatMap((r) => r.copilot_response?.signal_actions ?? []);
        if (signalActions.length > 0) {
          console.log(`[map] ${signalActions.length} signal actions from backend`);
        }
      }
    } catch (e) {
      console.warn("[map] backend load error:", e);
    } finally {
      setLoading(false);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // When active incident changes, load its map data
  useEffect(() => {
    if (activeIncident) {
      loadIncidentMapData(activeIncident);
      if (activeIncident.location_lat && activeIncident.location_lon) {
        mapHandleRef.current?.flyTo([activeIncident.location_lon, activeIncident.location_lat], 15);
      }
    }
  }, [activeIncident, loadIncidentMapData]);

  // Auto-select critical incident on load
  useEffect(() => {
    if (incidents.length > 0 && !activeIncident) {
      const critical = incidents.find((i) => (i as unknown as Record<string,string>).severity === "critical") ?? incidents[0];
      setActiveIncident(critical);
    }
  }, [incidents, activeIncident]);

  // Map ready callback
  const handleMapReady = useCallback((handle: MapboxHandle) => {
    mapHandleRef.current = handle;
    setMapReady(true);
  }, []);

  // Search with Mapbox Geocoding API
  const handleSearch = async (q: string) => {
    setSearchValue(q);
    if (q.length < 3) { setSearchResults([]); setSearchOpen(false); return; }
    try {
      const res = await fetch(
        `https://api.mapbox.com/geocoding/v5/mapbox.places/${encodeURIComponent(q)}.json?access_token=${MAPBOX_TOKEN}&limit=5`
      );
      const data = await res.json();
      const results: SearchResult[] = (data.features ?? []).map((f: Record<string, unknown>) => ({
        place_name: f.place_name as string,
        center: f.center as [number, number],
      }));
      setSearchResults(results);
      setSearchOpen(results.length > 0);
    } catch {}
  };

  const selectSearchResult = (r: SearchResult) => {
    mapHandleRef.current?.flyTo(r.center, 15);
    setSearchValue(r.place_name);
    setSearchOpen(false);
    setSearchResults([]);
  };

  const switchStyle = (s: "map" | "satellite" | "dark") => {
    setMapStyle(s);
    mapHandleRef.current?.setMapStyle(STYLE_URLS[s]);
  };

  const toggleLayer = (key: keyof typeof layers) => {
    const next = { ...layers, [key]: !layers[key] };
    setLayers(next);
    const layerMap: Record<string, string[]> = {
      affectedSegments: ["affected-segments"],
      diversionRoutes: ["diversion-route-0", "diversion-route-1", "diversion-route-2", "diversion-route-3"],
      signals: ["signal-circles", "signal-icons"],
    };
    (layerMap[key] ?? []).forEach((id) =>
      mapHandleRef.current?.setLayerVisibility(id, !layers[key])
    );
  };

  const selectRoute = (idx: number) => {
    setRouteOptions((p) => p.map((r, i) => ({ ...r, selected: i === idx })));
    // Highlight selected route by changing opacity; others dim
    ROUTE_COLORS.forEach((_, i) => {
      const visible = i === idx || true; // keep all visible, selection shown by UI
      mapHandleRef.current?.setLayerVisibility(`diversion-route-${i}`, visible);
    });
    // Fly to active incident location
    if (activeIncident?.location_lat && activeIncident?.location_lon) {
      mapHandleRef.current?.flyTo([activeIncident.location_lon, activeIncident.location_lat], 14);
    }
  };

  // Build markers based on settings
  const markers: MapMarker[] = [
    ...(layers.cameras && settings.dataSources.cctv ? CAMERA_MARKERS : []),
    ...(layers.incidents
      ? incidents.map((i) => ({
          id: String(i.id),
          lat: (i as unknown as Record<string,number>).lat ?? (i.location_lat ?? 40.7589),
          lng: (i as unknown as Record<string,number>).lng ?? (i.location_lon ?? -73.9851),
          type: "incident" as const,
          severity: i.severity === "medium" ? "moderate" as const : i.severity as "critical" | "high" | "low",
          label: String(i.id).slice(0, 8).toUpperCase(),
          popup: (i as unknown as Record<string,string>).title ?? i.description ?? i.severity,
        }))
      : []),
  ];

  const LAYER_CONTROLS = [
    { key: "traffic" as const, icon: "traffic", label: "Traffic Flow" },
    { key: "incidents" as const, icon: "warning", label: "Incidents" },
    { key: "signals" as const, icon: "traffic_lights" as string, label: "Signal Actions" },
    { key: "cameras" as const, icon: "videocam", label: "CCTV Cameras" },
    { key: "affectedSegments" as const, icon: "route", label: "Affected Roads" },
    { key: "diversionRoutes" as const, icon: "alt_route", label: "Diversion Routes" },
  ];

  return (
    <main className="h-screen relative overflow-hidden pt-16">
      {/* Full-screen Mapbox */}
      <div className="absolute inset-0 top-16">
        <MapboxMap
          ref={mapHandleRef}
          center={[-73.9857, 40.7484]}
          zoom={13}
          styleUrl={STYLE_URLS[mapStyle]}
          markers={markers}
          className="w-full h-full"
          onMapReady={handleMapReady}
        />
      </div>

      {/* ── Floating Search Bar ── */}
      <div className="absolute top-20 left-6 z-20" style={{ width: "360px" }}>
        <div className="relative">
          <div className="bg-white rounded-xl shadow-2xl p-2 flex items-center gap-2">
            <span className="material-symbols-outlined text-on-surface-variant ml-2">search</span>
            <input
              className="flex-1 bg-transparent border-none focus:ring-0 text-sm py-2 text-on-surface placeholder:text-on-surface-variant/50 outline-none"
              placeholder="Search addresses, intersections..."
              value={searchValue}
              onChange={(e) => handleSearch(e.target.value)}
              onFocus={() => searchResults.length > 0 && setSearchOpen(true)}
            />
            {searchValue && (
              <button onClick={() => { setSearchValue(""); setSearchResults([]); setSearchOpen(false); }} className="p-1 text-on-surface-variant hover:text-primary">
                <span className="material-symbols-outlined text-sm">close</span>
              </button>
            )}
            <button onClick={() => setShowFilters((p) => !p)} className={`p-2 rounded-lg transition-colors ${showFilters ? "bg-primary text-white" : "hover:bg-surface-container-low text-primary"}`}>
              <span className="material-symbols-outlined">tune</span>
            </button>
          </div>

          {/* Search dropdown */}
          {searchOpen && searchResults.length > 0 && (
            <div className="absolute top-full left-0 right-0 mt-1 bg-white rounded-xl shadow-2xl overflow-hidden z-30">
              {searchResults.map((r, i) => (
                <button key={i} onClick={() => selectSearchResult(r)} className="w-full text-left px-4 py-3 hover:bg-surface-container-low transition-colors flex items-center gap-3 border-b border-outline-variant/10 last:border-0">
                  <span className="material-symbols-outlined text-primary text-sm">location_on</span>
                  <span className="text-xs text-on-surface leading-tight">{r.place_name}</span>
                </button>
              ))}
            </div>
          )}

          {/* Filter panel */}
          {showFilters && (
            <div className="absolute top-full left-0 right-0 mt-1 bg-white rounded-xl shadow-2xl p-4 z-30">
              <p className="text-[10px] font-bold text-on-surface-variant uppercase tracking-widest mb-3">Filter by Severity</p>
              <div className="flex flex-wrap gap-2">
                {["Critical", "High", "Moderate", "Low"].map((s) => (
                  <button key={s} className="px-3 py-1 text-xs font-bold rounded-full bg-surface-container-low text-on-surface hover:bg-primary hover:text-white transition-colors">
                    {s}
                  </button>
                ))}
              </div>
              <p className="text-[10px] font-bold text-on-surface-variant uppercase tracking-widest mb-3 mt-4">Incident Status</p>
              <div className="flex flex-wrap gap-2">
                {["Active", "Monitoring", "Resolved"].map((s) => (
                  <button key={s} className="px-3 py-1 text-xs font-bold rounded-full bg-surface-container-low text-on-surface hover:bg-primary hover:text-white transition-colors">
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* ── Right panel: Controls + Layers ── */}
      <div className="absolute top-20 right-6 z-20 flex flex-col gap-3">
        {/* Zoom + Location */}
        <div className="bg-white rounded-xl shadow-2xl p-1 flex flex-col items-center">
          <button onClick={() => mapHandleRef.current?.zoomIn()} className="p-3 hover:bg-surface-container-low rounded-lg transition-colors text-on-surface-variant" title="Zoom in">
            <span className="material-symbols-outlined">add</span>
          </button>
          <div className="w-8 h-px bg-outline-variant/30"></div>
          <button onClick={() => mapHandleRef.current?.zoomOut()} className="p-3 hover:bg-surface-container-low rounded-lg transition-colors text-on-surface-variant" title="Zoom out">
            <span className="material-symbols-outlined">remove</span>
          </button>
          <div className="w-8 h-px bg-outline-variant/30"></div>
          <button onClick={() => mapHandleRef.current?.flyTo([-73.9857, 40.7484], 13)} className="p-3 hover:bg-surface-container-low rounded-lg transition-colors text-on-surface-variant" title="Reset view">
            <span className="material-symbols-outlined">my_location</span>
          </button>
        </div>

        {/* Layer Toggles */}
        <div className="bg-white rounded-xl shadow-2xl p-2 space-y-1 w-56">
          <h3 className="text-[10px] font-bold text-on-surface-variant uppercase tracking-widest px-2 py-1">Map Layers</h3>
          {LAYER_CONTROLS.map(({ key, icon, label }) => (
            <button
              key={key}
              onClick={() => toggleLayer(key)}
              className={`w-full flex items-center justify-between px-2 py-2 rounded-lg text-sm transition-colors ${layers[key] ? "text-primary bg-primary/5" : "text-on-surface-variant hover:bg-surface-container-low"}`}
            >
              <span className="flex items-center gap-2">
                <span className="material-symbols-outlined text-lg">{icon}</span>
                <span className="text-xs font-medium">{label}</span>
              </span>
              <div className={`w-8 h-4 rounded-full relative transition-colors ${layers[key] ? "bg-primary" : "bg-outline-variant"}`}>
                <div className={`absolute top-0.5 w-3 h-3 bg-white rounded-full transition-transform ${layers[key] ? "right-0.5" : "left-0.5"}`}></div>
              </div>
            </button>
          ))}
        </div>

        {/* Severity Legend */}
        <div className="bg-white rounded-xl shadow-2xl p-4 w-56">
          <h3 className="text-[10px] font-bold text-on-surface-variant uppercase tracking-widest mb-3">Layer Legend</h3>
          <div className="space-y-2">
            {[
              { color: "#BA1A1A", label: "Critical Incident" },
              { color: "#D97706", label: "High Incident" },
              { color: "#FF6600", label: "Affected Road" },
              ...ROUTE_COLORS.slice(0, 3).map((c, i) => ({ color: c, label: `Diversion Route ${i + 1}` })),
              { color: "#EAB308", label: "Signal Action" },
              { color: "#2A6C0D", label: "Camera" },
            ].map(({ color, label }) => (
              <div key={label} className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full flex-shrink-0" style={{ background: color }}></div>
                <span className="text-[10px] font-medium text-on-surface-variant">{label}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* ── Active Incident Pill ── */}
      <div className="absolute top-20 left-1/2 -translate-x-1/2 z-20">
        <div className="bg-white rounded-full shadow-2xl px-5 py-2 flex items-center gap-3">
          <span className={`w-2.5 h-2.5 rounded-full ${incidents.length > 0 ? "bg-error animate-pulse" : "bg-primary"}`}></span>
          <span className="text-xs font-bold text-on-surface">
            {incidents.filter((i) => (i as unknown as Record<string,string>).status === "active").length} Active Incidents
          </span>
          <span className="w-px h-4 bg-outline-variant/30"></span>
          <span className={`text-[10px] font-bold ${backendOnline ? "text-primary" : "text-on-surface-variant"}`}>
            {backendOnline ? "● Backend Live" : "○ Mock Data"}
          </span>
          {loading && <span className="material-symbols-outlined text-primary text-sm animate-spin">sync</span>}
        </div>
      </div>

      {/* ── Route Selection Panel (bottom center) ── */}
      {routeOptions.length > 0 && (
        <div className="absolute bottom-24 left-1/2 -translate-x-1/2 z-20 w-[600px] max-w-[90vw]">
          <div className="bg-white rounded-2xl shadow-2xl p-4">
            <p className="text-[10px] font-bold text-on-surface-variant uppercase tracking-widest mb-3">
              Diversion Route Options — Select to Activate
            </p>
            <div className="flex gap-2 overflow-x-auto pb-1">
              {routeOptions.map((r, i) => (
                <button
                  key={i}
                  onClick={() => selectRoute(i)}
                  className={`flex-shrink-0 px-3 py-2 rounded-xl border-2 transition-all text-left min-w-[140px] ${r.selected ? "border-primary bg-primary/5 shadow-sm" : "border-outline-variant/20 hover:border-primary/40"}`}
                >
                  <div className="flex items-center gap-2 mb-1">
                    <div className="w-3 h-3 rounded-full" style={{ background: r.color }}></div>
                    <span className="text-[10px] font-bold text-on-surface-variant">ROUTE {i + 1}</span>
                  </div>
                  <p className="text-xs font-semibold text-on-surface leading-tight mb-1 truncate">{r.label}</p>
                  <p className="text-[9px] text-on-surface-variant">+{r.extra_minutes.toFixed(1)} min · {r.redistribution.toFixed(0)}% shift</p>
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* ── Active Incident Details (bottom-left) ── */}
      {activeIncident && (
        <div className="absolute bottom-20 left-6 z-20">
          <div className="bg-white rounded-xl shadow-2xl p-4 w-72">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-error animate-pulse"></span>
                <span className="text-xs font-bold text-on-surface">Active Incident</span>
              </div>
              <button onClick={() => setActiveIncident(null)} className="text-on-surface-variant hover:text-primary">
                <span className="material-symbols-outlined text-sm">close</span>
              </button>
            </div>
            <p className="text-[11px] text-on-surface-variant leading-relaxed mb-2">
              {(activeIncident as unknown as Record<string,string>).description ?? "Incident under monitoring"}
            </p>
            <div className="flex gap-2">
              <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${activeIncident.severity === "critical" ? "bg-error-container text-on-error-container" : "bg-primary/10 text-primary"}`}>
                {activeIncident.severity?.toUpperCase()}
              </span>
              <span className="text-[10px] text-on-surface-variant px-2 py-0.5 bg-surface-container rounded-full">
                {activeIncident.corridor_id ?? "Unknown Corridor"}
              </span>
            </div>
          </div>
        </div>
      )}

      {/* ── Signal Actions Panel (from recommendations) ── */}
      {routeOptions.length === 0 && incidents.length > 0 && (
        <SignalActionsPanel incidentId={String((activeIncident ?? incidents[0]).id)} backendOnline={backendOnline} />
      )}

      {/* ── Map style toggle ── */}
      <div className="absolute bottom-6 right-6 z-20">
        <div className="bg-white rounded-xl shadow-2xl p-1 flex gap-1">
          {(["map", "satellite", "dark"] as const).map((s) => (
            <button
              key={s}
              onClick={() => switchStyle(s)}
              className={`px-3 py-2 rounded-lg text-xs font-bold transition-all capitalize ${mapStyle === s ? "bg-primary text-white" : "text-on-surface-variant hover:bg-surface-container-low"}`}
            >
              {s}
            </button>
          ))}
        </div>
      </div>
    </main>
  );
}

// Separate component so it can fetch recommendations independently
function SignalActionsPanel({ incidentId, backendOnline }: { incidentId: string; backendOnline: boolean }) {
  const [actions, setActions] = useState<Array<{ intersection_id: string; action: string; expected_impact: string; confidence: number }>>([]);

  useEffect(() => {
    if (!backendOnline || !incidentId) return;
    fetch(`${process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000"}/recommendations/${incidentId}`, { signal: AbortSignal.timeout(8000) })
      .then((r) => r.json())
      .then((recs) => {
        const sa = recs.flatMap((r: BackendRecommendation) => r.copilot_response?.signal_actions ?? []);
        setActions(sa.slice(0, 4));
      })
      .catch(() => {});
  }, [incidentId, backendOnline]);

  if (actions.length === 0) return null;

  return (
    <div className="absolute bottom-6 left-1/2 -translate-x-1/2 z-20 w-[480px] max-w-[90vw]">
      <div className="bg-white rounded-2xl shadow-2xl p-4">
        <p className="text-[10px] font-bold text-on-surface-variant uppercase tracking-widest mb-3">
          Signal Re-timing Recommendations
        </p>
        <div className="space-y-2">
          {actions.map((a, i) => (
            <div key={i} className="flex items-start gap-3 p-2 bg-surface-container-low rounded-lg">
              <div className="w-6 h-6 rounded-full bg-[#EAB308] flex items-center justify-center shrink-0 mt-0.5">
                <span className="material-symbols-outlined text-white text-xs" style={{ fontVariationSettings: "'FILL' 1" }}>traffic</span>
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-xs font-bold text-on-surface truncate">{a.intersection_id}</p>
                <p className="text-[10px] text-on-surface-variant">{a.action}</p>
                <p className="text-[9px] text-primary mt-0.5">{a.expected_impact} · {Math.round(a.confidence * 100)}% confidence</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
