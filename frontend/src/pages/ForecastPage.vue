<script setup lang="ts">
/**
 * ForecastPage.vue - 예측 페이지
 * 
 * [중요] 이 페이지는 조합 전용 페이지입니다.
 * - API를 직접 호출하지 마세요.
 */

import { onMounted } from 'vue'
import { useForecastFeature } from '@/features/forecast'

const { generationForecast, demandForecast, isLoading, fetchForecasts } = useForecastFeature()

onMounted(async () => {
  await fetchForecasts()
})
</script>

<template>
  <div class="forecast-page">
    <h1 class="page-title">예측</h1>
    
    <div v-if="isLoading" class="loading">로딩 중...</div>
    
    <!-- 발전량 예측 -->
    <section class="forecast-section">
      <h2>발전량 예측</h2>
      <div v-if="generationForecast.length > 0" class="forecast-list">
        <div 
          v-for="forecast in generationForecast" 
          :key="forecast.timestamp"
          class="forecast-item"
        >
          <span class="timestamp">{{ forecast.timestamp }}</span>
          <span class="predicted">{{ forecast.predicted_kw }} kW</span>
          <span class="confidence">{{ forecast.confidence }}%</span>
        </div>
      </div>
    </section>
    
    <!-- 수요 예측 -->
    <section class="forecast-section">
      <h2>수요 예측</h2>
      <div v-if="demandForecast.length > 0" class="forecast-list">
        <div 
          v-for="forecast in demandForecast" 
          :key="forecast.timestamp"
          class="forecast-item"
        >
          <span class="timestamp">{{ forecast.timestamp }}</span>
          <span class="predicted">{{ forecast.predicted_kw }} kW</span>
          <span class="confidence">{{ forecast.confidence }}%</span>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.forecast-page {
  @apply p-6;
}

.page-title {
  @apply text-2xl font-bold mb-6;
}

.forecast-section {
  @apply mb-8;
}

.forecast-list {
  @apply space-y-2;
}

.forecast-item {
  @apply flex justify-between p-3 bg-white rounded shadow;
}
</style>