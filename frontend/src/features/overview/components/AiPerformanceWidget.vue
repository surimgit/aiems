<script setup lang="ts">
import { computed } from 'vue'
import { storeToRefs } from 'pinia'
import { useAiStore } from '@/stores/ai/ai.store'

const aiStore = useAiStore()
const { recommendations, modelStatus } = storeToRefs(aiStore)

const highPriorityCount = computed(() => recommendations.value.filter((item) => item.priority === 'high').length)
const avgConfidence = computed(() => {
  if (recommendations.value.length === 0) return null
  const total = recommendations.value.reduce((sum, rec) => sum + rec.confidence, 0)
  return total / recommendations.value.length
})
</script>

<template>
  <section class="panel-card">
    <h3 class="title">AI 성과</h3>
    <div class="content">
      <p class="value">{{ highPriorityCount }}건</p>
      <div class="meta">
        <span>고우선 추천</span>
        <span>{{ avgConfidence === null ? '신뢰도 N/A' : `평균 신뢰도 ${(avgConfidence * 100).toFixed(1)}%` }}</span>
      </div>
      <p class="text-xs text-slate-400">모델 상태: {{ modelStatus?.status ?? 'UNKNOWN' }}</p>
    </div>
  </section>
</template>

<style scoped>
.panel-card {
  @apply rounded border border-slate-700 bg-slate-900/80 p-4 text-slate-100;
}

.title {
  @apply mb-3 font-semibold;
}

.content {
  @apply flex h-40 flex-col justify-between rounded border border-slate-700 bg-slate-950/60 p-3;
}

.value {
  @apply text-2xl font-semibold text-cyan-300;
}

.meta {
  @apply flex items-center justify-between text-sm text-slate-300;
}
</style>
