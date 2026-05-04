<script setup lang="ts">
/**
 * AlarmPage.vue - 알람 페이지
 * 
 * [중요] 이 페이지는 조합 전용 페이지입니다.
 * - API를 직접 호출하지 마세요.
 */

import { onMounted } from 'vue'
import { useAlarmFeature } from '@/features/alarm'

const { 
  alarms, 
  activeAlarms, 
  criticalAlarms, 
  hasActiveAlarm, 
  criticalAlarmCount,
  isLoading, 
  fetchAlarms,
  acknowledgeAlarm 
} = useAlarmFeature()

onMounted(async () => {
  await fetchAlarms()
})
</script>

<template>
  <div class="alarm-page">
    <h1 class="page-title">알람</h1>
    
    <!-- 요약 -->
    <section class="alarm-summary">
      <div class="summary-card">
        <span class="count">{{ activeAlarms.length }}</span>
        <span class="label">활성 알람</span>
      </div>
      <div class="summary-card critical">
        <span class="count">{{ criticalAlarmCount }}</span>
        <span class="label">비상 알람</span>
      </div>
    </section>
    
    <!-- 비상 알람 -->
    <section v-if="criticalAlarms.length > 0" class="critical-alarms">
      <h2>🚨 비상 알람</h2>
      <div class="alarm-list">
        <div 
          v-for="alarm in criticalAlarms" 
          :key="alarm.alarm_id"
          class="alarm-item critical"
        >
          <span class="level">{{ alarm.level }}</span>
          <span class="code">{{ alarm.code }}</span>
          <span class="message">{{ alarm.message }}</span>
          <span class="timestamp">{{ alarm.timestamp }}</span>
          <button @click="acknowledgeAlarm(alarm.alarm_id!)">확인</button>
        </div>
      </div>
    </section>
    
    <!-- 모든 알람 -->
    <section class="all-alarms">
      <h2>모든 알람</h2>
      <div v-if="alarms.length > 0" class="alarm-list">
        <div 
          v-for="alarm in alarms" 
          :key="alarm.alarm_id"
          class="alarm-item"
          :class="alarm.level"
        >
          <span class="level">{{ alarm.level }}</span>
          <span class="code">{{ alarm.code }}</span>
          <span class="message">{{ alarm.message }}</span>
          <span class="timestamp">{{ alarm.timestamp }}</span>
          <button 
            v-if="!alarm.acknowledged" 
            @click="acknowledgeAlarm(alarm.alarm_id!)"
          >
            확인
          </button>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.alarm-page {
  @apply p-6;
}

.page-title {
  @apply text-2xl font-bold mb-6;
}

.alarm-summary {
  @apply flex gap-4 mb-8;
}

.summary-card {
  @apply p-4 bg-white rounded shadow text-center;
}

.summary-card .count {
  @apply block text-3xl font-bold;
}

.summary-card.critical {
  @apply bg-red-50 border border-red-500;
}

.alarm-summary,
.critical-alarms,
.all-alarms {
  @apply mb-8;
}

.alarm-list {
  @apply space-y-2;
}

.alarm-item {
  @apply flex items-center gap-4 p-3 bg-white rounded shadow;
}

.alarm-item.critical {
  @apply border-l-4 border-red-500;
}

.alarm-item.warning {
  @apply border-l-4 border-amber-500;
}

.alarm-item.info {
  @apply border-l-4 border-blue-500;
}

.alarm-item button {
  @apply ml-auto px-3 py-1 bg-blue-500 text-white rounded;
}
</style>