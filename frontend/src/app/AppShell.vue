<script setup lang="ts">
/**
 * AppShell.vue - 전역 앱 셸
 * 
 * 역할:
 * - 전역 알람 스트립 표시
 * - 라우터 뷰 영역 제공
 * - 비상 우선 상태 노출
 * 
 * 설계 원칙:
 * - 알람/비상 상태는 AppShell 레벨에서 항상 노출 가능
 * - 페이지 컴포넌트는 라우터를 통해 지연 로드
 */

import { useAlarmStore } from '@/stores/alarm/alarm.store'
import { storeToRefs } from 'pinia'

const alarmStore = useAlarmStore()
const { hasActiveAlarm, criticalAlarmCount } = storeToRefs(alarmStore)

// 알람 스트립 클릭 핸들러
const handleAlarmStripClick = () => {
  // TODO: 알람 페이지로 네비게이트
  console.log('Navigate to alarm page')
}
</script>

<template>
  <div class="app-shell">
    <!-- 전역 알람 스트립 (항상 표시) -->
    <div 
      v-if="hasActiveAlarm" 
      class="alarm-strip"
      :class="{ 'critical': criticalAlarmCount > 0 }"
      @click="handleAlarmStripClick"
    >
      <span class="alarm-icon">⚠️</span>
      <span class="alarm-message">
        {{ criticalAlarmCount > 0 ? `${criticalAlarmCount}건의 비상 알람` : '활성 알람 있음' }}
      </span>
      <span class="alarm-action">자세히 보기 →</span>
    </div>

    <!-- 메인 레이아웃 -->
    <div class="app-layout">
      <!-- 사이드바 (필요시) -->
      <aside class="sidebar">
        <!-- TODO: 네비게이션 메뉴 -->
      </aside>

      <!-- 메인 콘텐츠 영역 -->
      <main class="main-content">
        <router-view />
      </main>
    </div>
  </div>
</template>

<style scoped>
.app-shell {
  @apply h-screen w-screen flex flex-col bg-gray-50;
}

.alarm-strip {
  @apply flex items-center justify-between px-4 py-2 bg-amber-500 text-white cursor-pointer;
  @apply hover:bg-amber-600 transition-colors;
}

.alarm-strip.critical {
  @apply bg-red-600 hover:bg-red-700;
}

.alarm-icon {
  @apply text-lg;
}

.alarm-message {
  @apply font-medium;
}

.alarm-action {
  @apply text-sm opacity-80;
}

.app-layout {
  @apply flex flex-1 overflow-hidden;
}

.sidebar {
  @apply w-64 bg-white border-r border-gray-200;
}

.main-content {
  @apply flex-1 overflow-auto p-6;
}
</style>