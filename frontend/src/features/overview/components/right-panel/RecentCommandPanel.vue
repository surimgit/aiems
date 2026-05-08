<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useControlStore } from '@/stores/control/control.store'
import { useI18n } from 'vue-i18n'
import { useResourceAlias } from '@/features/overview/composables/useResourceAlias'
import type { LocaleType } from '@/app/i18n'
import ControlHistoryTable from './ControlHistoryTable.vue'

const controlStore = useControlStore()
const { pendingCommands, commandHistory, loading, error } = storeToRefs(controlStore)
const { t, locale } = useI18n()
const { getDisplayName } = useResourceAlias()
const viewMode = ref<'summary' | 'table'>('summary')

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

const displayedItems = computed(() => {
  return [...pendingCommands.value]
    .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
    .slice(0, 8)
})

watch(
  () => viewMode.value,
  async (mode) => {
    if (mode === 'table' && commandHistory.value.length === 0 && !loading.value) {
      try {
        await controlStore.fetchCommandHistory()
      } catch {
        // error state is handled by store
      }
    }
  }
)

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
      <button class="view-all-btn" type="button" @click="viewMode = viewMode === 'summary' ? 'table' : 'summary'">
        {{ viewMode === 'summary' ? t('recentPanel.viewAll') : t('recentPanel.viewSummary') }}
      </button>
    </div>

    <ul v-if="viewMode === 'summary' && displayedItems.length > 0" class="result-list">
      <li v-for="item in displayedItems" :key="item.command_id" class="result-row">
        <p class="command-text">{{ resolveDisplayResourceName(item.target_resource_id) }} {{ item.action }}</p>
        <div class="right-meta">
          <span class="status" :class="toResult(item.status).tone">{{ toResult(item.status).label }}</span>
          <span class="time">{{ item.created_at }}</span>
        </div>
      </li>
    </ul>

    <p v-else-if="viewMode === 'summary'" class="empty-text">{{ t('recentPanel.empty') }}</p>

    <ControlHistoryTable
      v-else
      :items="commandHistory"
      :loading="loading"
      :error="error"
    />
  </div>
</template>

<style scoped>
.panel-content {
  @apply rounded border border-slate-700 bg-slate-950/60 p-3 text-sm text-slate-300;
}

.header-row {
  @apply mb-2 flex items-center justify-between;
}

.title {
  @apply text-sm font-semibold text-slate-100;
}

.view-all-btn {
  @apply rounded border border-slate-700 px-2 py-1 text-xs text-slate-300;
}

.result-list {
  @apply space-y-1.5;
}

.result-row {
  @apply grid grid-cols-[minmax(0,1fr)_auto] items-center rounded border border-slate-800 bg-slate-900/60 px-2 py-2;
}

.command-text {
  @apply truncate pr-2 text-xs text-slate-100;
}

.right-meta {
  @apply grid grid-cols-[4.5rem_4.5rem] items-center justify-items-end gap-1 text-xs;
}

.status {
  @apply inline-block w-[4.5rem] text-right;
}

.status.success {
  @apply text-emerald-300;
}

.status.fail {
  @apply text-red-300;
}

.status.neutral {
  @apply text-slate-300;
}

.time {
  @apply inline-block w-[4.5rem] text-right text-slate-400;
}

.empty-text {
  @apply rounded border border-slate-700 bg-slate-900/50 px-3 py-3 text-xs text-slate-400;
}
</style>
