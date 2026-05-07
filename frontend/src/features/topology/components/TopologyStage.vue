<!-- src/features/topology/components/TopologyStage.vue -->
<template>
  <!-- STD 규칙: 부모(DashboardShell) 영역을 꽉 채우도록 w-full, h-full 적용 -->
  <div
    class="relative w-full h-full bg-slate-950 overflow-hidden rounded-xl border border-white/10"
  >
    <!-- MapLibre 캔버스 -->
    <div ref="mapContainer" class="w-full h-full"></div>

    <!-- 줌 레벨에 따라 나타나는 글래스모피즘 상태창 (텍스트 최소화, 상태 우선) -->
    <div v-show="isUiVisible" class="absolute inset-0 pointer-events-none z-10">
      <div
        v-for="node in topology?.nodes || []"
        :key="node.node_id"
        class="absolute w-[140px] bg-slate-900/60 backdrop-blur-md border border-white/10 rounded-lg text-white pointer-events-auto shadow-xl transition-transform cursor-pointer"
        :style="getUiPosition(node.node_id)"
        @click="emit('select-node', node.node_id)"
      >
        <!-- 상태별 색상 적용 (정상: 초록, 에러: 빨강, 중지: 회색) -->
        <div
          class="px-3 py-1.5 font-bold text-[12px] border-b border-white/10 flex justify-between"
          :class="{
            'text-emerald-400': node.status === 'NORMAL',
            'text-rose-500': node.status === 'EMERGENCY',
            'text-slate-400': node.status === 'WARNING',
          }"
        >
          <span>{{ node.node_id || node.node_type }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, onBeforeUnmount, watch } from "vue";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import type { TopologyData } from "@/types/common";

const props = defineProps<{
  topology: TopologyData | null;
}>();

const emit = defineEmits<{
  // STD 6.3: 노드 클릭 시 이벤트 발생 -> OverviewPage에서 처리
  (e: "select-node", nodeId: string): void;
  (e: "select-line", lineId: string): void;
}>();

const mapContainer = ref<HTMLElement | null>(null);
let map: maplibregl.Map | null = null;
const isUiVisible = ref(true);
const uiPositions = reactive<Record<string, { x: number; y: number }>>({});

// --- [MapLibre 초기화 및 로직] ---
onMounted(() => {
  if (!mapContainer.value) return;

  map = new maplibregl.Map({
    container: mapContainer.value,
    style: "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json",
    center: [129.0755, 35.1785],
    zoom: 16.5,
    pitch: 60,
    bearing: -15,
    interactive: true, // 드래그/줌 허용
  });

  map.on("zoom", () => {
    isUiVisible.value = map!.getZoom() > 16.0;
  });

  map.on("load", () => {
    // 1. 소스 추가 (빈 데이터로 시작)
    map!.addSource("nodes-source", {
      type: "geojson",
      data: { type: "FeatureCollection", features: [] },
    });
    map!.addSource("lines-source", {
      type: "geojson",
      data: { type: "FeatureCollection", features: [] },
    });

    // 2. 레이어 추가 로직 (이전 턴의 3D 박스, 선 레이어 코드 그대로 삽입)
    // (코드 길이상 생략: map.addLayer({ id: "nodes-normal", ... }) 등)

    // 3. UI 위치 지속 업데이트
    map!.on("render", () => {
      if (!props.topology?.nodes) return;
      props.topology.nodes.forEach((node: any) => {
        uiPositions[node.node_id] = map!.project([
          node.position.x,
          node.position.y,
        ]);
      });
    });

    // 4. 노드 클릭 이벤트 (STD 6.3 인터랙션 구현)
    map!.on("click", "nodes-normal", (e: any) => {
      if (e.features.length > 0)
        emit("select-node", e.features[0].properties.node_id);
    });
    map!.on("click", "nodes-error", (e: any) => {
      if (e.features.length > 0)
        emit("select-node", e.features[0].properties.node_id);
    });

    // 마우스 포인터 변경
    map!.on("mouseenter", "nodes-normal", () => {
      map!.getCanvas().style.cursor = "pointer";
    });
    map!.on("mouseleave", "nodes-normal", () => {
      map!.getCanvas().style.cursor = "";
    });

    // 초기 데이터가 있으면 렌더링
    if (props.topology) updateMapData();
  });
});

onBeforeUnmount(() => {
  if (map) map.remove();
});

// --- [데이터 업데이트 로직] ---
const updateMapData = () => {
  if (!map || !props.topology) return;

  // Box Size & GeoJSON 변환 로직 (이전 답변 참고)
  const boxSize = 0.0003;
  const nodesGeoJSON = {
    /* ... */
  };
  const linesGeoJSON = {
    /* ... */
  };

  if (!map) return;

  // 2. nodes-source가 지도에 로드되어 있는지 확인 후 데이터 업데이트
  const nodesSource = map.getSource("nodes-source") as
    | maplibregl.GeoJSONSource
    | undefined;
  if (nodesSource) {
    nodesSource.setData(nodesGeoJSON as any);
  }

  // 3. lines-source가 지도에 로드되어 있는지 확인 후 데이터 업데이트
  const linesSource = map.getSource("lines-source") as
    | maplibregl.GeoJSONSource
    | undefined;
  if (linesSource) {
    linesSource.setData(linesGeoJSON as any);
  }
};

// props.topology가 변경될 때마다 맵 업데이트
watch(
  () => props.topology,
  () => {
    updateMapData();
  },
  { deep: true },
);

const getUiPosition = (id: string) => {
  const pos = uiPositions[id];
  if (!pos) return { display: "none" };
  return {
    transform: `translate(calc(${pos.x}px - 50%), calc(${pos.y}px - 100px))`,
  };
};
</script>
