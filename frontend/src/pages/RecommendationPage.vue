<script setup lang="ts">
/**
 * RecommendationPage.vue - 권장 조치 페이지
 * 
 * [중요] 이 페이지는 조합 전용 페이지입니다.
 * - API를 직접 호출하지 마세요.
 */

import { onMounted } from 'vue'
import { useRecommendationFeature } from '@/features/recommendation'

const { 
  recommendations, 
  highPriorityRecommendations, 
  isLoading, 
  fetchRecommendations 
} = useRecommendationFeature()

onMounted(async () => {
  await fetchRecommendations()
})
</script>

<template>
  <div class="recommendation-page">
    <h1 class="page-title">권장 조치</h1>
    
    <div v-if="isLoading" class="loading">로딩 중...</div>
    
    <!-- 높은 우선순위 -->
    <section v-if="highPriorityRecommendations.length > 0" class="high-priority">
      <h2>🔥 주요 권장</h2>
      <div class="recommendation-list">
        <div 
          v-for="rec in highPriorityRecommendations" 
          :key="rec.recommendation_id"
          class="recommendation-card high"
        >
          <h3>{{ rec.action }}</h3>
          <p>{{ rec.reason }}</p>
          <span class="priority-badge">높음</span>
        </div>
      </div>
    </section>
    
    <!-- 모든 권장 -->
    <section class="all-recommendations">
      <h2>모든 권장</h2>
      <div v-if="recommendations.length > 0" class="recommendation-list">
        <div 
          v-for="rec in recommendations" 
          :key="rec.recommendation_id"
          class="recommendation-card"
          :class="rec.priority"
        >
          <h3>{{ rec.action }}</h3>
          <p>{{ rec.reason }}</p>
          <span class="priority-badge">{{ rec.priority }}</span>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.recommendation-page {
  @apply p-6;
}

.page-title {
  @apply text-2xl font-bold mb-6;
}

.high-priority,
.all-recommendations {
  @apply mb-8;
}

.recommendation-list {
  @apply space-y-4;
}

.recommendation-card {
  @apply p-4 bg-white rounded shadow;
}

.recommendation-card.high {
  @apply border-l-4 border-red-500;
}

.recommendation-card h3 {
  @apply font-semibold mb-2;
}

.priority-badge {
  @apply inline-block px-2 py-1 text-xs rounded;
  @apply bg-gray-200;
}
</style>
