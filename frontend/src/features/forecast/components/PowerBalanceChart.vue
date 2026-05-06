<script setup lang="ts">
import { computed } from 'vue'
import { storeToRefs } from 'pinia'
import { useAiStore } from '@/stores/ai/ai.store'

interface ChartSeriesPoint {
  timestamp: string
  generationKw: number
  demandKw: number
  netKw: number
}

interface YAxisTick {
  label: string
  y: number
}

const VIEWBOX_WIDTH = 100
const VIEWBOX_HEIGHT = 60
const MIN_BOUND_GAP = 1

const aiStore = useAiStore()
const { generationForecast, demandForecast } = storeToRefs(aiStore)

const normalizedSeries = computed<ChartSeriesPoint[]>(() => {
  if (generationForecast.value.length === 0 || demandForecast.value.length === 0) return []

  const generationMap = new Map<string, number>()
  generationForecast.value.forEach((item) => {
    if (typeof item.predicted_kw === 'number' && Number.isFinite(item.predicted_kw)) {
      generationMap.set(item.timestamp, item.predicted_kw)
    }
  })

  const merged = demandForecast.value
    .filter((item) => typeof item.predicted_kw === 'number' && Number.isFinite(item.predicted_kw))
    .map((demandPoint) => {
      const generationKw = generationMap.get(demandPoint.timestamp)
      if (typeof generationKw !== 'number') return null
      const demandKw = demandPoint.predicted_kw
      return {
        timestamp: demandPoint.timestamp,
        generationKw,
        demandKw,
        netKw: generationKw - demandKw
      }
    })
    .filter((item): item is ChartSeriesPoint => item !== null)

  return merged.slice(0, 24)
})

const hasForecastData = computed(() => normalizedSeries.value.length > 2)

const chartBounds = computed(() => {
  if (!hasForecastData.value) {
    return { min: -500, max: 1500 }
  }

  const values = normalizedSeries.value.flatMap((point) => [point.generationKw, point.demandKw, point.netKw])
  const min = Math.min(...values)
  const max = Math.max(...values)

  if (min === max) {
    return { min: min - 100, max: max + 100 }
  }

  const gap = Math.max((max - min) * 0.1, MIN_BOUND_GAP)
  return {
    min: Math.floor((min - gap) / 100) * 100,
    max: Math.ceil((max + gap) / 100) * 100
  }
})

const toY = (value: number): number => {
  const min = chartBounds.value.min
  const max = chartBounds.value.max
  const ratio = (value - min) / Math.max(max - min, MIN_BOUND_GAP)
  return VIEWBOX_HEIGHT - ratio * VIEWBOX_HEIGHT
}

const toPath = (values: number[]): string => {
  if (values.length === 0) return ''

  return values
    .map((value, index) => {
      const x = (index / Math.max(values.length - 1, 1)) * VIEWBOX_WIDTH
      const y = toY(value)
      return `${index === 0 ? 'M' : 'L'} ${x.toFixed(2)} ${y.toFixed(2)}`
    })
    .join(' ')
}

const generationPath = computed(() => toPath(normalizedSeries.value.map((item) => item.generationKw)))
const demandPath = computed(() => toPath(normalizedSeries.value.map((item) => item.demandKw)))
const netPath = computed(() => toPath(normalizedSeries.value.map((item) => item.netKw)))

const yAxisTicks = computed<YAxisTick[]>(() => {
  const min = chartBounds.value.min
  const max = chartBounds.value.max
  const step = (max - min) / 4

  return Array.from({ length: 5 }, (_, index) => {
    const value = max - step * index
    return {
      label: value.toLocaleString('ko-KR', { maximumFractionDigits: 0 }),
      y: (index / 4) * VIEWBOX_HEIGHT
    }
  })
})

const peakTimeRange = computed(() => {
  if (!hasForecastData.value) return '정보 없음'

  let maxPoint = normalizedSeries.value[0]
  for (const point of normalizedSeries.value) {
    if (point.demandKw > maxPoint.demandKw) {
      maxPoint = point
    }
  }

  const date = new Date(maxPoint.timestamp)
  if (Number.isNaN(date.getTime())) return '정보 없음'
  const startHour = date.getHours().toString().padStart(2, '0')
  const endHour = ((date.getHours() + 4) % 24).toString().padStart(2, '0')
  return `${startHour}~${endHour}시`
})
</script>

<template>
  <section class="panel-card">
    <div class="header-row">
      <h3 class="title">AI 예측 <span class="sub-title">(24시간)</span></h3>
      <span class="peak-label">피크 예상 {{ peakTimeRange }}</span>
    </div>

    <div class="legend-row">
      <div class="legend-item">
        <span class="legend-line generation" />
        <span>발전 예측</span>
      </div>
      <div class="legend-item">
        <span class="legend-line demand" />
        <span>소비 예측</span>
      </div>
      <div class="legend-item">
        <span class="legend-line net" />
        <span>순 전력 예측</span>
      </div>
    </div>

    <div v-if="hasForecastData" class="chart-area">
      <div class="y-axis">
        <span class="unit">kW</span>
        <div v-for="tick in yAxisTicks" :key="tick.label" class="tick-label" :style="{ top: `${tick.y / VIEWBOX_HEIGHT * 100}%` }">
          {{ tick.label }}
        </div>
      </div>

      <div class="plot-wrap">
        <svg viewBox="0 0 100 60" preserveAspectRatio="none" class="plot-svg" aria-label="AI 예측 시계열 차트">
          <g class="grid-lines">
            <line v-for="tick in yAxisTicks" :key="`line-${tick.label}`" x1="0" :y1="tick.y" x2="100" :y2="tick.y" />
          </g>

          <path class="series generation" :d="generationPath" />
          <path class="series demand" :d="demandPath" />
          <path class="series net" :d="netPath" />
        </svg>

        <div class="x-axis">
          <span>00:00</span>
          <span>06:00</span>
          <span>12:00</span>
          <span>18:00</span>
          <span>24:00</span>
        </div>
      </div>
    </div>

    <div v-else class="empty-state">AI 예측 데이터가 아직 없습니다.</div>

    <p class="note">* 이상 발생 시 붉은색으로 구간 표시됩니다.</p>
  </section>
</template>

<style scoped>
.panel-card {
  @apply rounded border border-slate-700 bg-slate-900/80 p-3 text-slate-100;
}

.header-row {
  @apply mb-2 flex items-center justify-between gap-2;
}

.title {
  @apply text-sm font-semibold;
}

.sub-title {
  @apply ml-1 text-xs font-normal text-slate-400;
}

.peak-label {
  @apply rounded border border-slate-700 bg-slate-950/70 px-2 py-1 text-[10px] text-cyan-200;
}

.legend-row {
  @apply mb-2 flex items-center gap-3 text-[11px] text-slate-300;
}

.legend-item {
  @apply flex items-center gap-1;
}

.legend-line {
  @apply inline-block h-[2px] w-5 rounded;
}

.legend-line.generation {
  @apply bg-sky-300;
}

.legend-line.demand {
  @apply bg-indigo-300;
  border-top: 1px dashed rgba(165, 180, 252, 0.9);
}

.legend-line.net {
  @apply bg-emerald-300;
}

.chart-area {
  @apply flex min-h-[8rem] rounded border border-slate-700 bg-slate-950/60 p-2;
}

.y-axis {
  @apply relative mr-2 w-9 flex-shrink-0 text-[10px] text-slate-400;
}

.unit {
  @apply absolute -top-1 left-0 text-[10px] text-slate-500;
}

.tick-label {
  @apply absolute left-0 -translate-y-1/2;
}

.plot-wrap {
  @apply flex min-w-0 flex-1 flex-col;
}

.plot-svg {
  @apply h-[7.2rem] w-full;
}

.grid-lines line {
  stroke: rgba(148, 163, 184, 0.25);
  stroke-width: 0.35;
}

.series {
  fill: none;
  stroke-width: 1.05;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.series.generation {
  stroke: #7dd3fc;
}

.series.demand {
  stroke: #a5b4fc;
  stroke-dasharray: 2.2 1.5;
}

.series.net {
  stroke: #6ee7b7;
}

.x-axis {
  @apply mt-1 flex justify-between text-[10px] text-slate-400;
}

.empty-state {
  @apply min-h-[8rem] rounded border border-slate-700 bg-slate-950/60 p-2 text-xs text-slate-400;
}

.note {
  @apply mt-2 text-[10px] text-slate-500;
}
</style>
