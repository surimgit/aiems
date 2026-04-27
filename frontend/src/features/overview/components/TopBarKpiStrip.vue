<script setup lang="ts">
import type { PowerSummary } from '@/types/common'

defineProps<{
  powerSummary: PowerSummary | null
  activeAlarmCount: number
}>()
</script>

<template>
  <section class="topbar-kpi-strip">
    <slot />
    <div class="kpi-placeholder">Net / SOC / Alarm KPI strip</div>
  </section>
</template>

<style scoped>
.topbar-kpi-strip {
  @apply grid grid-cols-1 md:grid-cols-3 xl:grid-cols-6 gap-3;
}

.kpi-placeholder {
  @apply rounded border border-slate-700 p-3 text-slate-200;
}
</style>
