<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
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
import { useOverviewPolling } from '@/features/overview/composables/useOverviewPolling'
import type { RightPanelMode } from '@/features/overview/types'

const { powerSummary, activeAlarms, initialize } = useOverviewFeature()
const { t } = useI18n()
const topologyFeature = useTopologyFeature()
const forecastFeature = useForecastFeature()
const overviewPolling = useOverviewPolling()
const kpiItems = computed(() => buildKpiSummary(powerSummary.value, activeAlarms.value.length))

const viewportWidth = ref(typeof window !== 'undefined' ? window.innerWidth : 1920)
const rightPanel = useRightPanelState()
const isMapExpanded = ref(false)
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
    alarm: t('rightPanel.alarmTop3'),
    'recent-command': t('rightPanel.recentCommand'),
    'country-language': t('rightPanel.countryLanguage'),
    'selected-resource': t('rightPanel.selectedResource'),
    control: t('rightPanel.control'),
    'load-usage': t('rightPanel.loadUsage')
  }

  if (!rightPanel.mode.value) return t('rightPanel.defaultTitle')
  return titleMap[rightPanel.mode.value]
})

onMounted(async () => {
  window.addEventListener('resize', onResize)
  window.addEventListener('keydown', onKeydown)

  await initialize()
  await Promise.all([topologyFeature.initialize(), forecastFeature.fetchForecasts()])
  overviewPolling.start()
})

onUnmounted(() => {
  overviewPolling.stop()
  window.removeEventListener('resize', onResize)
  window.removeEventListener('keydown', onKeydown)
})
</script>

<template>
  <div class="overview-page">
    <DashboardShell :mode="mode" :panel-open="rightPanel.isOpen.value" :map-expanded="isMapExpanded">
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
        <div class="topology-wrap">
          <TopologyStage :topology="topologyFeature.topology.value" @select-node="handleSelectNode">
            <template #svg>
              <TopologyLineLayer :lines="topologyFeature.topology.value?.lines ?? []" />
              <TopologyNodeLayer :nodes="topologyFeature.topology.value?.nodes ?? []" @select-node="handleSelectNode" />
            </template>
            <template #overlay>
              <TopologyLegend />
            </template>
          </TopologyStage>
          <button
            type="button"
            class="map-expand-btn"
            @click="isMapExpanded = !isMapExpanded"
            :aria-label="isMapExpanded ? '지도 축소' : '지도 확장'"
          >
            {{ isMapExpanded ? '⤡' : '⤢' }}
          </button>
        </div>
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

.topology-wrap {
  @apply relative h-full min-h-0;
}

.map-expand-btn {
  @apply absolute bottom-3 right-3 z-20 rounded border border-white/20 bg-slate-900/80 px-2 py-1 text-sm text-white backdrop-blur;
}
</style>
