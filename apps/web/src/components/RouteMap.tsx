import { useEffect, useRef } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import type { LifeRoute } from "../types";

const STYLE = "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json";

type RouteMapProps = {
  route: LifeRoute;
  activeStopIndex: number;
  onSelectStop?: (index: number) => void;
  compact?: boolean;
};

export function RouteMap({
  route,
  activeStopIndex,
  onSelectStop,
  compact = false,
}: RouteMapProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const markersRef = useRef<maplibregl.Marker[]>([]);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    const first = route.stops[0];
    const map = new maplibregl.Map({
      container: containerRef.current,
      style: STYLE,
      center: [first.lng, first.lat],
      zoom: compact ? 13.2 : 14,
      attributionControl: false,
    });
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
    mapRef.current = map;

    map.on("load", () => {
      if (route.geometry?.coordinates?.length) {
        map.addSource("route-line", {
          type: "geojson",
          data: {
            type: "Feature",
            properties: {},
            geometry: route.geometry,
          },
        });
        map.addLayer({
          id: "route-line-glow",
          type: "line",
          source: "route-line",
          paint: {
            "line-color": "#00e676",
            "line-width": 8,
            "line-opacity": 0.25,
            "line-blur": 2,
          },
        });
        map.addLayer({
          id: "route-line",
          type: "line",
          source: "route-line",
          paint: {
            "line-color": "#00e676",
            "line-width": 3,
            "line-opacity": 0.9,
          },
        });
      }

      const bounds = new maplibregl.LngLatBounds();
      route.stops.forEach((s) => bounds.extend([s.lng, s.lat]));
      if (!bounds.isEmpty()) {
        map.fitBounds(bounds, { padding: compact ? 28 : 48, maxZoom: 15 });
      }
    });

    return () => {
      markersRef.current.forEach((m) => m.remove());
      markersRef.current = [];
      map.remove();
      mapRef.current = null;
    };
  }, [route, compact]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    markersRef.current.forEach((m) => m.remove());
    markersRef.current = [];

    route.stops.forEach((stop, index) => {
      const el = document.createElement("button");
      el.type = "button";
      el.className = `map-stop-marker${index === activeStopIndex ? " map-stop-marker--active" : ""}`;
      el.textContent = stop.code.split("-").pop() ?? String(index + 1);
      el.title = stop.name;
      el.addEventListener("click", () => onSelectStop?.(index));

      const marker = new maplibregl.Marker({ element: el })
        .setLngLat([stop.lng, stop.lat])
        .addTo(map);
      markersRef.current.push(marker);
    });
  }, [route.stops, activeStopIndex, onSelectStop]);

  return (
    <div
      className={`route-map-canvas${compact ? " route-map-canvas--compact" : ""}`}
      ref={containerRef}
      role="img"
      aria-label={`${route.title} 步行线路地图`}
    />
  );
}
