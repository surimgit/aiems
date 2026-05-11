import type { Component } from 'vue'
import { FEATURE_KEYS, type FeatureKey } from '@/domain/scenario/featureFlags'

import PowerBalanceChart from '@/features/forecast/components/PowerBalanceChart.vue'
import KpiSummaryWidget from '@/features/kpi/components/KpiSummaryWidget.vue'
import AiPerformanceWidget from '@/features/overview/components/AiPerformanceWidget.vue'

export const widgetRegistry: Partial<Record<FeatureKey, Component>> = {
  [FEATURE_KEYS.FORECAST]: PowerBalanceChart,
  [FEATURE_KEYS.KPI]: KpiSummaryWidget,
  [FEATURE_KEYS.AI_PERFORMANCE]: AiPerformanceWidget
}
