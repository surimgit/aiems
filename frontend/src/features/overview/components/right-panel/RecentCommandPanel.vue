<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useControlStore } from '@/stores/control/control.store'
import { useI18n } from 'vue-i18n'
import { useResourceAlias } from '@/features/overview/composables/useResourceAlias'
import type { LocaleType } from '@/app/i18n'
import { resolveDashboardLayoutMode } from '@/features/overview/layoutPresets'
import ControlHistoryTable from './ControlHistoryTable.vue'

const emit = defineEmits<{
  (e: 'open-resource', resourceId: string): void
}>()

const controlStore = useControlStore()
const { commandHistory, loading, error, operatorId } = storeToRefs(controlStore)
const { t, locale } = useI18n()
const { getDisplayName } = useResourceAlias()
const viewportWidth = ref(typeof window !== 'undefined' ? window.innerWidth : 1920)
const tablePage = ref(1)

const tablePageSize = computed(() => {
  const mode = resolveDashboardLayoutMode(viewportWidth.value)
  if (mode === 'tablet') return 5
  if (mode === 'wall') return 10
  return 8
})

const operatorCommandHistory = computed(() =>
  commandHistory.value.filter((item) => item.issued_by !== 'rule')
)

const totalPages = computed(() =>
  Math.max(1, Math.ceil(operatorCommandHistory.value.length / tablePageSize.value))
)

const hasNextPage = computed(() => tablePage.value < totalPages.value)

const visibleCommandHistory = computed(() => {
  const start = (tablePage.value - 1) * tablePageSize.value
  return operatorCommandHistory.value.slice(start, start + tablePageSize.value)
})

const statusToneMap: Record<string, 'success' | 'fail' | 'neutral'> = {
  ACCEPTED: 'success',
  COMPLETED: 'success',
  RUNNING: 'neutral',
  CREATED: 'neutral',
  REJECTED: 'fail',
  FAILED: 'fail',
  BLOCKED: 'fail',
  EXPIRED: 'fail',
  TIMED_OUT: 'fail'
}

const loadTablePage = async (page: number) => {
  tablePage.value = Math.max(1, page)
  try {
    await controlStore.fetchCommandHistory({ page: 1, page_size: 200 })
  } catch {
    // error state is handled by store
  }
}

const movePrevPage = async () => {
  if (tablePage.value <= 1 || loading.value) return
  await loadTablePage(tablePage.value - 1)
}

const moveNextPage = async () => {
  if (!hasNextPage.value || loading.value) return
  await loadTablePage(tablePage.value + 1)
}

const pageLabel = computed(() => `${tablePage.value}`)

const onResize = () => {
  viewportWidth.value = window.innerWidth
}

onMounted(async () => {
  window.addEventListener('resize', onResize)
  await loadTablePage(1)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize)
})

watch(tablePageSize, () => {
  tablePage.value = 1
})

const resolveDisplayResourceName = (resourceId: string): string =>
  getDisplayName(resourceId, resourceId, locale.value as LocaleType)

const toResult = (status: string) => {
  const tone = statusToneMap[status] ?? 'neutral'
  if (tone === 'success') return { label: t('recentPanel.status.success'), tone }
  if (status === 'RUNNING') return { label: t('recentPanel.status.running'), tone }
  if (status === 'CREATED') return { label: t('recentPanel.status.created'), tone }
  if (status === 'BLOCKED') return { label: t('recentPanel.status.blocked'), tone }
  if (status === 'EXPIRED') return { label: t('recentPanel.status.expired'), tone }
  if (status === 'TIMED_OUT') return { label: t('recentPanel.status.timeout'), tone }
  if (tone === 'fail') return { label: t('recentPanel.status.fail'), tone }
  return { label: status, tone }
}
</script>

<template>
  <div class="panel-content">
    <div class="header-row">
      <p class="title">{{ t('recentPanel.title') }}</p>
    </div>

    <ControlHistoryTable
      :items="visibleCommandHistory"
      :loading="loading"
      :error="error"
      @open-resource="emit('open-resource', $event)"
    />

    <div class="pager-row">
      <button class="pager-btn" type="button" :disabled="tablePage <= 1 || loading" @click="movePrevPage">
        이전
      </button>
      <span class="pager-index">{{ pageLabel }}</span>
      <button class="pager-btn" type="button" :disabled="!hasNextPage || loading" @click="moveNextPage">
        다음
      </button>
    </div>
  </div>
</template>

<style scoped>
.panel-content {
  @apply rounded border border-slate-700 bg-slate-950/60 p-3 text-sm text-slate-300;
}

.header-row {
  @apply mb-2 flex items-center justify-start;
}

.title {
  @apply text-sm font-semibold text-slate-100;
}

.pager-row {
  @apply mt-3 flex items-center justify-center gap-2;
}

.pager-btn {
  @apply rounded border border-slate-700 px-2 py-1 text-xs text-slate-300 disabled:cursor-not-allowed disabled:opacity-40;
}

.pager-index {
  @apply min-w-14 text-center text-xs text-slate-300;
}
</style>
