<script setup lang="ts">
import { computed } from 'vue'
import { storeToRefs } from 'pinia'
import { useAlarmStore } from '@/stores/alarm/alarm.store'
import { useI18n } from 'vue-i18n'

const alarmStore = useAlarmStore()
const { activeAlarms } = storeToRefs(alarmStore)
const { t } = useI18n()

const top3 = computed(() => activeAlarms.value.slice(0, 3))

const toLevelLabel = (value: string): string => {
  const normalized = value.toLowerCase()
  if (normalized === 'critical') return t('alarmPanel.level.critical')
  if (normalized === 'warning') return t('alarmPanel.level.warning')
  if (normalized === 'info') return t('alarmPanel.level.info')
  return value
}

const acknowledge = async (alarmId?: string) => {
  if (!alarmId) return
  await alarmStore.acknowledgeAlarm(alarmId)
}
</script>

<template>
  <div class="panel-content">
    <ul v-if="top3.length > 0" class="space-y-2">
      <li v-for="alarm in top3" :key="alarm.alarm_id" class="rounded border border-slate-700 p-2 text-xs">
        <p class="font-semibold text-slate-100">{{ alarm.code }} · {{ toLevelLabel(alarm.level) }}</p>
        <p class="text-slate-300">{{ alarm.message }}</p>
        <div class="mt-1 flex items-center justify-between">
          <span class="text-slate-400">{{ alarm.timestamp }}</span>
          <button class="ack-btn" @click="acknowledge(alarm.alarm_id)">{{ t('alarmPanel.ack') }}</button>
        </div>
      </li>
    </ul>
    <p v-else class="text-sm text-slate-400">{{ t('alarmPanel.empty') }}</p>
  </div>
</template>

<style scoped>
.panel-content {
  @apply rounded border border-slate-700 bg-slate-950/60 p-3 text-sm text-slate-300;
}

.ack-btn {
  @apply rounded border border-slate-600 px-2 py-0.5 text-[11px] text-slate-100;
}
</style>
