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
import { menuItems } from '@/app/router'
import { useRoute, useRouter } from 'vue-router'

const alarmStore = useAlarmStore()
const { hasActiveAlarm, criticalAlarmCount } = storeToRefs(alarmStore)
const router = useRouter()
const route = useRoute()

// 알람 스트립 클릭 핸들러
const handleAlarmStripClick = () => {
  void router.push('/alarm')
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
      <!-- 사이드바 -->
      <aside class="sidebar">
        <div class="sidebar-header">
          <p class="sidebar-title">AI EMS</p>
          <p class="sidebar-subtitle">Navigation</p>
        </div>

        <nav class="sidebar-nav" aria-label="주요 메뉴">
          <router-link
            v-for="item in menuItems"
            :key="item.path"
            :to="item.path"
            class="nav-item"
            :class="{ active: route.path === item.path }"
          >
            <span class="icon">{{ item.icon }}</span>
            <span>{{ item.title }}</span>
          </router-link>
        </nav>
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
  @apply h-screen w-screen flex flex-col bg-slate-950 text-slate-100;
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
  @apply hidden md:flex md:w-64 shrink-0 flex-col border-r border-slate-800 bg-slate-900/80;
}

.main-content {
  @apply flex-1 overflow-auto p-4 md:p-6;
}

.sidebar-header {
  @apply border-b border-slate-800 px-4 py-4;
}

.sidebar-title {
  @apply text-lg font-semibold text-slate-100;
}

.sidebar-subtitle {
  @apply text-xs text-slate-400;
}

.sidebar-nav {
  @apply flex flex-col gap-1 px-3 py-3;
}

.nav-item {
  @apply flex items-center gap-2 rounded-md px-3 py-2 text-sm text-slate-300 transition-colors;
}

.nav-item:hover {
  @apply bg-slate-800/80 text-slate-100;
}

.nav-item.active {
  @apply bg-slate-800 text-cyan-300;
}

.icon {
  @apply w-5 text-center;
}
</style>
