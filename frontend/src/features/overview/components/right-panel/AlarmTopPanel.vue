<script setup lang="ts">
import { computed } from 'vue'
import { storeToRefs } from 'pinia'
import { useAlarmStore } from '@/stores/alarm/alarm.store'

const alarmStore = useAlarmStore()
const { activeAlarms } = storeToRefs(alarmStore)

const top3 = computed(() => activeAlarms.value.slice(0, 3))

const acknowledge = async (alarmId?: string) => {
  if (!alarmId) return
  await alarmStore.acknowledgeAlarm(alarmId)
}
</script>

<template>
  <div class="panel-content">
    <ul v-if="top3.length > 0" class="space-y-2">
      <li v-for="alarm in top3" :key="alarm.alarm_id" class="rounded border border-slate-700 p-2 text-xs">
        <p class="font-semibold text-slate-100">{{ alarm.code }} · {{ alarm.level }}</p>
        <p class="text-slate-300">{{ alarm.message }}</p>
        <div class="mt-1 flex items-center justify-between">
          <span class="text-slate-400">{{ alarm.timestamp }}</span>
          <button class="ack-btn" @click="acknowledge(alarm.alarm_id)">확인</button>
        </div>
      </li>
    </ul>
    <p v-else class="text-sm text-slate-400">활성 알람이 없습니다.</p>
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
