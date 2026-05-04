<script setup lang="ts">
import { storeToRefs } from 'pinia'
import { useDashboardStore } from '@/stores/dashboard/dashboard.store'

const dashboardStore = useDashboardStore()
const { selectedEss } = storeToRefs(dashboardStore)
</script>

<template>
  <div class="panel-content">
    <template v-if="selectedEss">
      <p class="title">{{ selectedEss.name || selectedEss.ess_id }}</p>
      <dl class="grid grid-cols-2 gap-2 text-xs text-slate-300">
        <dt>ESS ID</dt><dd>{{ selectedEss.ess_id }}</dd>
        <dt>SOC</dt><dd>{{ selectedEss.soc }}%</dd>
        <dt>SOH</dt><dd>{{ selectedEss.soh ?? '-' }}%</dd>
        <dt>상태</dt><dd>{{ selectedEss.status }}</dd>
        <dt>용량</dt><dd>{{ selectedEss.capacity_kwh }} kWh</dd>
        <dt>최대출력</dt><dd>{{ selectedEss.max_power_kw }} kW</dd>
      </dl>
    </template>
    <p v-else class="text-sm text-slate-400">토폴로지에서 ESS 노드를 선택하세요.</p>
  </div>
</template>

<style scoped>
.panel-content {
  @apply rounded border border-slate-700 bg-slate-950/60 p-3 text-sm text-slate-300;
}

.title {
  @apply mb-3 text-sm font-semibold text-slate-100;
}
</style>
