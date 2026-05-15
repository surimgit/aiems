<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute } from 'vue-router'
import { useDashboardStore } from '@/stores/dashboard/dashboard.store'
import { useOverviewFeature } from '@/features/overview'
import { useTopologyFeature } from '@/features/topology'
import { buildKpiSummary } from '@/features/kpi'
import TopBarKpiStrip from '@/features/overview/components/TopBarKpiStrip.vue'
import AnomalyAlertBanner from '@/features/overview/components/AnomalyAlertBanner.vue'
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
import SettingsPanel from '@/features/overview/components/right-panel/SettingsPanel.vue'
import SelectedResourceIntegratedPanel from '@/features/overview/components/right-panel/SelectedResourceIntegratedPanel.vue'
import LoadUsagePanel from '@/features/overview/components/right-panel/LoadUsagePanel.vue'
import { useRightPanelState } from '@/features/overview/composables/useRightPanelState'
import { useDashboardLayout } from '@/features/overview/composables/useDashboardLayout'
import { useOverviewPolling } from '@/features/overview/composables/useOverviewPolling'
import { useForecastFeature } from '@/features/forecast'
import { useCommandStatusPoller } from '@/features/overview/composables/useCommandStatusPoller'
import type { RightPanelMode } from '@/features/overview/types'

const { powerSummary, activeAlarms, resources, initialize } = useOverviewFeature()
const { t } = useI18n()
const topologyFeature = useTopologyFeature()
const overviewPolling = useOverviewPolling()
const forecastFeature = useForecastFeature()
useCommandStatusPoller()
const dashboardStore = useDashboardStore()
const route = useRoute()
const kpiItems = computed(() => buildKpiSummary(powerSummary.value, resources.value, activeAlarms.value.length))

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
  if (!nodeId) {
    dashboardStore.selectEss(null)
    if (rightPanel.mode.value === 'selected-resource') {
      rightPanel.close()
    }
    return
  }
  topologyFeature.selectNode(nodeId)
  rightPanel.open('selected-resource')
}

const handleSelectLine = (lineId: string) => {
  if (!lineId) {
    dashboardStore.selectEss(null)
    if (rightPanel.mode.value === 'selected-resource') {
      rightPanel.close()
    }
    return
  }
  topologyFeature.selectLine(lineId)
  rightPanel.open('selected-resource')
}

const handleOpenResourceFromBanner = (resourceId: string) => {
  topologyFeature.selectNode(resourceId)
  rightPanel.open('selected-resource')
}

const handleOpenResourceFallbackFromBanner = () => {
  const candidate = dashboardStore.resources[0]?.resource_id
  if (candidate) {
    topologyFeature.selectNode(candidate)
  }
  rightPanel.open('selected-resource')
}

const rightPanelTitle = computed(() => {
  const titleMap: Record<RightPanelMode, string> = {
    alarm: t('rightPanel.alarmTop3'),
    'recent-command': t('rightPanel.recentCommand'),
    'country-language': t('rightPanel.countryLanguage'),
    settings: t('rightPanel.settings'),
    'selected-resource': t('rightPanel.selectedResource'),
    'load-usage': t('rightPanel.loadUsage')
  }

  if (!rightPanel.mode.value) return t('rightPanel.defaultTitle')
  return titleMap[rightPanel.mode.value]
})

// AI 예측은 최초 1회 + 10분 주기 갱신 (100ms 폴링에 넣으면 요청 폭탄)
const FORECAST_INTERVAL_MS = 10 * 60 * 1000
let forecastIntervalId: ReturnType<typeof setInterval> | null = null

onMounted(async () => {
  window.addEventListener('resize', onResize)
  window.addEventListener('keydown', onKeydown)

  await initialize()
  await topologyFeature.initialize()
  if (route.query.panel === 'alarm') {
    rightPanel.open('alarm')
  }
  overviewPolling.start()

  // AI 예측 최초 1회 호출 (비동기 - 실패해도 페이지 초기화 지연 없음)
  forecastFeature.fetchForecasts()
  forecastIntervalId = setInterval(() => {
    forecastFeature.fetchForecasts()
  }, FORECAST_INTERVAL_MS)
})

onUnmounted(() => {
  overviewPolling.stop()
  if (forecastIntervalId !== null) {
    clearInterval(forecastIntervalId)
    forecastIntervalId = null
  }
  window.removeEventListener('resize', onResize)
  window.removeEventListener('keydown', onKeydown)
})
</script>

<template>
  <div class="overview-page">
    <DashboardShell :mode="mode" :panel-open="rightPanel.isOpen.value" :map-expanded="isMapExpanded">
      <template #topbar>
        <div class="topbar-stack">
          <TopBarKpiStrip
            :power-summary="powerSummary"
            :active-alarm-count="activeAlarms.length"
            :current-mode="rightPanel.mode.value"
            :panel-open="rightPanel.isOpen.value"
            @toggle-mode="handleTopbarMode"
          />
          <AnomalyAlertBanner
            :active-alarms="activeAlarms"
            @open-alarm-panel="handleOpenResourceFallbackFromBanner"
            @open-resource="handleOpenResourceFromBanner"
          />
        </div>
      </template>

      <template #topology>
        <div class="topology-wrap">
          <TopologyStage
            :topology="topologyFeature.topology.value"
            :resources="resources"
            :resources-last-fetched-at="dashboardStore.resourcesLastFetchedAt"
            :topology-last-fetched-at="dashboardStore.topologyLastFetchedAt"
            :resources-fetch-fail-streak="dashboardStore.resourcesFetchFailStreak"
            :topology-fetch-fail-streak="dashboardStore.topologyFetchFailStreak"
            @select-node="handleSelectNode"
            @select-line="handleSelectLine"
          >
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
          <AlarmTopPanel v-if="rightPanel.mode.value === 'alarm'" @open-resource="handleOpenResourceFromBanner" />
          <RecentCommandPanel v-else-if="rightPanel.mode.value === 'recent-command'" @open-resource="handleOpenResourceFromBanner" />
          <SettingsPanel v-else-if="rightPanel.mode.value === 'settings'" />
          <SelectedResourceIntegratedPanel v-else-if="rightPanel.mode.value === 'selected-resource'" />
          <LoadUsagePanel v-else-if="rightPanel.mode.value === 'load-usage'" />
        </RightPanelShell>
      </template>
    </DashboardShell>
  </div>
</template>

<style scoped>
.overview-page {
  @apply h-full min-h-0 overflow-y-scroll overflow-x-hidden bg-slate-950;
}

.topology-wrap {
  @apply relative h-full min-h-0;
}

.topbar-stack {
  @apply space-y-2;
}

.map-expand-btn {
  @apply absolute bottom-3 right-3 z-20 rounded border border-white/20 bg-slate-900/80 px-2 py-1 text-sm text-white backdrop-blur;
}
</style>
