<script setup lang="ts">
import { computed, ref } from 'vue'
import { storeToRefs } from 'pinia'
import { useAlarmStore } from '@/stores/alarm/alarm.store'
import { useI18n } from 'vue-i18n'

const alarmStore = useAlarmStore()
const { activeAlarms } = storeToRefs(alarmStore)
const { t } = useI18n()

const isFullView = ref(false)

const toTimestampNumber = (value: string): number => {
  const date = new Date(value)
  const time = date.getTime()
  return Number.isFinite(time) ? time : 0
}

const sortedActiveAlarms = computed(() => {
  return [...activeAlarms.value].sort((a, b) => {
    return toTimestampNumber(b.timestamp) - toTimestampNumber(a.timestamp)
  })
})

const visibleAlarms = computed(() => {
  if (isFullView.value) return sortedActiveAlarms.value
  return sortedActiveAlarms.value.slice(0, 5)
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
</script>

<template>
  <div class="panel-content">
    <div class="mb-2 flex justify-end">
      <button type="button" class="toggle-btn" @click="isFullView = !isFullView">
        {{ isFullView ? t('alarmPanel.viewTop5') : t('alarmPanel.viewAll') }}
      </button>
    </div>

    <ul v-if="visibleAlarms.length > 0" class="space-y-2">
      <li v-for="alarm in visibleAlarms" :key="alarm.alarm_id" class="alarm-row" :class="{ critical: isCritical(alarm.level) }">
        <div class="left-block">
          <span class="level-icon" :class="{ critical: isCritical(alarm.level) }">!</span>
          <p class="title" :class="{ critical: isCritical(alarm.level) }">{{ toTitleText(alarm.message) }}</p>
        </div>
        <p class="metric" :class="{ critical: isCritical(alarm.level) }">{{ toMetricText(alarm.message) }}</p>
        <p class="time">{{ toTimeText(alarm.timestamp) }}</p>
      </li>
    </ul>
    <p v-else class="text-sm text-slate-400">{{ t('alarmPanel.empty') }}</p>
  </div>
</template>

<style scoped>
.panel-content {
  @apply rounded border border-slate-700 bg-slate-950/60 p-3 text-sm text-slate-300;
}

.toggle-btn {
  @apply rounded border border-slate-600 px-2 py-1 text-[11px] text-slate-300;
}

.alarm-row {
  @apply grid grid-cols-[minmax(0,1fr)_auto_auto] items-center gap-2 rounded border border-slate-700 bg-slate-900/50 px-3 py-2 text-xs;
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
  @apply border-l border-slate-700 pl-3 text-xs text-slate-200;
}

.metric.critical {
  @apply text-red-300;
}

.time {
  @apply border-l border-slate-700 pl-3 text-xs text-slate-300;
}
</style>
