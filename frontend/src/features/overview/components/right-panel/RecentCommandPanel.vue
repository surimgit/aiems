<script setup lang="ts">
import { computed } from 'vue'
import { storeToRefs } from 'pinia'
import { useControlStore } from '@/stores/control/control.store'
import { useI18n } from 'vue-i18n'
import { useResourceAlias } from '@/features/overview/composables/useResourceAlias'
import type { LocaleType } from '@/app/i18n'

const controlStore = useControlStore()
const { pendingCommands } = storeToRefs(controlStore)
const { t, locale } = useI18n()
const { getDisplayName } = useResourceAlias()

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

const fallbackItems = [
  { command_id: 'cmd-1', action: 'CLOSE_SWITCH', target_resource_id: '스위치 2', status: 'ACCEPTED', created_at: '14:34:10' },
  { command_id: 'cmd-2', action: 'START_DISCHARGE', target_resource_id: 'ESS', status: 'ACCEPTED', created_at: '14:33:50' },
  { command_id: 'cmd-3', action: 'SHED_LOAD', target_resource_id: '부하 센터 3', status: 'REJECTED', created_at: '14:33:21' },
  { command_id: 'cmd-4', action: 'SET_POWER_LIMIT', target_resource_id: '태양광 2', status: 'ACCEPTED', created_at: '14:32:45' },
  { command_id: 'cmd-5', action: 'START_GENERATOR', target_resource_id: '디젤 발전기', status: 'ACCEPTED', created_at: '14:31:02' }
]

const displayedItems = computed(() => {
  if (pendingCommands.value.length > 0) {
    return pendingCommands.value.slice(0, 8)
  }
  return fallbackItems
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
      <button class="view-all-btn" type="button">{{ t('recentPanel.viewAll') }}</button>
    </div>

    <ul class="result-list">
      <li v-for="item in displayedItems" :key="item.command_id" class="result-row">
        <p class="command-text">{{ resolveDisplayResourceName(item.target_resource_id) }} {{ item.action }}</p>
        <div class="right-meta">
          <span class="status" :class="toResult(item.status).tone">{{ toResult(item.status).label }}</span>
          <span class="time">{{ item.created_at }}</span>
        </div>
      </li>
    </ul>
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
  @apply flex items-center justify-between rounded border border-slate-800 bg-slate-900/60 px-2 py-2;
}

.command-text {
  @apply truncate pr-2 text-xs text-slate-100;
}

.right-meta {
  @apply flex items-center gap-2 text-xs;
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
  @apply text-slate-400;
}
</style>
