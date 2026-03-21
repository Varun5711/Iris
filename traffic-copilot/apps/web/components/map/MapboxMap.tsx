"use client";

import { useEffect, useRef, useImperativeHandle, forwardRef } from "react";

export interface MapMarker {
  id: string;
  lat: number;
  lng: number;
  type: "incident" | "camera" | "signal" | "diversion";
  severity?: "critical" | "high" | "moderate" | "low";
  label?: string;
  popup?: string;
}

export interface GeoJSONLayerDef {
  id: string;
  sourceId: string;
  data: GeoJSON.FeatureCollection | GeoJSON.Feature;
  layerType: "line" | "circle" | "fill";
  paint?: Record<string, unknown>;
  layout?: Record<string, unknown>;
}

export interface MapboxHandle {
  zoomIn(): void;
  zoomOut(): void;
  flyTo(center: [number, number], zoom?: number): void;
  setLayerVisibility(layerId: string, visible: boolean): void;
  setMapStyle(styleUrl: string): void;
  addGeoJSONLayer(def: GeoJSONLayerDef): void;
  removeLayerAndSource(id: string): void;
  getMap(): unknown;
}

interface Props {
  center?: [number, number];
  zoom?: number;
  styleUrl?: string;
  markers?: MapMarker[];
  className?: string;
  onMapReady?: (handle: MapboxHandle) => void;
}

const SEVERITY_COLORS: Record<string, string> = {
  critical: "#BA1A1A",
  high: "#D97706",
  moderate: "#EAB308",
  low: "#2A6C0D",
};

// Store pending layers to add after style reloads
type PendingLayer = {
  def: GeoJSONLayerDef;
  markers: MapMarker[];
  customLayerIds: string[];
};

const MapboxMap = forwardRef<MapboxHandle, Props>(function MapboxMap(
  { center = [-73.9857, 40.7484], zoom = 13, styleUrl = "mapbox://styles/mapbox/light-v11", markers = [], className = "", onMapReady },
  ref
) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<import("mapbox-gl").Map | null>(null);
  const handleRef = useRef<MapboxHandle | null>(null);
  const pendingRef = useRef<PendingLayer>({ def: null as unknown as GeoJSONLayerDef, markers: [], customLayerIds: [] });
  const layerDefsRef = useRef<Map<string, GeoJSONLayerDef>>(new Map());
  const markerInstancesRef = useRef<import("mapbox-gl").Marker[]>([]);

  useImperativeHandle(ref, () => ({
    zoomIn: () => mapRef.current?.zoomIn(),
    zoomOut: () => mapRef.current?.zoomOut(),
    flyTo: (c, z) => mapRef.current?.flyTo({ center: c, zoom: z ?? mapRef.current.getZoom(), essential: true }),
    setLayerVisibility: (layerId, visible) => {
      const m = mapRef.current;
      if (!m) return;
      try {
        if (m.getLayer(layerId)) {
          m.setLayoutProperty(layerId, "visibility", visible ? "visible" : "none");
        }
      } catch {}
    },
    setMapStyle: (s) => {
      const m = mapRef.current;
      if (!m) return;
      // Save current layer defs before style change
      const savedDefs = new Map(layerDefsRef.current);
      const savedMarkers = [...markers];
      m.setStyle(s);
      m.once("style.load", () => {
        // Re-add all custom layers after style reload
        savedDefs.forEach((def) => {
          addLayerToMap(m, def);
        });
        addMarkersToMap(m, savedMarkers);
      });
    },
    addGeoJSONLayer: (def) => {
      layerDefsRef.current.set(def.id, def);
      if (mapRef.current?.isStyleLoaded()) {
        addLayerToMap(mapRef.current, def);
      }
    },
    removeLayerAndSource: (id) => {
      layerDefsRef.current.delete(id);
      const m = mapRef.current;
      if (!m) return;
      try { if (m.getLayer(id)) m.removeLayer(id); } catch {}
      try { if (m.getSource(id + "-src") || m.getSource(id)) m.removeSource(id + "-src"); } catch {}
      try { if (m.getSource(id)) m.removeSource(id); } catch {}
    },
    getMap: () => mapRef.current,
  }));

  function addLayerToMap(m: import("mapbox-gl").Map, def: GeoJSONLayerDef) {
    const srcId = def.sourceId || def.id + "-src";
    try {
      if (!m.getSource(srcId)) {
        m.addSource(srcId, { type: "geojson", data: def.data as GeoJSON.GeoJSON });
      } else {
        (m.getSource(srcId) as import("mapbox-gl").GeoJSONSource).setData(def.data as GeoJSON.GeoJSON);
        return; // layer already exists, just updated data
      }

      if (!m.getLayer(def.id)) {
        m.addLayer({
          id: def.id,
          type: def.layerType as "line" | "circle" | "fill",
          source: srcId,
          paint: (def.paint ?? {}) as Parameters<typeof m.addLayer>[0]["paint"],
          layout: (def.layout ?? {}) as Parameters<typeof m.addLayer>[0]["layout"],
        });
      }
    } catch (e) {
      console.warn("[MapboxMap] addLayer error:", e);
    }
  }

  function addMarkersToMap(m: import("mapbox-gl").Map, mkrs: MapMarker[]) {
    // Clear existing markers
    markerInstancesRef.current.forEach((mk) => mk.remove());
    markerInstancesRef.current = [];

    // Add pulsing CSS once
    if (!document.getElementById("mapbox-marker-styles")) {
      const style = document.createElement("style");
      style.id = "mapbox-marker-styles";
      style.textContent = `
        @keyframes pulse-red { 0%,100% { box-shadow: 0 0 0 0 rgba(186,26,26,.5); } 70% { box-shadow: 0 0 0 14px rgba(186,26,26,0); } }
        @keyframes pulse-amber { 0%,100% { box-shadow: 0 0 0 0 rgba(217,119,6,.5); } 70% { box-shadow: 0 0 0 10px rgba(217,119,6,0); } }
        .mk-critical { animation: pulse-red 1.8s infinite; }
        .mk-high { animation: pulse-amber 2.2s infinite; }
      `;
      document.head.appendChild(style);
    }

    mkrs.forEach((marker) => {
      const el = document.createElement("div");
      const color = SEVERITY_COLORS[marker.severity ?? "moderate"] ?? "#888";

      if (marker.type === "incident") {
        el.style.cssText = `width:36px;height:36px;background:${color};border:3px solid white;border-radius:50%;display:flex;align-items:center;justify-content:center;cursor:pointer;box-shadow:0 4px 12px rgba(0,0,0,.3);`;
        el.className = `mk-${marker.severity}`;
        el.innerHTML = `<span style="color:white;font-family:'Material Symbols Outlined';font-size:16px;font-variation-settings:'FILL' 1">warning</span>`;
      } else if (marker.type === "camera") {
        el.style.cssText = `width:30px;height:30px;background:#2A6C0D;border:2px solid white;border-radius:50%;display:flex;align-items:center;justify-content:center;cursor:pointer;box-shadow:0 2px 8px rgba(0,0,0,.2);`;
        el.innerHTML = `<span style="color:white;font-family:'Material Symbols Outlined';font-size:14px;font-variation-settings:'FILL' 1">videocam</span>`;
      } else if (marker.type === "signal") {
        el.style.cssText = `width:28px;height:28px;background:#EAB308;border:2px solid white;border-radius:50%;display:flex;align-items:center;justify-content:center;cursor:pointer;box-shadow:0 2px 8px rgba(0,0,0,.2);`;
        el.innerHTML = `<span style="color:white;font-family:'Material Symbols Outlined';font-size:13px;font-variation-settings:'FILL' 1">traffic</span>`;
      } else if (marker.type === "diversion") {
        el.style.cssText = `width:26px;height:26px;background:#3B82F6;border:2px solid white;border-radius:50%;display:flex;align-items:center;justify-content:center;cursor:pointer;`;
        el.innerHTML = `<span style="color:white;font-family:'Material Symbols Outlined';font-size:13px;font-variation-settings:'FILL' 1">turn_right</span>`;
      }

      import("mapbox-gl").then((mgl) => {
        const mapboxgl = mgl.default as unknown as typeof import("mapbox-gl");
        const popup = marker.popup
          ? new (mapboxgl as unknown as { Popup: new (o: unknown) => import("mapbox-gl").Popup }).Popup({ offset: 25, closeButton: false })
              .setHTML(`<div style="font-family:sans-serif;padding:8px;min-width:160px"><p style="font-weight:700;font-size:12px;margin:0 0 4px">${marker.label ?? marker.id}</p><p style="font-size:11px;color:#555;margin:0">${marker.popup}</p></div>`)
          : undefined;

        const mk = new (mapboxgl as unknown as { Marker: new (o: unknown) => import("mapbox-gl").Marker }).Marker({ element: el })
          .setLngLat([marker.lng, marker.lat]);
        if (popup) mk.setPopup(popup);
        mk.addTo(m);
        markerInstancesRef.current.push(mk);
      });
    });
  }

  useEffect(() => {
    if (mapRef.current || !containerRef.current) return;
    const token = process.env.NEXT_PUBLIC_MAPBOX_TOKEN;
    if (!token) { console.error("[MapboxMap] Missing NEXT_PUBLIC_MAPBOX_TOKEN"); return; }

    import("mapbox-gl").then((mgl) => {
      const mapboxgl = mgl.default as unknown as typeof import("mapbox-gl");
      (mapboxgl as unknown as { accessToken: string }).accessToken = token;

      const map = new (mapboxgl as unknown as { Map: new (o: unknown) => import("mapbox-gl").Map }).Map({
        container: containerRef.current!,
        style: styleUrl,
        center,
        zoom,
        attributionControl: false,
      });

      mapRef.current = map;
      pendingRef.current.markers = markers;

      map.on("load", () => {
        addMarkersToMap(map, markers);
        // Re-add any layers queued before load
        layerDefsRef.current.forEach((def) => addLayerToMap(map, def));
        // Expose handle
        onMapReady?.(handleRef.current!);
      });
    });

    return () => {
      markerInstancesRef.current.forEach((mk) => mk.remove());
      mapRef.current?.remove();
      mapRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Update markers when prop changes (after initial load)
  useEffect(() => {
    if (mapRef.current?.isStyleLoaded()) {
      addMarkersToMap(mapRef.current, markers);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [markers]);

  return <div ref={containerRef} className={className} style={{ width: "100%", height: "100%" }} />;
});

export default MapboxMap;
