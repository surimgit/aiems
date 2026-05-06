<script setup lang="ts">
import type { KpiSummaryItem } from '../index'

defineProps<{
  items: KpiSummaryItem[]
}>()

const iconByKey: Record<NonNullable<KpiSummaryItem['icon']>, string> = {
  generation: '⚡',
  consumption: '📊',
  selfSufficiency: '◔',
  saving: '₩'
}

const getDeltaClass = (direction?: KpiSummaryItem['deltaDirection']): string => {
  if (direction === 'up') return 'delta-up'
  if (direction === 'down') return 'delta-down'
  return 'delta-neutral'
}
</script>

<template>
  <section class="panel-card">
    <h3 class="title">KPI 요약 <span class="sub-title">(이번 달)</span></h3>
    <div class="kpi-grid">
      <article v-for="item in items" :key="item.id" class="kpi-card">
        <header class="kpi-card-header">
          <span class="icon" :class="item.icon">{{ item.icon ? iconByKey[item.icon] : '•' }}</span>
          <p class="label">{{ item.label }}</p>
        </header>

        <p class="value">
          {{ item.value }}
          <span v-if="item.unit" class="unit">{{ item.unit }}</span>
        </p>

        <p v-if="item.deltaText" class="delta" :class="getDeltaClass(item.deltaDirection)">
          {{ item.deltaText }}
        </p>
        <p v-if="item.subText" class="sub">{{ item.subText }}</p>
      </article>
    </div>
  </section>
</template>

<style scoped>
.panel-card {
  @apply rounded border border-slate-700 bg-slate-900/80 p-3 text-slate-100;
}

.title {
  @apply mb-2 font-semibold text-sm;
}

.sub-title {
  @apply ml-1 text-xs font-normal text-slate-400;
}

.kpi-grid {
  @apply grid grid-cols-2 gap-1.5;
}

.kpi-card {
  @apply rounded border border-slate-700 bg-slate-950/60 p-2;
}

.kpi-card-header {
  @apply mb-1 flex items-center gap-1.5;
}

.icon {
  @apply inline-flex h-4 w-4 items-center justify-center rounded-sm text-[10px] text-slate-200;
}

.icon.generation,
.icon.consumption,
.icon.selfSufficiency,
.icon.saving {
  @apply bg-slate-800;
}

.label {
  @apply text-[11px] text-slate-400;
}

.value {
  @apply text-sm font-semibold text-slate-100;
}

.unit {
  @apply ml-1 text-[11px] font-normal text-slate-300;
}

.delta {
  @apply mt-1 text-[11px] font-medium;
}

.delta-up {
  @apply text-cyan-300;
}

.delta-down {
  @apply text-amber-300;
}

.delta-neutral {
  @apply text-slate-400;
}

.sub {
  @apply mt-1 text-[10px] text-slate-500;
}
</style>
