<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { Chart } from 'chart.js/auto'
import { useAiStore } from '@/stores/ai/ai.store'
import { useI18n } from 'vue-i18n'

interface PowerPoint {
  ts: string
  generationKw: number | null
  consumptionKw: number | null
  balanceKw: number | null
}

const MIN_BOUND_GAP = 1

const aiStore = useAiStore()
const { generationForecast, demandForecast, loading } = storeToRefs(aiStore)
const { t, locale } = useI18n()

const chartCanvasRef = ref<HTMLCanvasElement | null>(null)
const chartInstance = ref<Chart<'line'> | null>(null)

const toFiniteNumberOrNull = (value: unknown): number | null => {
  if (typeof value !== 'number' || !Number.isFinite(value)) return null
  return value
}

const buildDevFallbackSeries = (): PowerPoint[] => {
  const baseDate = new Date()
  baseDate.setMinutes(0, 0, 0)

  return Array.from({ length: 24 }, (_, hourOffset) => {
    const pointDate = new Date(baseDate)
    pointDate.setHours(baseDate.getHours() + hourOffset)

    const daytimeFactor = Math.max(0, Math.sin(((hourOffset - 6) / 24) * Math.PI * 2))
    const generationKw = Math.round(480 + daytimeFactor * 620)
    const consumptionKw = Math.round(620 + Math.sin(((hourOffset + 2) / 24) * Math.PI * 2) * 210)

    return {
      ts: pointDate.toISOString(),
      generationKw,
      consumptionKw,
      balanceKw: generationKw - consumptionKw
    }
  })
}

const normalizeSeries = (points: PowerPoint[]): PowerPoint[] => {
  const deduped = new Map<string, PowerPoint>()
  points.forEach((point) => {
    if (!point.ts) return
    deduped.set(point.ts, point)
  })

  return [...deduped.values()]
    .sort((a, b) => new Date(a.ts).getTime() - new Date(b.ts).getTime())
    .slice(0, 24)
}

const normalizedSeries = computed<PowerPoint[]>(() => {
  if (generationForecast.value.length === 0 || demandForecast.value.length === 0) {
    return import.meta.env.DEV ? buildDevFallbackSeries() : []
  }

  const generationMap = new Map<string, number | null>()
  generationForecast.value.forEach((item) => {
    generationMap.set(item.timestamp, toFiniteNumberOrNull(item.predicted_kw))
  })

  const merged = demandForecast.value.map((demandPoint) => {
    const generationKw = generationMap.get(demandPoint.timestamp) ?? null
    const consumptionKw = toFiniteNumberOrNull(demandPoint.predicted_kw)

    return {
      ts: demandPoint.timestamp,
      generationKw,
      consumptionKw,
      balanceKw:
        generationKw === null || consumptionKw === null
          ? null
          : generationKw - consumptionKw
    }
  })

  return normalizeSeries(merged)
})

const hasForecastData = computed(() =>
  normalizedSeries.value.some(
    (point) => point.generationKw !== null || point.consumptionKw !== null || point.balanceKw !== null
  )
)

const isLoading = computed(() => loading.value && normalizedSeries.value.length === 0)

const peakTimeRange = computed(() => {
  if (!hasForecastData.value) return t('common.noData')

  const valid = normalizedSeries.value.filter((point) => point.consumptionKw !== null)
  if (valid.length === 0) return t('common.noData')

  let maxPoint = valid[0]
  for (const point of valid) {
    if ((point.consumptionKw ?? Number.NEGATIVE_INFINITY) > (maxPoint.consumptionKw ?? Number.NEGATIVE_INFINITY)) {
      maxPoint = point
    }
  }

  const date = new Date(maxPoint.ts)
  if (Number.isNaN(date.getTime())) return t('common.noData')
  const startHour = date.getHours().toString().padStart(2, '0')
  const endHour = ((date.getHours() + 4) % 24).toString().padStart(2, '0')
  return `${startHour}~${endHour}시`
})

interface YAxisRange {
  min: number
  max: number
  step: number
}

const pickNiceStep = (rawStep: number): number => {
  const candidateSteps = [50, 100, 200, 250, 500, 1000, 2000]
  for (const step of candidateSteps) {
    if (rawStep <= step) return step
  }
  return Math.ceil(rawStep / 1000) * 1000
}

const buildYAxisRange = (series: PowerPoint[]): YAxisRange => {
  const values = series.flatMap((point) => [point.generationKw, point.consumptionKw, point.balanceKw]).filter((v): v is number => v !== null)

  if (values.length === 0) {
    return { min: -500, max: 1500, step: 500 }
  }

  const rawMin = Math.min(...values)
  const rawMax = Math.max(...values)
  if (rawMin === rawMax) {
    const fallbackStep = pickNiceStep(Math.max(Math.abs(rawMin) * 0.2, 100))
    return {
      min: rawMin - fallbackStep * 2,
      max: rawMax + fallbackStep * 2,
      step: fallbackStep
    }
  }

  const gap = Math.max((rawMax - rawMin) * 0.1, MIN_BOUND_GAP)
  const paddedMin = rawMin - gap
  const paddedMax = rawMax + gap
  const step = pickNiceStep((paddedMax - paddedMin) / 4)

  return {
    min: Math.floor(paddedMin / step) * step,
    max: Math.ceil(paddedMax / step) * step,
    step
  }
}

const toTimeLabel = (isoTimestamp: string): string => {
  const date = new Date(isoTimestamp)
  if (Number.isNaN(date.getTime())) return '--:--'
  return date.toLocaleTimeString(locale.value, {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false
  })
}

const createOrUpdateChart = () => {
  if (!chartCanvasRef.value) return

  const points = normalizedSeries.value
  const labels = points.map((point) => toTimeLabel(point.ts))
  const range = buildYAxisRange(points)

  const datasets = [
    {
      label: t('powerBalance.legend.generation'),
      data: points.map((point) => point.generationKw),
      borderColor: '#7dd3fc',
      backgroundColor: 'rgba(125, 211, 252, 0.15)',
      borderWidth: 2,
      spanGaps: true,
      pointRadius: 0,
      pointHoverRadius: 3,
      tension: 0.25
    },
    {
      label: t('powerBalance.legend.demand'),
      data: points.map((point) => point.consumptionKw),
      borderColor: '#a5b4fc',
      backgroundColor: 'rgba(165, 180, 252, 0.15)',
      borderWidth: 2,
      borderDash: [6, 4],
      spanGaps: true,
      pointRadius: 0,
      pointHoverRadius: 3,
      tension: 0.25
    },
    {
      label: t('powerBalance.legend.net'),
      data: points.map((point) => point.balanceKw),
      borderColor: '#6ee7b7',
      backgroundColor: 'rgba(110, 231, 183, 0.15)',
      borderWidth: 2,
      spanGaps: true,
      pointRadius: 0,
      pointHoverRadius: 3,
      tension: 0.25
    }
  ]

  if (!chartInstance.value) {
    chartInstance.value = new Chart(chartCanvasRef.value, {
      type: 'line',
      data: {
        labels,
        datasets
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: false,
        interaction: {
          mode: 'index',
          intersect: false
        },
        plugins: {
          legend: {
            display: false
          },
          tooltip: {
            callbacks: {
              label: (context) => {
                const value = context.raw
                if (typeof value !== 'number' || !Number.isFinite(value)) {
                  return `${context.dataset.label}: -`
                }
                return `${context.dataset.label}: ${value.toLocaleString(locale.value, { maximumFractionDigits: 1 })} kW`
              }
            }
          }
        },
        scales: {
          x: {
            ticks: {
              color: '#94a3b8',
              maxTicksLimit: 5
            },
            grid: {
              color: 'rgba(148, 163, 184, 0.15)'
            }
          },
          y: {
            min: range.min,
            max: range.max,
            ticks: {
              color: '#94a3b8',
              stepSize: range.step,
              callback: (tickValue) => Number(tickValue).toLocaleString(locale.value)
            },
            grid: {
              color: 'rgba(148, 163, 184, 0.22)'
            }
          }
        }
      }
    })

    return
  }

  chartInstance.value.data.labels = labels
  chartInstance.value.data.datasets = datasets
  chartInstance.value.options.scales = {
    x: {
      ticks: {
        color: '#94a3b8',
        maxTicksLimit: 5
      },
      grid: {
        color: 'rgba(148, 163, 184, 0.15)'
      }
    },
    y: {
      min: range.min,
      max: range.max,
      ticks: {
        color: '#94a3b8',
        stepSize: range.step,
        callback: (tickValue) => Number(tickValue).toLocaleString(locale.value)
      },
      grid: {
        color: 'rgba(148, 163, 184, 0.22)'
      }
    }
  }
  chartInstance.value.update()
}

onMounted(() => {
  createOrUpdateChart()
})

watch([normalizedSeries, locale], () => {
  createOrUpdateChart()
}, { deep: true })

onBeforeUnmount(() => {
  chartInstance.value?.destroy()
  chartInstance.value = null
})
</script>

<template>
  <section class="panel-card">
    <div class="header-row">
      <h3 class="title">{{ t('powerBalance.title') }} <span class="sub-title">({{ t('powerBalance.subTitle24h') }})</span></h3>
      <span class="peak-label">{{ t('powerBalance.peakExpected') }} {{ peakTimeRange }}</span>
    </div>

    <div class="legend-row">
      <div class="legend-item">
        <span class="legend-line generation" />
        <span>{{ t('powerBalance.legend.generation') }}</span>
      </div>
      <div class="legend-item">
        <span class="legend-line demand" />
        <span>{{ t('powerBalance.legend.demand') }}</span>
      </div>
      <div class="legend-item">
        <span class="legend-line net" />
        <span>{{ t('powerBalance.legend.net') }}</span>
      </div>
      <span class="legend-unit">단위 : kW · 간격 : 1h</span>
    </div>

    <div v-if="isLoading" class="empty-state">{{ t('powerBalance.loading') }}</div>
    <div v-else-if="hasForecastData" class="chart-area">
      <div class="plot-wrap">
        <canvas ref="chartCanvasRef" class="plot-canvas" :aria-label="t('powerBalance.ariaLabel')" role="img" />
      </div>
    </div>
    <div v-else class="empty-state">{{ t('powerBalance.emptyState') }}</div>

    <p class="note">{{ t('powerBalance.note') }}</p>
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

.legend-unit {
  @apply ml-auto text-[10px] text-slate-400;
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

.plot-wrap {
  @apply flex min-w-0 flex-1 flex-col;
}

.plot-canvas {
  @apply h-[7.2rem] w-full;
}

.empty-state {
  @apply min-h-[8rem] rounded border border-slate-700 bg-slate-950/60 p-2 text-xs text-slate-400;
}

.note {
  @apply mt-2 text-[10px] text-slate-500;
}
</style>
