<script setup lang="ts">
/**
 * HistoryPage.vue - 이력 페이지
 * 
 * [중요] 이 페이지는 조합 전용 페이지입니다.
 * - API를 직접 호출하지 마세요.
 */

import { ref } from 'vue'
import { useHistoryFeature } from '@/features/history'

const { records, isLoading, fetchHistory } = useHistoryFeature()

const startDate = ref('')
const endDate = ref('')

const handleSearch = async () => {
  if (startDate.value && endDate.value) {
    await fetchHistory(startDate.value, endDate.value)
  }
}
</script>

<template>
  <div class="history-page">
    <h1 class="page-title">이력</h1>
    
    <!-- 검색 필터 -->
    <section class="search-filter">
      <div class="filter-form">
        <label>
          시작일
          <input v-model="startDate" type="date" />
        </label>
        <label>
          종료일
          <input v-model="endDate" type="date" />
        </label>
        <button @click="handleSearch">검색</button>
      </div>
    </section>
    
    <!-- 이력 목록 -->
    <section class="history-list">
      <div v-if="isLoading" class="loading">로딩 중...</div>
      <div v-else-if="records.length === 0" class="empty">
        이력이 없습니다.
      </div>
      <div v-else class="record-list">
        <div 
          v-for="(record, index) in records" 
          :key="index"
          class="record-item"
        >
          <span class="timestamp">{{ record.timestamp }}</span>
          <span class="type">{{ record.type }}</span>
          <span class="data">{{ JSON.stringify(record.data) }}</span>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.history-page {
  @apply p-6;
}

.page-title {
  @apply text-2xl font-bold mb-6;
}

.search-filter {
  @apply mb-8;
}

.filter-form {
  @apply flex gap-4 items-end;
}

.filter-form label {
  @apply flex flex-col gap-1;
}

.filter-form input {
  @apply border rounded px-2 py-1;
}

.filter-form button {
  @apply px-4 py-2 bg-blue-500 text-white rounded;
}

.history-list {
  @apply bg-white rounded shadow p-4;
}

.loading,
.empty {
  @apply text-gray-500;
}

.record-list {
  @apply space-y-2;
}

.record-item {
  @apply flex gap-4 p-2 border-b;
}
</style>