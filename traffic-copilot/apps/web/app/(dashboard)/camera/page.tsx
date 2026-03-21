"use client";

import { useState, useEffect } from "react";

interface Camera {
  id: string;
  label: string;
  location: string;
  status: "live" | "offline" | "recording";
  img: string;
  fps: number;
  bitrate: string;
  detections: number;
  temp: number;
  uptime: string;
  lat: number;
  lng: number;
}

const CAMERAS: Camera[] = [
  {
    id: "CAM-042",
    label: "5th Ave & Broadway",
    location: "Central District",
    status: "live",
    img: "https://lh3.googleusercontent.com/aida-public/AB6AXuDbuoLeNYnnqiAmzOxu8enM5UXNHhQe4EWbzM5FPoQ4jc3MpxRMdTLxoy4HUohnCwqtmoTM3UuFnHIjQZ1pgYkic9IHboqicYJcDD7wTmPhgRq5eP1f4ZPTPSAuinfDeIv1JFAs2WYCrsdCmbkipgUcLO7EJ7tTRUjErLW9aZYWr8GQEIMOBFVJ5sDKAwrz-EghzFxdF7wICxIgW0tXS5RG7emhROOwvJJX5qFCEdBcRKg9k8aOB6scC49Vq0fVovBTaxqnxqCW_1nh",
    fps: 30,
    bitrate: "12.4 MB/s",
    detections: 14,
    temp: 42,
    uptime: "142d 12h",
    lat: 40.7529,
    lng: -73.9773,
  },
  {
    id: "CAM-018",
    label: "West End Terminal",
    location: "West District",
    status: "live",
    img: "https://lh3.googleusercontent.com/aida-public/AB6AXuBjrcWz1ciK19wjz9z9v4nIDZzJM4ED-US14E2LXyaqRsViP8YFm6kfHoHwTQZn_qvzV9VhEiGizU5xRzC3tXaC_43Y2O_WlFodK1XzE-ydKEVj82gSZmdZEBJ5ClHkJ-IBpC5sMZaabZ7P9G8KzKRoRAxpFJyQmL7Xate_XxQoGlxWOjLStCJavLt5XFptHxZWii87GixVMq3GJcP0t3EXjjBX7Qa86JjvWE_Kt9hZCoPK2ghxZIKFVYuBXe_r2_8mTyom00AofP6C",
    fps: 24,
    bitrate: "9.1 MB/s",
    detections: 7,
    temp: 38,
    uptime: "98d 4h",
    lat: 40.7440,
    lng: -74.0021,
  },
  {
    id: "CAM-031",
    label: "Northern Gate Overpass",
    location: "North Gateway",
    status: "recording",
    img: "https://lh3.googleusercontent.com/aida-public/AB6AXuDbuoLeNYnnqiAmzOxu8enM5UXNHhQe4EWbzM5FPoQ4jc3MpxRMdTLxoy4HUohnCwqtmoTM3UuFnHIjQZ1pgYkic9IHboqicYJcDD7wTmPhgRq5eP1f4ZPTPSAuinfDeIv1JFAs2WYCrsdCmbkipgUcLO7EJ7tTRUjErLW9aZYWr8GQEIMOBFVJ5sDKAwrz-EghzFxdF7wICxIgW0tXS5RG7emhROOwvJJX5qFCEdBcRKg9k8aOB6scC49Vq0fVovBTaxqnxqCW_1nh",
    fps: 30,
    bitrate: "14.2 MB/s",
    detections: 22,
    temp: 45,
    uptime: "60d 18h",
    lat: 40.7690,
    lng: -73.9640,
  },
  {
    id: "CAM-057",
    label: "South Parkway Bridge",
    location: "South District",
    status: "offline",
    img: "https://lh3.googleusercontent.com/aida-public/AB6AXuBjrcWz1ciK19wjz9z9v4nIDZzJM4ED-US14E2LXyaqRsViP8YFm6kfHoHwTQZn_qvzV9VhEiGizU5xRzC3tXaC_43Y2O_WlFodK1XzE-ydKEVj82gSZmdZEBJ5ClHkJ-IBpC5sMZaabZ7P9G8KzKRoRAxpFJyQmL7Xate_XxQoGlxWOjLStCJavLt5XFptHxZWii87GixVMq3GJcP0t3EXjjBX7Qa86JjvWE_Kt9hZCoPK2ghxZIKFVYuBXe_r2_8mTyom00AofP6C",
    fps: 0,
    bitrate: "0 MB/s",
    detections: 0,
    temp: 0,
    uptime: "Offline",
    lat: 40.7380,
    lng: -73.9900,
  },
];

function now() { return new Date().toUTCString().split(" ").slice(1, 5).join(" "); }

export default function CameraFeedsPage() {
  const [selectedId, setSelectedId] = useState("CAM-042");
  const [timestamp, setTimestamp] = useState(now());
  const [detections, setDetections] = useState(14);

  const cam = CAMERAS.find((c) => c.id === selectedId)!;

  useEffect(() => {
    const iv = setInterval(() => {
      setTimestamp(now());
      setDetections((d) => Math.max(0, d + Math.floor(Math.random() * 5 - 2)));
    }, 3000);
    return () => clearInterval(iv);
  }, []);

  useEffect(() => {
    setDetections(cam.detections);
  }, [selectedId, cam.detections]);

  const statusColors: Record<string, string> = {
    live: "bg-red-500",
    recording: "bg-[#EAB308]",
    offline: "bg-outline-variant",
  };

  return (
    <main className="min-h-screen bg-surface p-8 pt-24">
      <div className="flex justify-between items-end mb-8">
        <div>
          <h2 className="text-3xl font-bold tracking-tight text-on-surface">Camera Feeds</h2>
          <p className="text-on-surface-variant mt-1">Real-time surveillance monitoring for Central District traffic flow.</p>
        </div>
        <div className="flex gap-2">
          <button className="px-4 py-2 text-sm font-semibold text-primary hover:bg-primary/5 rounded-full flex items-center gap-2 transition-colors">
            <span className="material-symbols-outlined text-sm">download</span> Export
          </button>
          <button className="px-5 py-2 text-sm font-semibold text-white signature-gradient rounded-full shadow-md hover:brightness-110">
            Add Camera
          </button>
        </div>
      </div>

      <div className="grid grid-cols-12 gap-6">
        {/* Main Feed */}
        <div className="col-span-12 lg:col-span-9 space-y-6">
          {/* Primary Video */}
          <div className="relative rounded-2xl overflow-hidden bg-slate-900 aspect-video">
            {cam.status === "offline" ? (
              <div className="w-full h-full flex flex-col items-center justify-center gap-4 bg-surface-container-low">
                <span className="material-symbols-outlined text-6xl text-on-surface-variant/40">videocam_off</span>
                <p className="font-bold text-on-surface-variant">Camera Offline</p>
                <p className="text-sm text-on-surface-variant/70">Connection lost · Technician dispatched</p>
              </div>
            ) : (
              <img src={cam.img} alt={cam.label} className="w-full h-full object-cover opacity-90" />
            )}

            {cam.status !== "offline" && (
              <>
                {/* Top overlay */}
                <div className="absolute top-4 left-4 flex items-center gap-3">
                  <span className={`w-2.5 h-2.5 rounded-full ${statusColors[cam.status]} animate-pulse`}></span>
                  <span className="text-xs font-bold text-white uppercase tracking-tighter drop-shadow">
                    {cam.status === "live" ? "LIVE" : "REC"} · {cam.id}
                  </span>
                </div>

                {/* Top right: timestamp */}
                <div className="absolute top-4 right-4 bg-black/50 backdrop-blur-sm px-3 py-1.5 rounded-lg">
                  <p className="text-[10px] font-bold text-white/90 font-mono">{timestamp}</p>
                </div>

                {/* Bottom overlay */}
                <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/80 to-transparent p-6">
                  <div className="flex items-end justify-between">
                    <div>
                      <h3 className="text-lg font-bold text-white">{cam.label}</h3>
                      <p className="text-sm text-white/70">{cam.location} · {cam.fps} FPS · {cam.bitrate}</p>
                    </div>
                    <div className="flex gap-2">
                      <button className="p-2 bg-white/20 backdrop-blur-sm rounded-lg hover:bg-white/30 transition-colors text-white">
                        <span className="material-symbols-outlined text-sm">fullscreen</span>
                      </button>
                      <button className="p-2 bg-white/20 backdrop-blur-sm rounded-lg hover:bg-white/30 transition-colors text-white">
                        <span className="material-symbols-outlined text-sm">fiber_manual_record</span>
                      </button>
                      <button className="p-2 bg-white/20 backdrop-blur-sm rounded-lg hover:bg-white/30 transition-colors text-white">
                        <span className="material-symbols-outlined text-sm">photo_camera</span>
                      </button>
                    </div>
                  </div>
                </div>
              </>
            )}
          </div>

          {/* Telemetry Cards */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="bg-surface-container-lowest p-5 rounded-xl shadow-sm">
              <div className="flex items-center gap-3 mb-3">
                <div className="p-2 bg-primary-container/20 rounded-lg">
                  <span className="material-symbols-outlined text-primary text-lg">directions_car</span>
                </div>
                <div>
                  <p className="text-[10px] font-bold text-on-surface-variant uppercase">Object Detection</p>
                  <p className="text-2xl font-bold text-on-surface">{detections}</p>
                </div>
              </div>
              <p className="text-xs text-on-surface-variant">Vehicles in frame right now</p>
              <div className="mt-3 h-1.5 bg-surface-container rounded-full overflow-hidden">
                <div className="h-full bg-primary rounded-full transition-all duration-500" style={{ width: `${Math.min(100, (detections / 30) * 100)}%` }}></div>
              </div>
            </div>

            <div className="bg-surface-container-lowest p-5 rounded-xl shadow-sm">
              <div className="flex items-center gap-3 mb-3">
                <div className="p-2 bg-secondary-container rounded-lg">
                  <span className="material-symbols-outlined text-on-secondary-container text-lg">thermostat</span>
                </div>
                <div>
                  <p className="text-[10px] font-bold text-on-surface-variant uppercase">Hardware Health</p>
                  <p className="text-2xl font-bold text-on-surface">{cam.temp > 0 ? `${cam.temp}°C` : "—"}</p>
                </div>
              </div>
              <p className="text-xs text-on-surface-variant">Operating {cam.temp < 50 ? "within" : "above"} normal range</p>
              <div className="mt-3 h-1.5 bg-surface-container rounded-full overflow-hidden">
                <div className={`h-full rounded-full ${cam.temp > 50 ? "bg-error" : "bg-primary"}`} style={{ width: cam.temp > 0 ? `${(cam.temp / 80) * 100}%` : "0%" }}></div>
              </div>
            </div>

            <div className="bg-surface-container-lowest p-5 rounded-xl shadow-sm">
              <div className="flex items-center gap-3 mb-3">
                <div className="p-2 bg-tertiary-container/20 rounded-lg">
                  <span className="material-symbols-outlined text-tertiary text-lg">timer</span>
                </div>
                <div>
                  <p className="text-[10px] font-bold text-on-surface-variant uppercase">Uptime</p>
                  <p className="text-2xl font-bold text-on-surface">{cam.uptime}</p>
                </div>
              </div>
              <p className="text-xs text-on-surface-variant">Continuous operation</p>
              <div className="mt-3 flex gap-1">
                {[...Array(7)].map((_, i) => (
                  <div key={i} className={`h-1.5 flex-1 rounded-full ${cam.status !== "offline" ? "bg-primary" : "bg-surface-container-high"}`}></div>
                ))}
              </div>
            </div>
          </div>

          {/* All camera grid thumbnails */}
          <div>
            <h4 className="font-bold text-sm text-on-surface mb-4">All Camera Feeds</h4>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {CAMERAS.map((c) => (
                <button
                  key={c.id}
                  onClick={() => setSelectedId(c.id)}
                  className={`relative rounded-xl overflow-hidden aspect-video group border-2 transition-all ${selectedId === c.id ? "border-primary shadow-lg" : "border-transparent hover:border-primary/30"}`}
                >
                  <img src={c.img} alt={c.label} className={`w-full h-full object-cover transition-all ${c.status === "offline" ? "grayscale opacity-50" : "group-hover:scale-105"}`} />
                  <div className="absolute inset-0 bg-gradient-to-t from-black/60 to-transparent"></div>
                  <div className="absolute top-2 left-2 flex items-center gap-1">
                    <span className={`w-1.5 h-1.5 rounded-full ${statusColors[c.status]} ${c.status !== "offline" ? "animate-pulse" : ""}`}></span>
                  </div>
                  <div className="absolute bottom-2 left-2">
                    <p className="text-[9px] font-bold text-white">{c.id}</p>
                    <p className="text-[8px] text-white/70">{c.location}</p>
                  </div>
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Sidebar */}
        <div className="col-span-12 lg:col-span-3 space-y-6">
          {/* Selected Camera Info */}
          <div className="bg-surface-container-lowest rounded-xl p-5 shadow-sm">
            <h4 className="font-bold text-sm text-on-surface mb-4">Camera Details</h4>
            <div className="space-y-3">
              {[
                { label: "Camera ID", value: cam.id },
                { label: "Location", value: cam.label },
                { label: "District", value: cam.location },
                { label: "Status", value: cam.status.toUpperCase() },
                { label: "Frame Rate", value: `${cam.fps} FPS` },
                { label: "Bitrate", value: cam.bitrate },
                { label: "Uptime", value: cam.uptime },
              ].map(({ label, value }) => (
                <div key={label} className="flex justify-between text-xs">
                  <span className="text-on-surface-variant font-bold uppercase">{label}</span>
                  <span className={`font-semibold ${label === "Status" ? (cam.status === "offline" ? "text-error" : "text-primary") : "text-on-surface"}`}>{value}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Camera Selector */}
          <div className="bg-surface-container-lowest rounded-xl p-5 shadow-sm">
            <h4 className="font-bold text-sm text-on-surface mb-4">Switch Camera</h4>
            <div className="space-y-2">
              {CAMERAS.map((c) => (
                <button
                  key={c.id}
                  onClick={() => setSelectedId(c.id)}
                  className={`w-full flex items-center gap-3 p-3 rounded-lg transition-all text-left ${selectedId === c.id ? "bg-primary-container/20 border-l-4 border-primary" : "hover:bg-surface-container-low"}`}
                >
                  <span className={`w-2 h-2 rounded-full ${statusColors[c.status]} shrink-0`}></span>
                  <div className="flex-1 min-w-0">
                    <p className={`text-xs font-bold truncate ${selectedId === c.id ? "text-primary" : "text-on-surface"}`}>{c.id}</p>
                    <p className="text-[10px] text-on-surface-variant truncate">{c.label}</p>
                  </div>
                  {c.status === "live" && <span className="text-[8px] font-bold text-error uppercase shrink-0">LIVE</span>}
                </button>
              ))}
            </div>
          </div>

          {/* IRIS Insight */}
          <div className="bg-surface-container-lowest rounded-xl p-5 shadow-sm border-b-4 border-secondary-container">
            <div className="flex items-center gap-2 mb-3">
              <div className="w-6 h-6 rounded bg-secondary-container flex items-center justify-center">
                <span className="material-symbols-outlined text-[14px] text-primary" style={{ fontVariationSettings: "'FILL' 1" }}>smart_toy</span>
              </div>
              <span className="text-xs font-bold text-on-surface">IRIS Camera Insight</span>
            </div>
            <p className="text-xs text-on-surface-variant leading-relaxed">
              {cam.status === "offline"
                ? "Camera CAM-057 is offline. Backup telemetry active. Tech dispatch scheduled for 09:30."
                : `Detecting ${detections} vehicles in ${cam.label}. Flow rate ${detections > 15 ? "elevated — monitor closely" : "normal"}. No incidents flagged.`}
            </p>
          </div>
        </div>
      </div>
    </main>
  );
}
