"use client";

import { useEffect, useState } from "react";
import dynamic from "next/dynamic";
import type { Incident } from "@/lib/types";
import type { MapMarker } from "@/components/map/MapboxMap";

const MapboxMap = dynamic(() => import("@/components/map/MapboxMap"), { ssr: false });

const CAMERA_MARKERS: MapMarker[] = [
  { id: "CAM-042", lat: 40.7529, lng: -73.9773, type: "camera", label: "CAM-042", popup: "5th Ave & Broadway — Normal Flow" },
  { id: "CAM-018", lat: 40.7440, lng: -74.0021, type: "camera", label: "CAM-018", popup: "West End Terminal — Live" },
  { id: "CAM-031", lat: 40.7690, lng: -73.9640, type: "camera", label: "CAM-031", popup: "Northern Gate — Live" },
];

export default function MapPage() {
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [layers, setLayers] = useState({ traffic: true, incidents: true, signals: false, cameras: true });
  const [mapStyle, setMapStyle] = useState<"map" | "satellite">("map");

  useEffect(() => {
    fetch("/api/incidents")
      .then((r) => r.json())
      .then(setIncidents)
      .catch(() => {});

    const iv = setInterval(() => {
      fetch("/api/incidents")
        .then((r) => r.json())
        .then(setIncidents)
        .catch(() => {});
    }, 30000);
    return () => clearInterval(iv);
  }, []);

  const markers: MapMarker[] = [
    ...(layers.cameras ? CAMERA_MARKERS : []),
    ...(layers.incidents
      ? incidents.filter((i) => i.status !== "resolved").map((i) => ({
          id: i.id,
          lat: i.lat,
          lng: i.lng,
          type: "incident" as const,
          severity: i.severity,
          label: i.id,
          popup: `${i.title} — ${i.severity.toUpperCase()}`,
        }))
      : []),
  ];

  const mapboxStyle =
    mapStyle === "satellite"
      ? "mapbox://styles/mapbox/satellite-streets-v12"
      : "mapbox://styles/mapbox/light-v11";

  const toggleLayer = (key: keyof typeof layers) => {
    setLayers((p) => ({ ...p, [key]: !p[key] }));
  };

  return (
    <main className="h-screen relative bg-surface-container-low pt-16 overflow-hidden">
      {/* Full screen map */}
      <div className="absolute inset-0 top-16">
        <MapboxMap
          center={[-73.9857, 40.7484]}
          zoom={13}
          markers={markers}
          className="w-full h-full"
          style={mapboxStyle}
        />
      </div>

      {/* Floating Search Bar */}
      <div className="absolute top-20 left-6 w-96 z-10">
        <div className="bg-surface-container-lowest rounded-xl shadow-2xl p-2 flex items-center gap-2">
          <span className="material-symbols-outlined text-outline ml-2">search</span>
          <input
            className="flex-1 bg-transparent border-none focus:ring-0 text-sm py-2 text-on-surface placeholder:text-on-surface-variant/50 outline-none"
            placeholder="Search segments or addresses..."
            type="text"
          />
          <button className="p-2 hover:bg-surface-container-low rounded-lg transition-colors">
            <span className="material-symbols-outlined text-primary">tune</span>
          </button>
        </div>
      </div>

      {/* Right Side Overlays */}
      <div className="absolute top-20 right-6 flex flex-col gap-4 z-10">
        {/* Navigation Controls */}
        <div className="bg-surface-container-lowest rounded-xl shadow-2xl p-1 flex flex-col items-center">
          <button className="p-3 hover:bg-surface-container-low rounded-lg transition-colors text-on-surface-variant">
            <span className="material-symbols-outlined">add</span>
          </button>
          <div className="w-8 h-[1px] bg-outline-variant/30"></div>
          <button className="p-3 hover:bg-surface-container-low rounded-lg transition-colors text-on-surface-variant">
            <span className="material-symbols-outlined">remove</span>
          </button>
          <div className="w-8 h-[1px] bg-outline-variant/30"></div>
          <button className="p-3 hover:bg-surface-container-low rounded-lg transition-colors text-on-surface-variant">
            <span className="material-symbols-outlined">my_location</span>
          </button>
        </div>

        {/* Layer Toggles */}
        <div className="bg-surface-container-lowest rounded-xl shadow-2xl p-2 space-y-1 w-52">
          <h3 className="text-[10px] font-bold text-on-surface-variant uppercase tracking-widest px-2 py-1">Map Layers</h3>
          {(
            [
              { key: "traffic", icon: "traffic", label: "Traffic Flow" },
              { key: "incidents", icon: "warning", label: "Incidents" },
              { key: "signals", icon: "traffic", label: "Signal Status" },
              { key: "cameras", icon: "videocam", label: "CCTV Cameras" },
            ] as const
          ).map(({ key, icon, label }) => (
            <button
              key={key}
              onClick={() => toggleLayer(key)}
              className={`w-full flex items-center justify-between px-2 py-2 rounded-lg text-sm transition-colors ${layers[key] ? "text-primary bg-primary-container/10" : "text-on-surface-variant hover:bg-surface-container-low"}`}
            >
              <span className="flex items-center gap-2">
                <span className="material-symbols-outlined text-lg">{icon}</span> {label}
              </span>
              <div className={`w-8 h-4 rounded-full relative transition-colors ${layers[key] ? "bg-primary" : "bg-outline-variant"}`}>
                <div className={`absolute top-0.5 w-3 h-3 bg-white rounded-full transition-transform ${layers[key] ? "right-0.5" : "left-0.5"}`}></div>
              </div>
            </button>
          ))}
        </div>

        {/* Legend */}
        <div className="bg-surface-container-lowest rounded-xl shadow-2xl p-4 w-52">
          <h3 className="text-[10px] font-bold text-on-surface-variant uppercase tracking-widest mb-3">Incident Severity</h3>
          <div className="space-y-2">
            <div className="flex items-center gap-3">
              <div className="w-3 h-3 rounded-full bg-error flex-shrink-0"></div>
              <span className="text-[11px] font-semibold text-on-surface-variant">Critical</span>
            </div>
            <div className="flex items-center gap-3">
              <div className="w-3 h-3 rounded-full bg-[#D97706] flex-shrink-0"></div>
              <span className="text-[11px] font-semibold text-on-surface-variant">High</span>
            </div>
            <div className="flex items-center gap-3">
              <div className="w-3 h-3 rounded-full bg-[#EAB308] flex-shrink-0"></div>
              <span className="text-[11px] font-semibold text-on-surface-variant">Moderate</span>
            </div>
            <div className="flex items-center gap-3">
              <div className="w-3 h-3 rounded-full bg-primary flex-shrink-0"></div>
              <span className="text-[11px] font-semibold text-on-surface-variant">Camera / Signal</span>
            </div>
          </div>
        </div>
      </div>

      {/* Live Incidents Count */}
      <div className="absolute top-20 left-1/2 -translate-x-1/2 z-10">
        <div className="bg-surface-container-lowest rounded-full shadow-2xl px-4 py-2 flex items-center gap-3">
          <span className="w-2 h-2 rounded-full bg-error animate-pulse"></span>
          <span className="text-xs font-bold text-on-surface">
            {incidents.filter((i) => i.status === "active").length} Active Incidents
          </span>
          <span className="text-on-surface-variant/30">|</span>
          <span className="text-xs text-on-surface-variant">{incidents.length} Total</span>
        </div>
      </div>

      {/* Map/Satellite Toggle */}
      <div className="absolute bottom-6 right-6 z-10">
        <div className="bg-surface-container-lowest rounded-xl shadow-2xl p-1 flex gap-1">
          <button
            onClick={() => setMapStyle("map")}
            className={`px-3 py-2 rounded-lg text-xs font-bold transition-all ${mapStyle === "map" ? "bg-primary text-white" : "text-on-surface-variant hover:bg-surface-container-low"}`}
          >
            Map
          </button>
          <button
            onClick={() => setMapStyle("satellite")}
            className={`px-3 py-2 rounded-lg text-xs font-bold transition-all ${mapStyle === "satellite" ? "bg-primary text-white" : "text-on-surface-variant hover:bg-surface-container-low"}`}
          >
            Satellite
          </button>
        </div>
      </div>

      {/* AI Insight Bottom Left */}
      <div className="absolute bottom-6 left-6 z-10">
        <div className="bg-surface-container-lowest rounded-xl shadow-2xl p-4 w-72 border-b-4 border-secondary-container">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-8 h-8 rounded-full bg-secondary-container flex items-center justify-center text-primary">
              <span className="material-symbols-outlined text-lg">smart_toy</span>
            </div>
            <div>
              <h4 className="text-xs font-bold text-on-surface">IRIS Intelligence</h4>
              <p className="text-[10px] text-on-surface-variant">Active Monitoring</p>
            </div>
          </div>
          <p className="text-[11px] leading-relaxed text-on-surface-variant bg-surface-container-low p-2 rounded-lg italic">
            &ldquo;Detected slowdown on I-90 corridor. {incidents.filter((i) => i.status === "active").length > 0 ? `${incidents.filter((i) => i.status === "active").length} active incident(s) currently on map.` : "All routes flowing normally."}&rdquo;
          </p>
        </div>
      </div>
    </main>
  );
}
