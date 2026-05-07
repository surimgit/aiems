<script setup lang="ts">
/**
 * DetailPage.vue - 상세 페이지
 * 
 * [중요] 이 페이지는 조합 전용 페이지입니다.
 * - API를 직접 호출하지 마세요.
 * - 대신 features/stores를 통해 데이터를 사용하세요.
 */

import { onMounted } from 'vue'
import { useDetailFeature } from '@/features/detail'

const { essList, selectedEss, isLoading, selectEss } = useDetailFeature()

onMounted(async () => {
  // TODO: 데이터 로드
})
</script>

<template>
  <div class="detail-page">
    <h1 class="page-title">ESS 상세</h1>
    
    <div v-if="isLoading" class="loading">로딩 중...</div>
    
    <!-- ESS 선택 -->
    <section class="ess-selector">
      <h2>ESS 선택</h2>
      <div class="ess-list">
        <button 
          v-for="ess in essList" 
          :key="ess.ess_id"
          @click="selectEss(ess.ess_id)"
          class="ess-button"
        >
          {{ ess.name || ess.ess_id }}
        </button>
      </div>
    </section>
    
    <!-- 상세 정보 -->
    <section v-if="selectedEss" class="ess-detail">
      <h2>상세 정보</h2>
      <dl>
        <dt>ESS ID</dt>
        <dd>{{ selectedEss.ess_id }}</dd>
        
        <dt>SOC</dt>
        <dd>{{ selectedEss.soc }}%</dd>
        
        <dt>SOH</dt>
        <dd>{{ selectedEss.soh }}%</dd>
        
        <dt>상태</dt>
        <dd>{{ selectedEss.status }}</dd>
        
        <dt>용량</dt>
        <dd>{{ selectedEss.capacity_kwh }} kWh</dd>
        
        <dt>최대 출력</dt>
        <dd>{{ selectedEss.max_power_kw }} kW</dd>
      </dl>
    </section>
  </div>
</template>

<style scoped>
.detail-page {
  @apply p-6;
}

.page-title {
  @apply text-2xl font-bold mb-6;
}

.loading {
  @apply text-gray-500;
}

.ess-selector,
.ess-detail {
  @apply mb-8;
}

.ess-list {
  @apply flex gap-2 flex-wrap;
}

.ess-button {
  @apply px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600;
}

.ess-detail dl {
  @apply grid grid-cols-2 gap-4;
}

.ess-detail dt {
  @apply font-semibold text-gray-600;
}

.ess-detail dd {
  @apply text-lg;
}
</style>