<template>
  <div
    ref="mapContainer"
    class="h-full w-full"
    :class="{ 'cursor-crosshair': isAddArmed }"
  />
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from "vue";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import type { MapConnection, MapEquipment } from "../types";

const props = defineProps<{
  equipmentData: MapEquipment[];
  connections: MapConnection[];
  isEditMode: boolean;
  isAddArmed: boolean;
  selectedEquipmentId?: string | null;
  selectedLineId?: string | null;
}>();

const emit = defineEmits<{
  (
    e: "update-positions",
    value: Record<string, { x: number; y: number }>,
  ): void;
  (e: "map-click", lngLat: [number, number]): void;
  (e: "equip-click", id: string): void;
  (e: "line-click", id: string): void;
  (e: "zoom-change", zoom: number): void;
}>();

const mapContainer = ref<HTMLElement | null>(null);
let map: maplibregl.Map | null = null;
let animationId: number | null = null;
let hasAutoCentered = false;
let lastAutoCenter: [number, number] | null = null;
let resizeObserver: ResizeObserver | null = null;
let resizeRaf: number | null = null;
let windowResizeHandler: (() => void) | null = null;

const toPointFeatureCollection = () => ({
  type: "FeatureCollection",
  features: props.equipmentData.map((e) => ({
    type: "Feature",
    properties: { id: e.id, status: e.status },
    geometry: { type: "Point", coordinates: e.lngLat },
  })),
});

const toBoxFeatureCollection = () => ({
  type: "FeatureCollection",
  features: props.equipmentData.map((e) => {
    const size = 0.00085;
    const [lng, lat] = e.lngLat;
    return {
      type: "Feature",
      properties: {
        id: e.id,
        status: e.status,
        height: 36,
      },
      geometry: {
        type: "Polygon",
        coordinates: [
          [
            [lng - size, lat - size],
            [lng + size, lat - size],
            [lng + size, lat + size],
            [lng - size, lat + size],
            [lng - size, lat - size],
          ],
        ],
      },
    };
  }),
});

const toLineFeatureCollection = () => {
  const equipmentMap = new Map(
    props.equipmentData.map((item) => [item.id, item]),
  );
  return {
    type: "FeatureCollection",
    features: props.connections
      .map((line) => {
        const from = equipmentMap.get(line.fromEquipmentId);
        const to = equipmentMap.get(line.toEquipmentId);
        if (!from || !to) return null;

        const busLng = (from.lngLat[0] + to.lngLat[0]) / 2;
        return {
          type: "Feature",
          properties: {
            id: line.id,
            status: line.status,
            direction: line.direction,
            arrow:
              line.direction === "FORWARD"
                ? "▶"
                : line.direction === "REVERSE"
                  ? "◀"
                  : "◀▶",
          },
          geometry: {
            type: "LineString",
            coordinates: [
              from.lngLat,
              [busLng, from.lngLat[1]],
              [busLng, to.lngLat[1]],
              to.lngLat,
            ],
          },
        };
      })
      .filter(Boolean),
  };
};

const refreshMapSources = () => {
  if (!map) return;
  const points = map.getSource("points-source") as
    | maplibregl.GeoJSONSource
    | undefined;
  if (points) points.setData(toPointFeatureCollection() as any);
  const boxes = map.getSource("3d-boxes-source") as
    | maplibregl.GeoJSONSource
    | undefined;
  if (boxes) boxes.setData(toBoxFeatureCollection() as any);
  const lines = map.getSource("power-lines-source") as
    | maplibregl.GeoJSONSource
    | undefined;
  if (lines) lines.setData(toLineFeatureCollection() as any);
};

const centerMapToEquipments = () => {
  if (!map || props.equipmentData.length === 0) return;
  const bounds = new maplibregl.LngLatBounds();
  props.equipmentData.forEach((item) => bounds.extend(item.lngLat));

  if (props.equipmentData.length === 1) {
    map.easeTo({ center: props.equipmentData[0].lngLat, zoom: 13.2, duration: 600 });
    return;
  }

  const lngSpan = Math.abs(bounds.getEast() - bounds.getWest());
  const latSpan = Math.abs(bounds.getNorth() - bounds.getSouth());
  const isVeryTightCluster = lngSpan < 0.004 && latSpan < 0.004;
  const isWideSpread = lngSpan > 0.2 || latSpan > 0.2;

  map.fitBounds(bounds, {
    padding: isWideSpread
      ? { top: 90, right: 90, bottom: 90, left: 90 }
      : { top: 140, right: 120, bottom: 140, left: 120 },
    duration: 700,
    maxZoom: isWideSpread ? 11.8 : isVeryTightCluster ? 13.6 : 14.2,
  });
};

const getEquipmentCentroid = (): [number, number] | null => {
  if (props.equipmentData.length === 0) return null;
  const sum = props.equipmentData.reduce(
    (acc, item) => {
      acc.lng += item.lngLat[0];
      acc.lat += item.lngLat[1];
      return acc;
    },
    { lng: 0, lat: 0 },
  );
  return [sum.lng / props.equipmentData.length, sum.lat / props.equipmentData.length];
};

const hasMeaningfulCenterShift = (nextCenter: [number, number], prevCenter: [number, number] | null): boolean => {
  if (!prevCenter) return true;
  const lngDelta = Math.abs(nextCenter[0] - prevCenter[0]);
  const latDelta = Math.abs(nextCenter[1] - prevCenter[1]);
  return lngDelta > 0.02 || latDelta > 0.02;
};

const startAnimation = () => {
  const dashLen = 2;
  const gapLen = 2;
  const steps = 12;
  const sequence: number[][] = [];
  const total = dashLen + gapLen;
  for (let i = 0; i < steps; i += 1) {
    const offset = (total * i) / steps;
    if (offset < dashLen) sequence.push([dashLen - offset, gapLen, offset, 0]);
    else
      sequence.push([
        0,
        gapLen - (offset - dashLen),
        dashLen,
        offset - dashLen,
      ]);
  }

  let stepIndex = 0;
  let lastTime = 0;

  const animate = (timestamp: number) => {
    if (!map) return;
    if (!lastTime) lastTime = timestamp;
    const progress = timestamp - lastTime;
    const blink = 0.6 + 0.3 * Math.sin(timestamp / 140);

    if (map.getLayer("lines-main-error")) {
      map.setPaintProperty("lines-main-error", "line-opacity", blink);
      map.setPaintProperty("lines-glow-error", "line-opacity", blink * 0.5);
    }
    if (map.getLayer("boxes-error")) {
      map.setPaintProperty("boxes-error", "fill-extrusion-opacity", blink);
    }

    if (progress > 42) {
      stepIndex = (stepIndex - 1 + steps) % steps;
      const dash = sequence[stepIndex];
      if (map.getLayer("lines-main-normal"))
        map.setPaintProperty("lines-main-normal", "line-dasharray", dash);
      if (map.getLayer("lines-main-error"))
        map.setPaintProperty("lines-main-error", "line-dasharray", dash);
      lastTime = timestamp;
    }

    animationId = requestAnimationFrame(animate);
  };

  animationId = requestAnimationFrame(animate);
};

onMounted(() => {
  if (!mapContainer.value) return;

  map = new maplibregl.Map({
    container: mapContainer.value,
    style: "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json",
    center: [129.0755, 35.1785],
    zoom: 16,
    minZoom: 2,
    maxZoom: 18,
    pitch: 60,
    bearing: -15,
    renderWorldCopies: false,
  });

  const requestMapResize = () => {
    if (!map) return;
    if (resizeRaf) cancelAnimationFrame(resizeRaf);
    resizeRaf = requestAnimationFrame(() => {
      if (!map) return;
      map.resize();
    });
  };

  if (typeof ResizeObserver !== "undefined" && mapContainer.value) {
    resizeObserver = new ResizeObserver(() => {
      requestMapResize();
    });
    resizeObserver.observe(mapContainer.value);
  }
  windowResizeHandler = requestMapResize;
  window.addEventListener("resize", windowResizeHandler);

  map.on("zoom", () => {
    if (!map) return;
    emit("zoom-change", map.getZoom());
  });

  map.on("load", () => {
    if (!map) return;

    map.addSource("points-source", {
      type: "geojson",
      data: toPointFeatureCollection() as any,
      cluster: true,
      clusterRadius: 64,
      clusterMaxZoom: 8,
    });
    map.addSource("3d-boxes-source", {
      type: "geojson",
      data: toBoxFeatureCollection() as any,
    });
    map.addSource("power-lines-source", {
      type: "geojson",
      data: toLineFeatureCollection() as any,
    });

    map.addLayer({
      id: "cluster-circles",
      type: "circle",
      source: "points-source",
      filter: ["has", "point_count"],
      maxzoom: 8,
      paint: {
        "circle-color": "#3b82f6",
        "circle-radius": 20,
        "circle-stroke-width": 2,
        "circle-stroke-color": "#ffffff",
      },
    });
    map.addLayer({
      id: "cluster-count",
      type: "symbol",
      source: "points-source",
      filter: ["has", "point_count"],
      maxzoom: 8,
      layout: { "text-field": "{point_count}", "text-size": 14 },
      paint: { "text-color": "#ffffff" },
    });
    map.addLayer({
      id: "points-unclustered",
      type: "circle",
      source: "points-source",
      filter: ["!", ["has", "point_count"]],
      minzoom: 7.5,
      paint: {
        "circle-color": [
          "match",
          ["get", "status"],
          "error",
          "#ef4444",
          "stopped",
          "#9ca3af",
          "#f8fafc",
        ],
        "circle-radius": ["interpolate", ["linear"], ["zoom"], 4, 4, 10, 6, 13, 8],
        "circle-stroke-width": 1.5,
        "circle-stroke-color": "#0f172a",
      },
    });
    map.addLayer({
      id: "points-label",
      type: "symbol",
      source: "points-source",
      filter: ["!", ["has", "point_count"]],
      minzoom: 8,
      layout: {
        "text-field": ["get", "id"],
        "text-size": ["interpolate", ["linear"], ["zoom"], 8, 10, 12, 12],
        "text-offset": [0, 1.2],
      },
      paint: {
        "text-color": "#e2e8f0",
        "text-halo-color": "#020617",
        "text-halo-width": 1,
      },
    });

    map.addLayer({
      id: "lines-glow-normal",
      type: "line",
      source: "power-lines-source",
      minzoom: 4,
      filter: ["==", ["get", "status"], "normal"],
      paint: {
        "line-color": "#ffffff",
        "line-width": ["interpolate", ["linear"], ["zoom"], 4, 2.2, 8, 3.4, 12, 5.4],
        "line-opacity": 0.18,
        "line-blur": ["interpolate", ["linear"], ["zoom"], 4, 1.2, 10, 3.2],
      },
    });
    map.addLayer({
      id: "lines-glow-error",
      type: "line",
      source: "power-lines-source",
      minzoom: 4,
      filter: ["==", ["get", "status"], "error"],
      paint: {
        "line-color": "#ef4444",
        "line-width": ["interpolate", ["linear"], ["zoom"], 4, 2.6, 8, 3.8, 12, 6],
        "line-opacity": 0.45,
        "line-blur": ["interpolate", ["linear"], ["zoom"], 4, 1.4, 10, 3.8],
      },
    });
    map.addLayer({
      id: "lines-glow-stopped",
      type: "line",
      source: "power-lines-source",
      minzoom: 4,
      filter: ["==", ["get", "status"], "stopped"],
      paint: {
        "line-color": "#9ca3af",
        "line-width": ["interpolate", ["linear"], ["zoom"], 4, 1.8, 8, 3, 12, 4.4],
        "line-opacity": 0.14,
        "line-blur": ["interpolate", ["linear"], ["zoom"], 4, 0.8, 10, 2.2],
      },
    });

    map.addLayer({
      id: "lines-main-normal",
      type: "line",
      source: "power-lines-source",
      minzoom: 4,
      filter: ["==", ["get", "status"], "normal"],
      paint: {
        "line-color": "#ffffff",
        "line-width": ["interpolate", ["linear"], ["zoom"], 4, 1.2, 8, 1.8, 12, 2.8],
        "line-dasharray": [2, 2],
      },
    });
    map.addLayer({
      id: "lines-main-error",
      type: "line",
      source: "power-lines-source",
      minzoom: 4,
      filter: ["==", ["get", "status"], "error"],
      paint: {
        "line-color": "#ef4444",
        "line-width": ["interpolate", ["linear"], ["zoom"], 4, 1.2, 8, 1.8, 12, 2.8],
        "line-dasharray": [2, 2],
      },
    });
    map.addLayer({
      id: "lines-main-stopped",
      type: "line",
      source: "power-lines-source",
      minzoom: 4,
      filter: ["==", ["get", "status"], "stopped"],
      paint: { "line-color": "#9ca3af", "line-width": ["interpolate", ["linear"], ["zoom"], 4, 1, 8, 1.4, 12, 2.2] },
    });

    map.addLayer({
      id: "lines-hit-area",
      type: "line",
      source: "power-lines-source",
      minzoom: 4,
      paint: {
        "line-color": "#000000",
        "line-width": 16,
        "line-opacity": 0.001,
      },
    });

    map.addLayer({
      id: "line-selected-highlight",
      type: "line",
      source: "power-lines-source",
      minzoom: 4,
      filter: ["==", ["get", "id"], "__none__"],
      paint: {
        "line-color": "#60a5fa",
        "line-width": 6,
        "line-opacity": 0.95,
      },
    });
    map.addLayer({
      id: "lines-direction",
      type: "symbol",
      source: "power-lines-source",
      minzoom: 4,
      layout: {
        "symbol-placement": "line",
        "text-field": ["get", "arrow"],
        "text-size": 10,
        "symbol-spacing": 100,
      },
      paint: { "text-color": "#e2e8f0", "text-opacity": 0.8 },
    });

    map.addLayer({
      id: "boxes-base",
      type: "fill-extrusion",
      source: "3d-boxes-source",
      minzoom: 7.5,
      filter: ["!=", ["get", "status"], "error"],
      paint: {
        "fill-extrusion-color": [
          "match",
          ["get", "status"],
          "normal",
          "#ffffff",
          "stopped",
          "#9ca3af",
          "#ffffff",
        ],
        "fill-extrusion-height": ["get", "height"],
        "fill-extrusion-base": 0,
        "fill-extrusion-opacity": ["interpolate", ["linear"], ["zoom"], 7.5, 0.72, 10, 0.88],
      },
    });
    map.addLayer({
      id: "boxes-error",
      type: "fill-extrusion",
      source: "3d-boxes-source",
      minzoom: 7.5,
      filter: ["==", ["get", "status"], "error"],
      paint: {
        "fill-extrusion-color": "#ef4444",
        "fill-extrusion-height": ["get", "height"],
        "fill-extrusion-base": 0,
        "fill-extrusion-opacity": ["interpolate", ["linear"], ["zoom"], 7.5, 0.72, 10, 0.88],
      },
    });
    map.addLayer({
      id: "boxes-selected-highlight",
      type: "line",
      source: "3d-boxes-source",
      minzoom: 7.5,
      filter: ["==", ["get", "id"], "__none__"],
      paint: {
        "line-color": "#22d3ee",
        "line-width": 4,
        "line-opacity": 0.95,
      },
    });

    map.on("render", () => {
      if (!map) return;
      const positions: Record<string, { x: number; y: number }> = {};
      props.equipmentData.forEach((e) => {
        const point = map!.project(e.lngLat);
        positions[e.id] = { x: point.x, y: point.y };
      });
      emit("update-positions", positions);
    });

    map.on("click", (event) => {
      if (!map) return;
      const features = map.queryRenderedFeatures(event.point, {
        layers: ["boxes-base", "boxes-error", "points-unclustered"],
      });
      if (features.length > 0) {
        const id = features[0].properties?.id;
        if (id) emit("equip-click", String(id));
        return;
      }

      const lineFeatures = map.queryRenderedFeatures(event.point, {
        layers: ["lines-hit-area", "lines-main-normal", "lines-main-error", "lines-main-stopped"],
      });
      if (lineFeatures.length > 0) {
        const lineId = lineFeatures[0].properties?.id;
        if (lineId) emit("line-click", String(lineId));
        return;
      }

      if (props.isEditMode && props.isAddArmed) {
        emit("map-click", [event.lngLat.lng, event.lngLat.lat]);
      }
    });

    map.on("mouseenter", "boxes-base", () => {
      if (!map || !props.isEditMode || props.isAddArmed) return;
      map.getCanvas().style.cursor = "pointer";
    });
    map.on("mouseleave", "boxes-base", () => {
      if (!map) return;
      map.getCanvas().style.cursor = "";
    });

    map.on("mouseenter", "lines-hit-area", () => {
      if (!map || props.isAddArmed) return;
      map.getCanvas().style.cursor = "pointer";
    });
    map.on("mouseleave", "lines-hit-area", () => {
      if (!map || props.isAddArmed) return;
      map.getCanvas().style.cursor = "";
    });
    map.on("mouseenter", "points-unclustered", () => {
      if (!map || props.isAddArmed) return;
      map.getCanvas().style.cursor = "pointer";
    });
    map.on("mouseleave", "points-unclustered", () => {
      if (!map || props.isAddArmed) return;
      map.getCanvas().style.cursor = "";
    });

    startAnimation();
  });
});

onBeforeUnmount(() => {
  if (animationId) cancelAnimationFrame(animationId);
  if (resizeRaf) cancelAnimationFrame(resizeRaf);
  if (resizeObserver) resizeObserver.disconnect();
  if (windowResizeHandler) window.removeEventListener("resize", windowResizeHandler);
  if (map) map.remove();
});

watch(() => props.equipmentData, refreshMapSources, { deep: true });
watch(
  () => props.equipmentData,
  (items) => {
    if (items.length === 0) return;
    const nextCenter = getEquipmentCentroid();
    const shouldRecenter = !hasAutoCentered || (nextCenter !== null && hasMeaningfulCenterShift(nextCenter, lastAutoCenter));
    if (!shouldRecenter) return;
    centerMapToEquipments();
    hasAutoCentered = true;
    if (nextCenter) lastAutoCenter = nextCenter;
  },
  { deep: true, immediate: true },
);
watch(() => props.connections, refreshMapSources, { deep: true });
watch(
  () => props.selectedEquipmentId,
  (equipmentId) => {
    if (!map || !map.getLayer("boxes-selected-highlight")) return;
    const targetId = equipmentId ?? "__none__";
    map.setFilter("boxes-selected-highlight", ["==", ["get", "id"], targetId]);
  },
  { immediate: true },
);

watch(
  () => props.selectedLineId,
  (lineId) => {
    if (!map || !map.getLayer("line-selected-highlight")) return;
    const targetId = lineId ?? "__none__";
    map.setFilter("line-selected-highlight", ["==", ["get", "id"], targetId]);
  },
  { immediate: true },
);
watch(
  () => props.isAddArmed,
  (armed) => {
    if (!map) return;
    map.getCanvas().style.cursor = armed ? "crosshair" : "";
  },
);
</script>
