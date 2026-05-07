<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { ControlResult } from '@/types/common'
import { useResourceAlias } from '@/features/overview/composables/useResourceAlias'
import type { LocaleType } from '@/app/i18n'

const props = defineProps<{
  items: ControlResult[]
  loading: boolean
  error?: string | null
}>()

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

const sortedItems = computed(() => {
  const toTime = (value: string): number => {
    const parsed = new Date(value).getTime()
    return Number.isFinite(parsed) ? parsed : 0
  }

  return [...props.items].sort((a, b) => toTime(b.created_at) - toTime(a.created_at))
})

const toStatus = (status: string) => {
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

const toTimeText = (createdAt: string): string => {
  const parsed = new Date(createdAt)
  if (Number.isNaN(parsed.getTime())) return createdAt
  return parsed.toLocaleString('ko-KR', {
    hour12: false,
    year: '2-digit',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  })
}

const toTargetName = (resourceId: string): string =>
  getDisplayName(resourceId, resourceId, locale.value as LocaleType)
</script>

<template>
  <div class="table-wrap">
    <p v-if="loading" class="state-text">{{ t('recentPanel.loading') }}</p>
    <p v-else-if="error" class="state-text error">{{ t('recentPanel.error') }}</p>
    <p v-else-if="sortedItems.length === 0" class="state-text">{{ t('recentPanel.empty') }}</p>

    <table v-else class="history-table">
      <thead>
        <tr>
          <th>{{ t('recentPanel.table.time') }}</th>
          <th>{{ t('recentPanel.table.status') }}</th>
          <th>{{ t('recentPanel.table.command') }}</th>
          <th>{{ t('recentPanel.table.target') }}</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="item in sortedItems" :key="item.command_id">
          <td>{{ toTimeText(item.created_at) }}</td>
          <td>
            <span class="status" :class="toStatus(item.status).tone">{{ toStatus(item.status).label }}</span>
          </td>
          <td>{{ item.action }}</td>
          <td>{{ toTargetName(item.target_resource_id) }}</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<style scoped>
.table-wrap {
  @apply rounded bg-transparent p-0;
}

.history-table {
  @apply w-full border-collapse text-xs;
}

.history-table th {
  @apply border-b border-slate-700 px-2 py-2 text-left font-semibold text-slate-300;
}

.history-table td {
  @apply border-b border-slate-800 px-2 py-2 text-slate-200;
}

.history-table tbody tr:last-child td {
  @apply border-b-0;
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

.state-text {
  @apply rounded border border-slate-700 bg-slate-900/50 px-3 py-3 text-xs text-slate-400;
}

.state-text.error {
  @apply text-red-300;
}
</style>
