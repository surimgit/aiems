<template>
  <div class="relative h-full w-full">
    <div
      ref="mapContainer"
      class="absolute inset-0 h-full w-full"
      :class="{ 'cursor-crosshair': isAddArmed }"
    />
  </div>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from "vue";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
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
const MODEL_HIDE_BELOW_ZOOM = 13;
const MODEL_MID_ENTER_ZOOM = 14.7;
const MODEL_MID_EXIT_ZOOM = 14.35;
const MODEL_NEAR_ENTER_ZOOM = 16.2;
const MODEL_NEAR_EXIT_ZOOM = 15.85;
const MODEL_SCALE_STOPS = [
  { zoom: MODEL_HIDE_BELOW_ZOOM, multiplier: 10.4 },
  { zoom: MODEL_MID_ENTER_ZOOM, multiplier: 7.2 },
  { zoom: MODEL_NEAR_ENTER_ZOOM, multiplier: 3.8 },
  { zoom: 17.4, multiplier: 2.7 },
];
const MODEL_LAYER_ID = "equipment-models-3d";
const MODEL_GROUND_OFFSET_METERS = 0.35;
const INITIAL_MAP_PITCH = 60;
const INITIAL_MAP_BEARING = -15;

type EquipmentModelLod = "far" | "mid" | "near";

type EquipmentModelLodConfig = {
  url: string;
  sizePixels: number;
};

type EquipmentModelConfig = {
  lods: Record<EquipmentModelLod, EquipmentModelLodConfig>;
  sizeMeters: number;
  rotationZ?: number;
};

type EquipmentModelTemplate = {
  object: THREE.Object3D;
  maxDimension: number;
};

const MODEL_CONFIG: Record<MapEquipment["type"], EquipmentModelConfig> = {
  SOLAR: {
    lods: {
      far: { url: "/models/equipment/lod/solar-far.glb?v=lod2", sizePixels: 28 },
      mid: { url: "/models/equipment/lod/solar-mid.glb?v=lod2", sizePixels: 42 },
      near: { url: "/models/equipment/lod/solar-near.glb?v=lod2", sizePixels: 72 },
    },
    sizeMeters: 30,
    rotationZ: Math.PI * 1.08,
  },
  DIESEL: {
    lods: {
      far: { url: "/models/equipment/lod/diesel-far.glb?v=lod2", sizePixels: 28 },
      mid: { url: "/models/equipment/lod/diesel-mid.glb?v=lod2", sizePixels: 44 },
      near: { url: "/models/equipment/lod/diesel-near.glb?v=lod2", sizePixels: 78 },
    },
    sizeMeters: 19,
    rotationZ: Math.PI,
  },
  GENERATOR: {
    lods: {
      far: { url: "/models/equipment/lod/diesel-far.glb?v=lod2", sizePixels: 28 },
      mid: { url: "/models/equipment/lod/diesel-mid.glb?v=lod2", sizePixels: 44 },
      near: { url: "/models/equipment/lod/diesel-near.glb?v=lod2", sizePixels: 78 },
    },
    sizeMeters: 19,
    rotationZ: Math.PI,
  },
  ESS: {
    lods: {
      far: { url: "/models/equipment/lod/ess-far.glb?v=lod2", sizePixels: 30 },
      mid: { url: "/models/equipment/lod/ess-mid.glb?v=lod2", sizePixels: 48 },
      near: { url: "/models/equipment/lod/ess-near.glb?v=lod2", sizePixels: 82 },
    },
    sizeMeters: 32,
    rotationZ: 0,
  },
  LOAD: {
    lods: {
      far: { url: "/models/equipment/lod/load-far.glb?v=lod2", sizePixels: 26 },
      mid: { url: "/models/equipment/lod/load-mid.glb?v=lod2", sizePixels: 42 },
      near: { url: "/models/equipment/lod/load-near.glb?v=lod2", sizePixels: 76 },
    },
    sizeMeters: 30,
    rotationZ: Math.PI * 0.25,
  },
};

type EquipmentModelLayerState = {
  scene: THREE.Scene;
  camera: THREE.Camera;
  renderer: THREE.WebGLRenderer;
  loader: GLTFLoader;
  templates: Map<string, EquipmentModelTemplate>;
  loadingKeys: Set<string>;
  objects: Map<string, THREE.Object3D>;
  projectionMatrix: THREE.Matrix4;
  sceneTransformMatrix: THREE.Matrix4;
  sceneScaleVector: THREE.Vector3;
  originLngLat: [number, number];
  originMercator: maplibregl.MercatorCoordinate;
};

type EquipmentModelRenderOptions = {
  defaultProjectionData?: {
    mainMatrix?: ArrayLike<number>;
  };
  modelViewProjectionMatrix?: ArrayLike<number>;
};

type EquipmentModelRenderInput = EquipmentModelRenderOptions | ArrayLike<number>;

type EquipmentModelCustomLayer = {
  id: typeof MODEL_LAYER_ID;
  type: "custom";
  renderingMode: "3d";
  onAdd: (
    mapInstance: maplibregl.Map,
    gl: WebGLRenderingContext | WebGL2RenderingContext,
  ) => void;
  render: (
    glOrOptions: WebGLRenderingContext | WebGL2RenderingContext | EquipmentModelRenderInput,
    options?: EquipmentModelRenderInput,
  ) => void;
  onRemove: () => void;
};

let modelLayerState: EquipmentModelLayerState | null = null;

const prepareModelMaterial = (material: THREE.Material) => {
  const prepared = material.clone();
  prepared.depthTest = true;
  prepared.depthWrite = !prepared.transparent;

  if ("alphaTest" in prepared) {
    prepared.alphaTest = 0.05;
  }

  if ("map" in prepared && prepared.map instanceof THREE.Texture) {
    prepared.map.colorSpace = THREE.SRGBColorSpace;
    prepared.map.minFilter = THREE.LinearMipmapLinearFilter;
    prepared.map.magFilter = THREE.LinearFilter;
    prepared.map.anisotropy = modelLayerState?.renderer.capabilities.getMaxAnisotropy() ?? 1;
    prepared.map.generateMipmaps = true;
    prepared.map.needsUpdate = true;
  }

  prepared.needsUpdate = true;
  return prepared;
};

const normalizeModel = (source: THREE.Object3D): THREE.Object3D => {
  const sourceClone = source.clone(true);
  sourceClone.traverse((child) => {
    if (!(child instanceof THREE.Mesh)) return;
    child.frustumCulled = false;
    child.material = Array.isArray(child.material)
      ? child.material.map(prepareModelMaterial)
      : prepareModelMaterial(child.material);
  });

  const sourceBox = new THREE.Box3().setFromObject(sourceClone);
  const center = new THREE.Vector3();
  sourceBox.getCenter(center);

  sourceClone.position.x -= center.x;
  sourceClone.position.y -= sourceBox.min.y;
  sourceClone.position.z -= center.z;

  const wrapper = new THREE.Group();
  wrapper.add(sourceClone);
  return wrapper;
};

const getModelMaxDimension = (object: THREE.Object3D) => {
  const box = new THREE.Box3().setFromObject(object);
  const size = new THREE.Vector3();
  box.getSize(size);
  return Math.max(size.x, size.y, size.z, 0.0001);
};

const getModelScaleMultiplier = (zoom: number) => {
  if (zoom <= MODEL_SCALE_STOPS[0].zoom) return MODEL_SCALE_STOPS[0].multiplier;

  for (let index = 1; index < MODEL_SCALE_STOPS.length; index += 1) {
    const previous = MODEL_SCALE_STOPS[index - 1];
    const next = MODEL_SCALE_STOPS[index];
    if (zoom > next.zoom) continue;

    const progress = (zoom - previous.zoom) / (next.zoom - previous.zoom);
    return previous.multiplier + (next.multiplier - previous.multiplier) * progress;
  }

  return MODEL_SCALE_STOPS[MODEL_SCALE_STOPS.length - 1].multiplier;
};

const getModelTemplateKey = (type: MapEquipment["type"], lod: EquipmentModelLod) =>
  `${type}:${lod}`;

const getCurrentObjectLod = (item: MapEquipment): EquipmentModelLod | undefined =>
  modelLayerState?.objects.get(item.id)?.userData.equipmentLod;

const getDesiredModelLod = (item: MapEquipment): EquipmentModelLod | null => {
  const zoom = map?.getZoom() ?? MODEL_NEAR_ENTER_ZOOM;
  if (zoom < MODEL_HIDE_BELOW_ZOOM) return null;

  const current = getCurrentObjectLod(item);
  if (current === "near" && zoom >= MODEL_NEAR_EXIT_ZOOM) return "near";
  if (current === "mid" && zoom >= MODEL_MID_EXIT_ZOOM && zoom < MODEL_NEAR_ENTER_ZOOM) return "mid";
  if (zoom >= MODEL_NEAR_ENTER_ZOOM) return "near";
  if (zoom >= MODEL_MID_ENTER_ZOOM) return "mid";
  return "far";
};

const loadModelTemplate = (type: MapEquipment["type"], lod: EquipmentModelLod) => {
  if (!modelLayerState) return;
  const key = getModelTemplateKey(type, lod);
  if (modelLayerState.templates.has(key) || modelLayerState.loadingKeys.has(key)) return;

  const config = MODEL_CONFIG[type];
  const lodConfig = config.lods[lod];
  modelLayerState.loadingKeys.add(key);
  modelLayerState.loader.load(
    lodConfig.url,
    (gltf) => {
      if (!modelLayerState) return;
      const object = normalizeModel(gltf.scene);
      modelLayerState.templates.set(key, {
        object,
        maxDimension: getModelMaxDimension(object),
      });
      modelLayerState.loadingKeys.delete(key);
      syncEquipmentModels();
    },
    undefined,
    (error) => {
      modelLayerState?.loadingKeys.delete(key);
      console.warn(`[Map3DViewer] GLB 모델 로드 실패: ${type}`, error);
    },
  );
};

const refreshEquipmentModelMatrices = () => {
  if (!modelLayerState) return;
  props.equipmentData.forEach((item) => {
    const object = modelLayerState?.objects.get(item.id);
    if (!object) return;
    const lod = object.userData.equipmentLod as EquipmentModelLod | undefined;
    if (!lod) return;
    applyModelMatrix(object, item, lod);
  });
};

const getLayerProjectionMatrix = (
  glOrOptions: WebGLRenderingContext | WebGL2RenderingContext | EquipmentModelRenderInput,
  options?: EquipmentModelRenderInput,
) => {
  const isMatrixLike = (value: unknown): value is ArrayLike<number> =>
    typeof value === "object" &&
    value !== null &&
    typeof (value as ArrayLike<number>).length === "number";

  if (isMatrixLike(options)) return options;
  if (isMatrixLike(glOrOptions)) return glOrOptions;

  const renderOptions =
    options ?? ("defaultProjectionData" in glOrOptions || "modelViewProjectionMatrix" in glOrOptions
      ? glOrOptions
      : undefined);

  return (
    renderOptions?.defaultProjectionData?.mainMatrix ??
    renderOptions?.modelViewProjectionMatrix ??
    null
  );
};

const getModelSceneOrigin = (): [number, number] => {
  const centroid = getEquipmentCentroid();
  if (centroid) return centroid;
  const center = map?.getCenter();
  return center ? [center.lng, center.lat] : [129.0755, 35.1785];
};

const updateModelSceneOrigin = () => {
  if (!modelLayerState) return;
  const originLngLat = getModelSceneOrigin();
  modelLayerState.originLngLat = originLngLat;
  modelLayerState.originMercator = maplibregl.MercatorCoordinate.fromLngLat(originLngLat, 0);
};

const getMeterOffsetFromOrigin = (lngLat: [number, number]) => {
  if (!modelLayerState) return { east: 0, north: 0 };
  const origin = modelLayerState.originMercator;
  const target = maplibregl.MercatorCoordinate.fromLngLat(lngLat, 0);
  const mercatorUnitsPerMeter = origin.meterInMercatorCoordinateUnits();
  return {
    east: (target.x - origin.x) / mercatorUnitsPerMeter,
    north: (origin.y - target.y) / mercatorUnitsPerMeter,
  };
};

const applyModelMatrix = (object: THREE.Object3D, item: MapEquipment, lod: EquipmentModelLod) => {
  if (!map || !modelLayerState) return;
  const config = MODEL_CONFIG[item.type];
  const lodConfig = config.lods[lod];
  const zoom = map.getZoom();
  const modelScaleMultiplier = getModelScaleMultiplier(zoom);
  const point = map.project(item.lngLat);
  const width = modelLayerState.renderer.domElement.clientWidth;
  const height = modelLayerState.renderer.domElement.clientHeight;
  const sizePixels = lodConfig.sizePixels * modelScaleMultiplier;
  const margin = sizePixels * 2;

  if (
    point.x < -margin ||
    point.x > width + margin ||
    point.y < -margin ||
    point.y > height + margin
  ) {
    object.visible = false;
    return;
  }

  const selectedScale = item.id === props.selectedEquipmentId ? 1.16 : 1;
  const modelMaxDimension =
    typeof object.userData.equipmentMaxDimension === "number"
      ? object.userData.equipmentMaxDimension
      : 1;
  const scale = (config.sizeMeters * selectedScale * modelScaleMultiplier) / modelMaxDimension;
  const offset = getMeterOffsetFromOrigin(item.lngLat);

  object.matrixAutoUpdate = true;
  object.position.set(offset.east, MODEL_GROUND_OFFSET_METERS, offset.north);
  object.rotation.set(0, -(config.rotationZ ?? 0), 0);
  object.scale.setScalar(scale);
  object.visible = true;
};

const syncEquipmentModels = () => {
  if (!modelLayerState) return;
  updateModelSceneOrigin();

  const visibleIds = new Set<string>();
  props.equipmentData.forEach((item) => {
    const lod = getDesiredModelLod(item);
    if (!lod) return;

    visibleIds.add(item.id);
    loadModelTemplate(item.type, lod);

    const templateKey = getModelTemplateKey(item.type, lod);
    const template = modelLayerState?.templates.get(templateKey);
    if (!template || !modelLayerState) return;

    let object = modelLayerState.objects.get(item.id);
    if (
      object &&
      (object.userData.equipmentType !== item.type ||
        object.userData.equipmentLod !== lod)
    ) {
      modelLayerState.scene.remove(object);
      modelLayerState.objects.delete(item.id);
      object = undefined;
    }
    if (!object) {
      object = template.object.clone(true);
      object.userData.equipmentType = item.type;
      object.userData.equipmentLod = lod;
      object.userData.equipmentMaxDimension = template.maxDimension;
      modelLayerState.objects.set(item.id, object);
      modelLayerState.scene.add(object);
    }
    applyModelMatrix(object, item, lod);
  });

  Array.from(modelLayerState.objects.entries()).forEach(([id, object]) => {
    if (visibleIds.has(id)) return;
    modelLayerState?.scene.remove(object);
    modelLayerState?.objects.delete(id);
  });

  map?.triggerRepaint();
};

const renderEquipmentModelLayer = (
  glOrOptions: WebGLRenderingContext | WebGL2RenderingContext | EquipmentModelRenderInput,
  options?: EquipmentModelRenderInput,
) => {
  if (!modelLayerState) return;
  const projectionMatrix = getLayerProjectionMatrix(glOrOptions, options);
  if (!projectionMatrix) return;

  updateModelSceneOrigin();
  refreshEquipmentModelMatrices();
  const originMercator = modelLayerState.originMercator;
  const mercatorScale = originMercator.meterInMercatorCoordinateUnits();
  const sceneTransformMatrix = modelLayerState.sceneTransformMatrix
    .makeTranslation(originMercator.x, originMercator.y, originMercator.z)
    .scale(modelLayerState.sceneScaleVector.set(mercatorScale, -mercatorScale, mercatorScale));
  modelLayerState.camera.projectionMatrix.copy(
    modelLayerState.projectionMatrix.fromArray(projectionMatrix).multiply(sceneTransformMatrix),
  );
  modelLayerState.renderer.resetState();
  modelLayerState.renderer.render(modelLayerState.scene, modelLayerState.camera);
};

const disposeEquipmentModelLayerState = () => {
  modelLayerState?.renderer.dispose();
  modelLayerState = null;
};

const createEquipmentModelLayer = (): EquipmentModelCustomLayer => ({
  id: MODEL_LAYER_ID,
  type: "custom",
  renderingMode: "3d",
  onAdd(mapInstance, gl) {
    const originLngLat = getModelSceneOrigin();
    const scene = new THREE.Scene();
    scene.rotateX(Math.PI / 2);
    scene.scale.multiply(new THREE.Vector3(1, 1, -1));
    scene.add(new THREE.AmbientLight(0xffffff, 2.2));

    const keyLight = new THREE.DirectionalLight(0xffffff, 2.4);
    keyLight.position.set(0, -70, 100).normalize();
    scene.add(keyLight);

    const fillLight = new THREE.DirectionalLight(0x93c5fd, 1.2);
    fillLight.position.set(-70, 70, 100).normalize();
    scene.add(fillLight);

    const renderer = new THREE.WebGLRenderer({
      canvas: mapInstance.getCanvas(),
      context: gl,
      antialias: true,
    });
    renderer.autoClear = false;
    renderer.outputColorSpace = THREE.SRGBColorSpace;

    modelLayerState = {
      scene,
      camera: new THREE.Camera(),
      renderer,
      loader: new GLTFLoader(),
      templates: new Map(),
      loadingKeys: new Set(),
      objects: new Map(),
      projectionMatrix: new THREE.Matrix4(),
      sceneTransformMatrix: new THREE.Matrix4(),
      sceneScaleVector: new THREE.Vector3(),
      originLngLat,
      originMercator: maplibregl.MercatorCoordinate.fromLngLat(originLngLat, 0),
    };

    syncEquipmentModels();
  },
  render: renderEquipmentModelLayer,
  onRemove() {
    disposeEquipmentModelLayerState();
  },
});

const setupEquipmentModelLayer = () => {
  if (!map || modelLayerState || map.getLayer(MODEL_LAYER_ID)) return;
  map.addLayer(createEquipmentModelLayer() as any);
};

const disposeEquipmentModelLayer = () => {
  if (map?.getLayer(MODEL_LAYER_ID)) {
    map.removeLayer(MODEL_LAYER_ID);
    return;
  }
  disposeEquipmentModelLayerState();
};

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
    const size = 0.00016;
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
  syncEquipmentModels();
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
      map.setPaintProperty("boxes-error", "fill-opacity", 0.04 + blink * 0.08);
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
    pitch: INITIAL_MAP_PITCH,
    bearing: INITIAL_MAP_BEARING,
    canvasContextAttributes: { antialias: true },
    renderWorldCopies: false,
  });

  const requestMapResize = () => {
    if (!map) return;
    if (resizeRaf) cancelAnimationFrame(resizeRaf);
    resizeRaf = requestAnimationFrame(() => {
      if (!map) return;
      map.resize();
      map.triggerRepaint();
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
    syncEquipmentModels();
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
      type: "fill",
      source: "3d-boxes-source",
      minzoom: 7.5,
      filter: ["!=", ["get", "status"], "error"],
      paint: {
        "fill-color": [
          "match",
          ["get", "status"],
          "normal",
          "#ffffff",
          "stopped",
          "#9ca3af",
          "#ffffff",
        ],
        "fill-opacity": 0.001,
      },
    });
    map.addLayer({
      id: "boxes-error",
      type: "fill",
      source: "3d-boxes-source",
      minzoom: 7.5,
      filter: ["==", ["get", "status"], "error"],
      paint: {
        "fill-color": "#ef4444",
        "fill-opacity": ["interpolate", ["linear"], ["zoom"], 7.5, 0.04, 10, 0.08],
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

    setupEquipmentModelLayer();

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
  disposeEquipmentModelLayer();
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
    syncEquipmentModels();
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
