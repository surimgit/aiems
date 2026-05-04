<script setup lang="ts">
import type { Recommendation } from '@/types/common'

defineProps<{
  recommendation: Recommendation | null
}>()

const emit = defineEmits<{
  (e: 'approve', recommendationId: string): void
  (e: 'reject', recommendationId: string): void
}>()
</script>

<template>
  <section class="panel-card">
    <h3 class="title">AI 제어 제안</h3>
    <div v-if="recommendation" class="space-y-2">
      <p class="text-sm text-slate-200">{{ recommendation.action }}</p>
      <p class="text-xs text-slate-400">{{ recommendation.reason }}</p>
      <div class="actions">
        <button class="btn success" @click="emit('approve', recommendation.recommendation_id)">승인</button>
        <button class="btn" @click="emit('reject', recommendation.recommendation_id)">거절</button>
      </div>
    </div>
    <p v-else class="text-sm text-slate-400">현재 추천 없음</p>
  </section>
</template>

<style scoped>
.panel-card {
  @apply rounded border border-slate-700 bg-slate-900/80 p-4 text-slate-100;
}

.title {
  @apply font-semibold mb-3;
}

.actions {
  @apply grid grid-cols-2 gap-2;
}

.btn {
  @apply rounded border border-slate-600 px-3 py-2 text-sm;
}

.success {
  @apply bg-emerald-600 border-emerald-600;
}
</style>
