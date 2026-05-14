<script setup lang="ts">
import { computed, ref } from 'vue'
import { storeToRefs } from 'pinia'
import { useAlarmStore } from '@/stores/alarm/alarm.store'
import { useDashboardStore } from '@/stores/dashboard/dashboard.store'
import { useI18n } from 'vue-i18n'
import { resolveDashboardLayoutMode } from '@/features/overview/layoutPresets'
import type { AlarmData } from '@/types/common'

const emit = defineEmits<{
  (e: 'open-resource', resourceId: string): void
}>()

const alarmStore = useAlarmStore()
const dashboardStore = useDashboardStore()
const { activeAlarms } = storeToRefs(alarmStore)
const { t } = useI18n()

const viewportWidth = ref(typeof window !== 'undefined' ? window.innerWidth : 1920)
const alarmPage = ref(1)

const pageSize = computed(() => {
  const mode = resolveDashboardLayoutMode(viewportWidth.value)
  if (mode === 'tablet') return 5
  if (mode === 'wall') return 10
  return 8
})

const totalPages = computed(() =>
  Math.max(1, Math.ceil(activeAlarms.value.length / pageSize.value))
)

const hasNextPage = computed(() => alarmPage.value < totalPages.value)

const visibleAlarms = computed(() => {
  const start = (alarmPage.value - 1) * pageSize.value
  return activeAlarms.value.slice(start, start + pageSize.value)
})

const toLevelLabel = (value: string): string => {
  const normalized = value.toLowerCase()
  if (normalized === 'critical') return t('alarmPanel.level.critical')
  if (normalized === 'warning') return t('alarmPanel.level.warning')
  if (normalized === 'info') return t('alarmPanel.level.info')
  return value
}

const isCritical = (value: string): boolean => value.toLowerCase() === 'critical'

const extractMetric = (message: string): string | null => {
  const trimmed = message.trim()
  const matched = trimmed.match(/(-?\d+(?:,\d{3})*(?:\.\d+)?)\s*(kW|kWh|°C|%|V|A|Hz)$/i)
  if (!matched) return null
  return `${matched[1]}${matched[2] === '%' ? '%' : ` ${matched[2]}`}`
}

const stripMetricFromMessage = (message: string): string => {
  return message.replace(/\s*(-?\d+(?:,\d{3})*(?:\.\d+)?)\s*(kW|kWh|°C|%|V|A|Hz)$/i, '').trim()
}

const toMetricText = (message: string): string => extractMetric(message) ?? '-'

const toTitleText = (message: string): string => stripMetricFromMessage(message)

const toTimeText = (timestamp: string): string => {
  const parsed = new Date(timestamp)
  if (Number.isNaN(parsed.getTime())) {
    const matched = timestamp.match(/(\d{2}:\d{2}:\d{2})$/)
    return matched ? matched[1] : timestamp
  }

  return parsed.toLocaleTimeString('ko-KR', {
    hour12: false,
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  })
}

const acknowledge = async (alarmId?: string) => {
  if (!alarmId) return
  await alarmStore.acknowledgeAlarm(alarmId)
}

const resolveResourceId = (alarm: AlarmData): string | null => {
  if (alarm.device_id) return alarm.device_id
  if (alarm.ess_id) return alarm.ess_id
  if (alarm.resource_type) {
    const match = dashboardStore.resources.find(
      (r) => r.resource_type === alarm.resource_type
    )
    return match?.resource_id ?? null
  }
  return null
}

const openResource = (alarm: AlarmData) => {
  const resourceId = resolveResourceId(alarm)
  if (!resourceId) return
  emit('open-resource', resourceId)
}
</script>

<template>
  <div class="panel-content">
    <div class="header-row">
      <p class="title">{{ t('rightPanel.alarmTop3') }}</p>
    </div>

    <ul v-if="visibleAlarms.length > 0" class="space-y-2">
      <li
        v-for="alarm in visibleAlarms"
        :key="alarm.alarm_id"
        class="alarm-row"
        :class="{ critical: isCritical(alarm.level), clickable: !!resolveResourceId(alarm) }"
        @click="openResource(alarm)"
      >
        <div class="left-block">
          <span class="level-icon" :class="{ critical: isCritical(alarm.level) }">!</span>
          <p class="title" :class="{ critical: isCritical(alarm.level) }">{{ toTitleText(alarm.message) }}</p>
        </div>
        <p class="metric" :class="{ critical: isCritical(alarm.level) }">{{ toMetricText(alarm.message) }}</p>
        <p class="time">{{ toTimeText(alarm.timestamp) }}</p>
        <button class="ack-btn" type="button" @click.stop="acknowledge(alarm.alarm_id)">{{ t('alarmPanel.ack') }}</button>
      </li>
    </ul>
    <p v-else class="empty-text">{{ t('alarmPanel.empty') }}</p>

    <div class="pager-row">
      <button class="pager-btn" type="button" :disabled="alarmPage <= 1" @click="alarmPage--">이전</button>
      <span class="pager-index">{{ alarmPage }}</span>
      <button class="pager-btn" type="button" :disabled="!hasNextPage" @click="alarmPage++">다음</button>
    </div>
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

.alarm-row {
  @apply grid grid-cols-[minmax(0,1fr)_4rem_5rem_3.5rem] items-center gap-2 rounded border border-slate-700 bg-slate-900/50 px-3 py-2 text-xs;
}

.alarm-row.clickable {
  @apply cursor-pointer hover:bg-slate-800/60;
}

.ack-btn {
  @apply rounded border border-slate-600 px-2 py-0.5 text-[11px] text-slate-400 hover:border-slate-400 hover:text-slate-200;
}

.left-block {
  @apply flex min-w-0 items-center gap-2;
}

.level-icon {
  @apply inline-flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-full bg-amber-400/20 text-[12px] font-bold text-amber-300;
}

.level-icon.critical {
  @apply bg-red-400/20 text-red-300;
}

.title {
  @apply break-words whitespace-normal font-semibold text-slate-100;
}

.title.critical {
  @apply text-red-300;
}

.metric {
  @apply border-l border-slate-700 pl-3 text-xs text-slate-200 text-right;
}

.metric.critical {
  @apply text-red-300;
}

.time {
  @apply border-l border-slate-700 pl-3 text-xs text-slate-300 text-center;
}

.empty-text {
  @apply rounded border border-slate-700 bg-slate-900/50 px-3 py-3 text-xs text-slate-400;
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
