<script setup lang="ts">
import { computed } from 'vue'
import { storeToRefs } from 'pinia'
import { useDashboardStore } from '@/stores/dashboard/dashboard.store'

const dashboardStore = useDashboardStore()
const { powerSummary } = storeToRefs(dashboardStore)

const points = computed(() => {
  if (!powerSummary.value) return []
  return [
    { label: 'PV', value: powerSummary.value.pv_power_kw },
    { label: 'ESS', value: powerSummary.value.ess_power_kw },
    { label: 'Grid', value: powerSummary.value.grid_power_kw },
    { label: 'Load', value: powerSummary.value.load_power_kw },
    { label: 'Net', value: powerSummary.value.net_power_kw }
  ]
})
</script>

<template>
  <section class="panel-card">
    <h3 class="title">전력 밸런스 추이</h3>
    <div v-if="points.length > 0" class="chart-placeholder">
      <div v-for="point in points" :key="point.label" class="row">
        <span>{{ point.label }}</span>
        <span>{{ point.value.toFixed(1) }} kW</span>
      </div>
    </div>
    <div v-else class="chart-placeholder">전력 요약 데이터가 아직 없습니다.</div>
  </section>
</template>

<style scoped>
.panel-card {
  @apply rounded border border-slate-700 bg-slate-900/80 p-4 text-slate-100;
}

.title {
  @apply font-semibold mb-3;
}

.chart-placeholder {
  @apply h-40 rounded border border-slate-700 bg-slate-950/60 p-3 text-sm text-slate-400;
}

.row {
  @apply flex items-center justify-between border-b border-slate-800 py-1 last:border-b-0;
}
</style>
