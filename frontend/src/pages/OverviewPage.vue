<script setup lang="ts">
/**
 * OverviewPage.vue - 개요 페이지
 * 
 * [중요] 이 페이지는 조합 전용 페이지입니다.
 * - API를 직접 호출하지 마세요.
 * - 대신 features/stores를 통해 데이터를 사용하세요.
 * - 데이터 흐름: API → Store → Feature → Page
 */

import { onMounted } from 'vue'
import { useOverviewFeature } from '@/features/overview'

const { 
  powerSummary, 
  essList, 
  activeAlarms, 
  isLoading, 
  initialize 
} = useOverviewFeature()

onMounted(async () => {
  await initialize()
})
</script>

<template>
  <div class="overview-page">
    <h1 class="page-title">대시보드 개요</h1>
    
    <!-- 로딩 상태 -->
    <div v-if="isLoading" class="loading-state">
      데이터를 불러오는 중...
    </div>
    
    <!-- 주요 전력 요약 -->
    <section class="power-summary">
      <h2>전력 요약</h2>
      <div v-if="powerSummary" class="summary-grid">
        <div class="summary-item">
          <span class="label">Net Power</span>
          <span class="value">{{ powerSummary.net_power_kw }} kW</span>
        </div>
        <div class="summary-item">
          <span class="label">PV</span>
          <span class="value">{{ powerSummary.pv_power_kw }} kW</span>
        </div>
        <div class="summary-item">
          <span class="label">ESS</span>
          <span class="value">{{ powerSummary.ess_power_kw }} kW</span>
        </div>
        <div class="summary-item">
          <span class="label">Grid</span>
          <span class="value">{{ powerSummary.grid_power_kw }} kW</span>
        </div>
        <div class="summary-item">
          <span class="label">Load</span>
          <span class="value">{{ powerSummary.load_power_kw }} kW</span>
        </div>
      </div>
    </section>
    
    <!-- ESS 목록 -->
    <section class="ess-list">
      <h2>ESS 상태</h2>
      <div v-if="essList.length > 0" class="ess-grid">
        <div v-for="ess in essList" :key="ess.ess_id" class="ess-card">
          <h3>{{ ess.name || ess.ess_id }}</h3>
          <p>SOC: {{ ess.soc }}%</p>
          <p>Status: {{ ess.status }}</p>
        </div>
      </div>
    </section>
    
    <!-- 활성 알람 -->
    <section v-if="activeAlarms.length > 0" class="active-alarms">
      <h2>활성 알람</h2>
      <ul>
        <li v-for="alarm in activeAlarms" :key="alarm.alarm_id" :class="alarm.level">
          {{ alarm.message }}
        </li>
      </ul>
    </section>
  </div>
</template>

<style scoped>
.overview-page {
  @apply p-6;
}

.page-title {
  @apply text-2xl font-bold mb-6;
}

.loading-state {
  @apply text-gray-500;
}

.power-summary,
.ess-list,
.active-alarms {
  @apply mb-8;
}

.summary-grid {
  @apply grid grid-cols-2 md:grid-cols-5 gap-4;
}

.summary-item {
  @apply p-4 bg-white rounded shadow;
}

.summary-item .label {
  @apply block text-sm text-gray-500;
}

.summary-item .value {
  @apply text-xl font-semibold;
}

.ess-grid {
  @apply grid grid-cols-1 md:grid-cols-3 gap-4;
}

.ess-card {
  @apply p-4 bg-white rounded shadow;
}

.active-alarms ul {
  @apply list-disc pl-5;
}

.active-alarms .critical {
  @apply text-red-600 font-bold;
}

.active-alarms .warning {
  @apply text-amber-600;
}

.active-alarms .info {
  @apply text-blue-600;
}
</style>