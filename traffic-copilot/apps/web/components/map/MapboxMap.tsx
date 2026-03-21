"use client";

import { useEffect, useRef } from "react";

export interface MapMarker {
  id: string;
  lat: number;
  lng: number;
  type: "incident" | "camera" | "signal";
  severity?: "critical" | "high" | "moderate" | "low";
  label?: string;
  popup?: string;
}

interface MapboxMapProps {
  center?: [number, number];
  zoom?: number;
  markers?: MapMarker[];
  className?: string;
  style?: string;
}

export default function MapboxMap({
  center = [-73.9857, 40.7484],
  zoom = 13,
  markers = [],
  className = "",
  style = "mapbox://styles/mapbox/light-v11",
}: MapboxMapProps) {
  const mapContainer = useRef<HTMLDivElement>(null);
  const mapRef = useRef<unknown>(null);

  useEffect(() => {
    if (mapRef.current || !mapContainer.current) return;

    const token = process.env.NEXT_PUBLIC_MAPBOX_TOKEN;
    if (!token) return;

    let mapboxgl: typeof import("mapbox-gl");
    let map: import("mapbox-gl").Map;

    import("mapbox-gl").then((mgl) => {
      mapboxgl = mgl.default as unknown as typeof import("mapbox-gl");
      (mapboxgl as unknown as { accessToken: string }).accessToken = token;

      map = new (mapboxgl as unknown as { Map: new (opts: unknown) => import("mapbox-gl").Map }).Map({
        container: mapContainer.current!,
        style,
        center,
        zoom,
        attributionControl: false,
      });

      mapRef.current = map;

      map.on("load", () => {
        markers.forEach((marker) => {
          const el = document.createElement("div");
          el.className = "mapbox-marker";

          const colors: Record<string, string> = {
            critical: "#BA1A1A",
            high: "#D97706",
            moderate: "#EAB308",
            low: "#2A6C0D",
          };

          if (marker.type === "incident") {
            el.style.cssText = `
              width: 36px; height: 36px;
              background: ${colors[marker.severity || "moderate"]};
              border: 3px solid white;
              border-radius: 50%;
              display: flex; align-items: center; justify-content: center;
              cursor: pointer;
              box-shadow: 0 4px 12px rgba(0,0,0,0.3);
              animation: pulse-marker 2s infinite;
            `;
            el.innerHTML = `<span style="color:white;font-family:'Material Symbols Outlined';font-size:16px;font-variation-settings:'FILL' 1">warning</span>`;
          } else if (marker.type === "camera") {
            el.style.cssText = `
              width: 32px; height: 32px;
              background: #2A6C0D;
              border: 2px solid white;
              border-radius: 50%;
              display: flex; align-items: center; justify-content: center;
              cursor: pointer;
              box-shadow: 0 2px 8px rgba(0,0,0,0.2);
            `;
            el.innerHTML = `<span style="color:white;font-family:'Material Symbols Outlined';font-size:14px;font-variation-settings:'FILL' 1">videocam</span>`;
          }

          const popup = marker.popup
            ? new (mapboxgl as unknown as { Popup: new (opts: unknown) => import("mapbox-gl").Popup }).Popup({ offset: 25, closeButton: false }).setHTML(`
                <div style="font-family:sans-serif;padding:8px;min-width:160px">
                  <p style="font-weight:700;font-size:12px;margin:0 0 4px">${marker.label || marker.id}</p>
                  <p style="font-size:11px;color:#666;margin:0">${marker.popup}</p>
                </div>
              `)
            : undefined;

          const m = new (mapboxgl as unknown as { Marker: new (opts: unknown) => import("mapbox-gl").Marker }).Marker({ element: el })
            .setLngLat([marker.lng, marker.lat]);

          if (popup) m.setPopup(popup);
          m.addTo(map);
        });

        // Add pulsing CSS
        if (!document.getElementById("mapbox-marker-styles")) {
          const style = document.createElement("style");
          style.id = "mapbox-marker-styles";
          style.textContent = `
            @keyframes pulse-marker {
              0% { box-shadow: 0 0 0 0 rgba(186,26,26,0.4); }
              70% { box-shadow: 0 0 0 12px rgba(186,26,26,0); }
              100% { box-shadow: 0 0 0 0 rgba(186,26,26,0); }
            }
          `;
          document.head.appendChild(style);
        }
      });
    });

    return () => {
      if (map) map.remove();
      mapRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div
      ref={mapContainer}
      className={className}
      style={{ width: "100%", height: "100%" }}
    />
  );
}
