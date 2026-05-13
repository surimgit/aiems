<script setup lang="ts">
import { computed, ref } from 'vue'
import { storeToRefs } from 'pinia'
import { useDashboardStore } from '@/stores/dashboard/dashboard.store'
import { useI18n } from 'vue-i18n'

const props = withDefaults(defineProps<{
  topOnly?: boolean
}>(), {
  topOnly: true
})

const dashboardStore = useDashboardStore()
const { resources, selectedResource } = storeToRefs(dashboardStore)
const { t } = useI18n()

const expanded = ref(false)

const loadItems = computed(() => {
  const loads = resources.value
    .filter((item) => item.resource_type === 'LOAD')
    .map((item) => ({
      id: item.resource_id,
      name: item.name || item.resource_id,
      usagePercent: Number(item.telemetry?.p_kw ?? 0)
    }))

  if (loads.length === 0) {
    return [
      { id: 'load-1', name: t('selectedResource.loadUsage.fallback.loadCenter', { index: '3-1' }), usagePercent: 120 },
      { id: 'load-2', name: t('selectedResource.loadUsage.fallback.loadCenter', { index: '3-2' }), usagePercent: 85 },
      { id: 'load-3', name: t('selectedResource.loadUsage.fallback.loadCenter', { index: '3-3' }), usagePercent: 60 }
    ]
  }

  const maxUsage = Math.max(...loads.map((item) => item.usagePercent), 1)
  return loads.map((item) => ({
    ...item,
    usagePercent: Math.round((item.usagePercent / maxUsage) * 120)
  }))
})

const visibleItems = computed(() => {
  const sorted = [...loadItems.value].sort((a, b) => b.usagePercent - a.usagePercent)
  if (!props.topOnly || expanded.value) return sorted
  return sorted.slice(0, 3)
})

const isLoadSelected = computed(() => selectedResource.value?.resource_type === 'LOAD')

const usageClass = (usagePercent: number) => {
  if (usagePercent > 100) return 'critical'
  if (usagePercent >= 90) return 'warning'
  return 'normal'
}
</script>

<template>
  <div class="panel-content" v-if="isLoadSelected">
    <div class="header-row">
      <p class="title">{{ t('selectedResource.loadUsage.title') }}</p>
      <button
        v-if="topOnly"
        type="button"
        class="toggle-btn"
        @click="expanded = !expanded"
      >
        {{ expanded ? t('selectedResource.loadUsage.collapse') : t('selectedResource.loadUsage.expand') }}
      </button>
    </div>

    <div class="list-wrap">
      <div v-for="item in visibleItems" :key="item.id" class="usage-row">
        <p class="name">{{ item.name }}</p>
        <div class="bar-wrap">
          <div class="bar" :class="usageClass(item.usagePercent)" :style="{ width: `${Math.min(item.usagePercent, 140)}%` }" />
        </div>
        <p class="percent" :class="usageClass(item.usagePercent)">{{ item.usagePercent }}%</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.panel-content {
  @apply rounded border border-slate-700 bg-slate-950/60 p-3 text-sm text-slate-300;
}

.header-row {
  @apply mb-2 flex items-center justify-between gap-2;
}

.title {
  @apply text-xs font-semibold text-slate-200;
}

.toggle-btn {
  @apply rounded border border-slate-600 px-2 py-1 text-[10px] text-slate-300;
}

.list-wrap {
  @apply space-y-2;
}

.usage-row {
  @apply grid grid-cols-[1fr_2.6fr_auto] items-center gap-2;
}

.name {
  @apply truncate text-xs text-slate-300;
}

.bar-wrap {
  @apply h-2 rounded bg-slate-800;
}

.bar {
  @apply h-full rounded;
}

.percent {
  @apply text-xs;
}

.normal {
  @apply text-cyan-300 bg-cyan-300/80;
}

.warning {
  @apply text-amber-300 bg-amber-300/80;
}

.critical {
  @apply text-red-300 bg-red-300/80;
}

.percent.normal,
.percent.warning,
.percent.critical {
  background: transparent;
}
</style>
