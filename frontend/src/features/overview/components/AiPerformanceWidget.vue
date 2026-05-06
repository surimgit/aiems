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

const clamp = (value: number, min: number, max: number): number => Math.min(max, Math.max(min, value))

const parseEffectWon = (text: string): number | null => {
  const normalized = text.replace(/,/g, '').replace(/\s/g, '')
  const matched = normalized.match(/(-?\d+(?:\.\d+)?)\s*(원|만원|천원)?/)
  if (!matched) return null

  const numeric = Number(matched[1])
  if (!Number.isFinite(numeric)) return null

  const unit = matched[2]
  if (unit === '만원') return numeric * 10000
  if (unit === '천원') return numeric * 1000
  return numeric
}

const estimatedSavingWon = computed(() => {
  const fromExpectedEffect = recommendations.value
    .map((item) => parseEffectWon(item.expected_effect))
    .filter((value): value is number => typeof value === 'number' && Number.isFinite(value))

  if (fromExpectedEffect.length > 0) {
    return Math.round(fromExpectedEffect.reduce((sum, current) => sum + current, 0))
  }

  if (avgConfidence.value !== null && recommendations.value.length > 0) {
    const fallback = avgConfidence.value * recommendations.value.length * 800000
    return Math.round(fallback)
  }

  return 0
})

const targetWon = computed(() => {
  if (estimatedSavingWon.value <= 0) return 1850000
  const derivedTarget = estimatedSavingWon.value * 0.75
  return Math.round(derivedTarget)
})

const achievementRate = computed(() => {
  if (targetWon.value <= 0) return 0
  return (estimatedSavingWon.value / targetWon.value) * 100
})

const gaugeRate = computed(() => clamp(achievementRate.value, 0, 150))

const gaugeArc = computed(() => {
  const radius = 82
  const circumference = Math.PI * radius
  const offset = circumference * (1 - gaugeRate.value / 150)
  return { circumference, offset }
})

const formattedSaving = computed(() => `${estimatedSavingWon.value.toLocaleString('ko-KR')} 원`)
const formattedTarget = computed(() => `${targetWon.value.toLocaleString('ko-KR')} 원`)

const modelStatusText = computed(() => {
  if (modelStatus.value?.status) return modelStatus.value.status
  return 'UNKNOWN'
})
</script>

<template>
  <section class="panel-card">
    <h3 class="title">AI 성과 <span class="sub-title">(이번 달)</span></h3>

    <div class="gauge-card">
      <div class="gauge-wrap" role="img" aria-label="AI 성과 달성률 게이지">
        <svg viewBox="0 0 220 140" class="gauge-svg" preserveAspectRatio="xMidYMid meet">
          <path class="track" d="M 28 112 A 82 82 0 0 1 192 112" />
          <path
            class="progress"
            d="M 28 112 A 82 82 0 0 1 192 112"
            :stroke-dasharray="gaugeArc.circumference"
            :stroke-dashoffset="gaugeArc.offset"
          />
        </svg>

        <div class="gauge-center">
          <p class="amount">{{ formattedSaving }}</p>
        </div>
      </div>

      <div class="gauge-footer">
        <div class="footer-item">
          <p class="footer-label">목표</p>
          <p class="footer-value">{{ formattedTarget }}</p>
        </div>
        <div class="footer-item align-right">
          <p class="footer-label">달성률</p>
          <p class="footer-value">{{ achievementRate.toFixed(1) }}%</p>
        </div>
      </div>
    </div>

    <p class="meta">고우선 추천 {{ highPriorityCount }}건 · 평균 신뢰도 {{ avgConfidence === null ? 'N/A' : `${(avgConfidence * 100).toFixed(1)}%` }} · 모델 상태 {{ modelStatusText }}</p>
  </section>
</template>

<style scoped>
.panel-card {
  @apply rounded border border-slate-700 bg-slate-900/80 p-3 text-slate-100;
}

.title {
  @apply mb-2 font-semibold text-sm;
}

.sub-title {
  @apply ml-1 text-xs font-normal text-slate-400;
}

.gauge-card {
  @apply rounded border border-slate-700 bg-slate-950/60 p-2;
}

.gauge-wrap {
  @apply relative;
}

.gauge-svg {
  @apply h-28 w-full;
}

.track {
  fill: none;
  stroke: rgba(148, 163, 184, 0.35);
  stroke-width: 14;
  stroke-linecap: round;
}

.progress {
  fill: none;
  stroke: #5b8dff;
  stroke-width: 14;
  stroke-linecap: round;
  transition: stroke-dashoffset 0.35s ease;
}

.gauge-center {
  @apply pointer-events-none absolute inset-0 flex items-center justify-center;
}

.amount {
  @apply text-lg font-semibold text-cyan-200;
}

.gauge-footer {
  @apply mt-1 grid grid-cols-2 gap-2 border-t border-slate-700 pt-2;
}

.footer-item {
  @apply min-w-0;
}

.align-right {
  @apply text-right;
}

.footer-label {
  @apply text-[11px] text-slate-400;
}

.footer-value {
  @apply mt-0.5 text-sm font-semibold text-slate-100;
}

.meta {
  @apply mt-2 text-[10px] text-slate-500;
}
</style>
