<script setup lang="ts">
import type { AlarmData } from '@/types/common'

defineProps<{
  alarms: AlarmData[]
}>()
</script>

<template>
  <section class="panel-card">
    <h3 class="title">알람 요약</h3>
    <ul class="space-y-2">
      <li v-for="alarm in alarms.slice(0, 3)" :key="alarm.alarm_id" class="text-sm text-slate-300">
        {{ alarm.message }}
      </li>
    </ul>
  </section>
</template>

<style scoped>
.panel-card {
  @apply rounded border border-slate-700 bg-slate-900/80 p-4 text-slate-100;
}

.title {
  @apply font-semibold mb-3;
}
</style>
