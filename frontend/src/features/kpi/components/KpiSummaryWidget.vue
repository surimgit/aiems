<script setup lang="ts">
import type { KpiSummaryItem } from '../index'

defineProps<{
  items: KpiSummaryItem[]
}>()
</script>

<template>
  <section class="panel-card">
    <h3 class="title">KPI 요약</h3>
    <div class="grid grid-cols-2 gap-2">
      <article v-for="item in items" :key="item.id" class="kpi-card">
        <p class="text-xs text-slate-400">{{ item.label }}</p>
        <p class="text-lg text-slate-100">{{ item.value }}</p>
      </article>
    </div>
  </section>
</template>

<style scoped>
.panel-card {
  @apply rounded border border-slate-700 bg-slate-900/80 p-4 text-slate-100;
}

.title {
  @apply font-semibold mb-3;
}

.kpi-card {
  @apply rounded border border-slate-700 bg-slate-950/60 p-3;
}
</style>
