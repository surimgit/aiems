<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from "vue";
import { useOverviewFeature } from "@/features/overview";
import { useTopologyFeature } from "@/features/topology";
import { useForecastFeature } from "@/features/forecast";
import { buildKpiSummary } from "@/features/kpi";

// Components
import TopBarKpiStrip from "@/features/overview/components/TopBarKpiStrip.vue";
import DashboardShell from "@/features/overview/components/DashboardShell.vue";
import TopologyStage from "@/features/topology/components/TopologyStage.vue";
import TopologyLegend from "@/features/topology/components/TopologyLegend.vue";
import TopologyNodeLayer from "@/features/topology/components/TopologyNodeLayer.vue";
import TopologyLineLayer from "@/features/topology/components/TopologyLineLayer.vue";
import PowerBalanceChart from "@/features/forecast/components/PowerBalanceChart.vue";
import KpiSummaryWidget from "@/features/kpi/components/KpiSummaryWidget.vue";
import AiPerformanceWidget from "@/features/overview/components/AiPerformanceWidget.vue";

// Right Panel Components
import RightPanelShell from "@/features/overview/components/right-panel/RightPanelShell.vue";
import AlarmTopPanel from "@/features/overview/components/right-panel/AlarmTopPanel.vue";
import RecentCommandPanel from "@/features/overview/components/right-panel/RecentCommandPanel.vue";
import CountryLanguagePanel from "@/features/overview/components/right-panel/CountryLanguagePanel.vue";
import SelectedResourceInfoPanel from "@/features/overview/components/right-panel/SelectedResourceInfoPanel.vue";
import ControlPanel from "@/features/overview/components/right-panel/ControlPanel.vue";
import LoadUsagePanel from "@/features/overview/components/right-panel/LoadUsagePanel.vue";

// Composables
import { useRightPanelState } from "@/features/overview/composables/useRightPanelState";
import { useDashboardLayout } from "@/features/overview/composables/useDashboardLayout";
import type { RightPanelMode } from "@/features/overview/types";

// Features & State
const { powerSummary, activeAlarms, initialize } = useOverviewFeature();
const topologyFeature = useTopologyFeature();
const { topology } = topologyFeature;
const forecastFeature = useForecastFeature();

const kpiItems = computed(() =>
  buildKpiSummary(powerSummary.value, activeAlarms.value.length),
);

const viewportWidth = ref(
  typeof window !== "undefined" ? window.innerWidth : 1920,
);
const rightPanel = useRightPanelState();
const { mode } = useDashboardLayout(
  () => viewportWidth.value,
  () => rightPanel.isOpen.value,
);

const selectedNodeId = ref<string>("");

// ✅ 알람, 선택장비 등 모드에 따라 우측 패널 제목을 하나로 통합
const rightPanelTitle = computed(() => {
  if (rightPanel.mode.value === "selected-resource")
    return `선택 장비: ${selectedNodeId.value}`;
  if (rightPanel.mode.value === "alarm") return "시스템 알람 (Top 3)";

  const titleMap: Record<string, string> = {
    "recent-command": "최근 명령 결과",
    "country-language": "국가 선택",
    control: "설비 제어",
    "load-usage": "소비처별 전력 사용 현황",
  };
  return titleMap[rightPanel.mode.value as string] || "상세 패널";
});

const onResize = () => {
  viewportWidth.value = window.innerWidth;
};

// 상단 아이콘 클릭 시
const handleModeToggle = (mode: string) => {
  if (rightPanel.mode.value === mode && rightPanel.isOpen.value) {
    rightPanel.close();
  } else {
    rightPanel.open(mode as RightPanelMode);
  }
};

// 3D 지도에서 노드(장비)를 클릭했을 때
const handleSelectNode = (nodeId: string) => {
  selectedNodeId.value = nodeId;
  topologyFeature.selectNode(nodeId);
  rightPanel.open("selected-resource");
};

onMounted(async () => {
  window.addEventListener("resize", onResize);
  await initialize();
  await Promise.all([
    topologyFeature.initialize(),
    forecastFeature.fetchForecasts(),
  ]);
});

onUnmounted(() => {
  window.removeEventListener("resize", onResize);
});
</script>

<template>
  <div class="overview-page h-screen w-full bg-slate-900">
    <DashboardShell :mode="mode" :panel-open="rightPanel.isOpen.value">
      <!-- 상단 헤더 -->
      <template #topbar>
        <TopBarKpiStrip
          :power-summary="powerSummary"
          :active-alarm-count="activeAlarms.length"
          :current-mode="rightPanel.mode.value"
          :panel-open="rightPanel.isOpen.value"
          @toggle-mode="handleModeToggle"
        />
      </template>

      <!-- 메인 토폴로지 구역 -->
      <template #topology>
        <TopologyStage :topology="topology" @select-node="handleSelectNode" />
      </template>

      <!-- 범례 구역 -->
      <template #overlay v-if="rightPanel.isOpen.value">
        <TopologyLegend />
      </template>

      <!-- 하단 3패널 구역 -->
      <template #power-balance>
        <PowerBalanceChart :series="[]" />
      </template>
      <template #kpi-summary>
        <KpiSummaryWidget :items="[]" />
      </template>
      <template #ai-performance>
        <AiPerformanceWidget :target="100" :actual="0" :rate="0" />
      </template>

      <!-- 🚨 문제 해결: 우측 패널 구역 렌더링 조건 완벽 분기 -->
      <template #right-panel>
        <!-- 1. 패널이 '열림' 상태일 때만 Shell 자체를 렌더링 -->
        <RightPanelShell
          v-if="rightPanel.isOpen.value"
          :title="rightPanelTitle"
          @close="rightPanel.close"
        >
          <AlarmTopPanel v-if="rightPanel.mode.value === 'alarm'" />
          <RecentCommandPanel
            v-else-if="rightPanel.mode.value === 'recent-command'"
          />
          <CountryLanguagePanel
            v-else-if="rightPanel.mode.value === 'country-language'"
          />
          <ControlPanel v-else-if="rightPanel.mode.value === 'control'" />
          <LoadUsagePanel v-else-if="rightPanel.mode.value === 'load-usage'" />

          <!-- 2. v-else 대신 명확한 조건(v-else-if) 부여 및 ID 텍스트와 통합 -->
          <template v-else-if="rightPanel.mode.value === 'selected-resource'">
            <div class="text-white p-4 border-b border-slate-700">
              선택된 장비 ID: {{ selectedNodeId }}
            </div>
            <SelectedResourceInfoPanel />
          </template>
        </RightPanelShell>
      </template>
    </DashboardShell>
  </div>
</template>

<style scoped>
.overview-page {
  @apply h-full min-h-0 overflow-y-auto overflow-x-hidden bg-slate-950;
}
</style>
