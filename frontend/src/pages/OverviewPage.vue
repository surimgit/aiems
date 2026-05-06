<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useOverviewFeature } from '@/features/overview'
import { useTopologyFeature } from '@/features/topology'
import { useForecastFeature } from '@/features/forecast'
import { buildKpiSummary } from '@/features/kpi'
import TopBarKpiStrip from '@/features/overview/components/TopBarKpiStrip.vue'
import DashboardShell from '@/features/overview/components/DashboardShell.vue'
import TopologyStage from '@/features/topology/components/TopologyStage.vue'
import TopologyLegend from '@/features/topology/components/TopologyLegend.vue'
import TopologyNodeLayer from '@/features/topology/components/TopologyNodeLayer.vue'
import TopologyLineLayer from '@/features/topology/components/TopologyLineLayer.vue'
import PowerBalanceChart from '@/features/forecast/components/PowerBalanceChart.vue'
import KpiSummaryWidget from '@/features/kpi/components/KpiSummaryWidget.vue'
import AiPerformanceWidget from '@/features/overview/components/AiPerformanceWidget.vue'
import RightPanelShell from '@/features/overview/components/right-panel/RightPanelShell.vue'
import AlarmTopPanel from '@/features/overview/components/right-panel/AlarmTopPanel.vue'
import RecentCommandPanel from '@/features/overview/components/right-panel/RecentCommandPanel.vue'
import CountryLanguagePanel from '@/features/overview/components/right-panel/CountryLanguagePanel.vue'
import SelectedResourceIntegratedPanel from '@/features/overview/components/right-panel/SelectedResourceIntegratedPanel.vue'
import ControlPanel from '@/features/overview/components/right-panel/ControlPanel.vue'
import LoadUsagePanel from '@/features/overview/components/right-panel/LoadUsagePanel.vue'
import { useRightPanelState } from '@/features/overview/composables/useRightPanelState'
import { useDashboardLayout } from '@/features/overview/composables/useDashboardLayout'
import type { RightPanelMode } from '@/features/overview/types'

const { powerSummary, activeAlarms, initialize } = useOverviewFeature()
const topologyFeature = useTopologyFeature()
const forecastFeature = useForecastFeature()
const kpiItems = computed(() => buildKpiSummary(powerSummary.value, activeAlarms.value.length))

const viewportWidth = ref(typeof window !== 'undefined' ? window.innerWidth : 1920)
const rightPanel = useRightPanelState()
const { mode } = useDashboardLayout(() => viewportWidth.value, () => rightPanel.isOpen.value)

const onResize = () => {
  viewportWidth.value = window.innerWidth
}

const onKeydown = (event: KeyboardEvent) => {
  if (event.key === 'Escape' && rightPanel.isOpen.value) {
    rightPanel.close()
    const activeElement = document.activeElement
    if (activeElement instanceof HTMLElement) {
      activeElement.blur()
    }
  }
}

const handleTopbarMode = (nextMode: RightPanelMode) => {
  rightPanel.toggle(nextMode)
}

const handleSelectNode = (nodeId: string) => {
  topologyFeature.selectNode(nodeId)
  rightPanel.open('selected-resource')
}

const rightPanelTitle = computed(() => {
  const titleMap: Record<RightPanelMode, string> = {
    alarm: '알람 (Top 3)',
    'recent-command': '최근 명령 결과',
    'country-language': '국가 선택',
    'selected-resource': '선택된 장비 정보',
    control: '설비 제어',
    'load-usage': '소비처별 전력 사용 현황'
  }

  if (!rightPanel.mode.value) return '패널'
  return titleMap[rightPanel.mode.value]
})

onMounted(async () => {
  window.addEventListener('resize', onResize)
  window.addEventListener('keydown', onKeydown)

  await initialize()
  await Promise.all([topologyFeature.initialize(), forecastFeature.fetchForecasts()])
})

onUnmounted(() => {
  window.removeEventListener('resize', onResize)
  window.removeEventListener('keydown', onKeydown)
})
</script>

<template>
  <div class="overview-page">
    <DashboardShell :mode="mode" :panel-open="rightPanel.isOpen.value">
      <template #topbar>
        <TopBarKpiStrip
          :power-summary="powerSummary"
          :active-alarm-count="activeAlarms.length"
          :current-mode="rightPanel.mode.value"
          :panel-open="rightPanel.isOpen.value"
          @toggle-mode="handleTopbarMode"
        />
      </template>

      <template #topology>
        <TopologyStage :topology="topologyFeature.topology.value" @select-node="handleSelectNode">
          <template #svg>
            <TopologyLineLayer :lines="topologyFeature.topology.value?.lines ?? []" />
            <TopologyNodeLayer :nodes="topologyFeature.topology.value?.nodes ?? []" @select-node="handleSelectNode" />
          </template>
          <template #overlay>
            <TopologyLegend />
          </template>
        </TopologyStage>
      </template>

      <template #power-balance>
        <PowerBalanceChart />
      </template>

      <template #kpi-summary>
        <KpiSummaryWidget :items="kpiItems" />
      </template>

      <template #ai-performance>
        <AiPerformanceWidget />
      </template>

      <template #right-panel>
        <RightPanelShell :title="rightPanelTitle" @close="rightPanel.close">
          <AlarmTopPanel v-if="rightPanel.mode.value === 'alarm'" />
          <RecentCommandPanel v-else-if="rightPanel.mode.value === 'recent-command'" />
          <CountryLanguagePanel v-else-if="rightPanel.mode.value === 'country-language'" />
          <SelectedResourceIntegratedPanel v-else-if="rightPanel.mode.value === 'selected-resource'" />
          <ControlPanel v-else-if="rightPanel.mode.value === 'control'" />
          <LoadUsagePanel v-else-if="rightPanel.mode.value === 'load-usage'" />
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
