import type { PowerSummary, ResourceInfo } from '@/types/common'
import i18n from '@/app/i18n'

export interface KpiSummaryItem {
  id: string
  label: string
  value: string
  unit?: string
  deltaText?: string
  deltaDirection?: 'up' | 'down' | 'neutral'
  subText?: string
  icon?: 'generation' | 'consumption' | 'selfSufficiency' | 'saving'
}

type MonthlyAccumulator = {
  monthKey: string
  lastTs: number
  generationKwh: number
  consumptionKwh: number
  gridImportKwh: number
}

type MonthlySnapshot = {
  monthKey: string
  generationKwh: number
  consumptionKwh: number
  selfSufficiencyPct: number
  savingsWon: number
}

const ACC_KEY = 'ems:kpi:acc:v3'
const HIST_KEY = 'ems:kpi:hist:v3'
const TARIFF_WON_PER_KWH = 150
const SOLAR_SUN_HOURS_PER_DAY = 3.5
const MAX_ELAPSED_HOURS = 1 / 6

const toFinite = (value: unknown): number => (typeof value === 'number' && Number.isFinite(value) ? value : 0)

const monthKeyOf = (d: Date): string => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`

const loadJson = <T>(key: string, fallback: T): T => {
  if (typeof window === 'undefined') return fallback
  try {
    const raw = window.localStorage.getItem(key)
    if (!raw) return fallback
    return JSON.parse(raw) as T
  } catch {
    return fallback
  }
}

const saveJson = (key: string, value: unknown) => {
  if (typeof window === 'undefined') return
  window.localStorage.setItem(key, JSON.stringify(value))
}

const initAccumulator = (monthKey: string, now: number): MonthlyAccumulator => ({
  monthKey,
  lastTs: now,
  generationKwh: 0,
  consumptionKwh: 0,
  gridImportKwh: 0
})

const loadAccumulator = (monthKey: string, now: number): MonthlyAccumulator => {
  const loaded = loadJson<MonthlyAccumulator | null>(ACC_KEY, null)
  if (!loaded || typeof loaded.monthKey !== 'string') return initAccumulator(monthKey, now)
  return loaded
}

const calcSelfSufficiencyPct = (consumptionKwh: number, gridImportKwh: number): number => {
  if (consumptionKwh <= 0) return 0
  return Math.max(0, Math.min(100, (1 - gridImportKwh / consumptionKwh) * 100))
}

const calcSavingsWon = (consumptionKwh: number, gridImportKwh: number): number => {
  const localSupplyKwh = Math.max(0, consumptionKwh - gridImportKwh)
  return Math.round(localSupplyKwh * TARIFF_WON_PER_KWH)
}

const directionFromDelta = (text: string): 'up' | 'down' | 'neutral' => {
  if (text.startsWith('▲')) return 'up'
  if (text.startsWith('▼')) return 'down'
  return 'neutral'
}

const percentDeltaText = (current: number, previous: number): string => {
  if (previous <= 0) return '—'
  const pct = ((current - previous) / previous) * 100
  return `${pct >= 0 ? '▲' : '▼'} ${Math.abs(pct).toFixed(1)}%`
}

const pointDeltaText = (current: number, previous: number): string => {
  const diff = current - previous
  return `${diff >= 0 ? '▲' : '▼'} ${Math.abs(diff).toFixed(1)}%p`
}

const wonDeltaText = (current: number, previous: number, locale: string): string => {
  const diff = current - previous
  return `${diff >= 0 ? '▲' : '▼'} ${Math.abs(Math.round(diff)).toLocaleString(locale)}원`
}

const currentKwByType = (resources: ResourceInfo[], type: ResourceInfo['resource_type']): number => {
  return resources
    .filter((resource) => resource.resource_type === type)
    .reduce((sum, resource) => sum + Math.max(0, toFinite(resource.telemetry?.p_kw)), 0)
}

const solarInstalledKw = (resources: ResourceInfo[]): number => {
  const solar = resources.filter((resource) => resource.resource_type === 'SOLAR')
  const fromLimit = solar.reduce((sum, resource) => sum + Math.max(0, toFinite(resource.limit_kw)), 0)
  if (fromLimit > 0) return fromLimit
  return solar.reduce((sum, resource) => sum + Math.max(0, toFinite(resource.telemetry?.p_kw)), 0)
}

export const buildKpiSummary = (
  powerSummary: PowerSummary | null,
  resources: ResourceInfo[],
  _activeAlarmCount: number
): KpiSummaryItem[] => {
  const locale = i18n.global.locale.value === 'en' ? 'en-US' : 'ko-KR'
  const t = i18n.global.t

  const now = Date.now()
  const monthKey = monthKeyOf(new Date(now))

  const solarKw = currentKwByType(resources, 'SOLAR')
  const dieselKw = currentKwByType(resources, 'DIESEL_GENERATOR')
  const generationKw = solarKw + dieselKw
  const consumptionKw = Math.max(0, toFinite(powerSummary?.load_power_kw))
  const gridImportKw = Math.max(0, toFinite(powerSummary?.grid_power_kw))

  let acc = loadAccumulator(monthKey, now)
  const history = loadJson<MonthlySnapshot[]>(HIST_KEY, [])

  if (acc.monthKey !== monthKey) {
    const previousMonth: MonthlySnapshot = {
      monthKey: acc.monthKey,
      generationKwh: acc.generationKwh,
      consumptionKwh: acc.consumptionKwh,
      selfSufficiencyPct: calcSelfSufficiencyPct(acc.consumptionKwh, acc.gridImportKwh),
      savingsWon: calcSavingsWon(acc.consumptionKwh, acc.gridImportKwh)
    }
    const merged = [...history.filter((item) => item.monthKey !== previousMonth.monthKey), previousMonth]
      .sort((a, b) => a.monthKey.localeCompare(b.monthKey))
      .slice(-12)
    saveJson(HIST_KEY, merged)
    acc = initAccumulator(monthKey, now)
  }

  const elapsedHours = Math.max(0, Math.min(MAX_ELAPSED_HOURS, (now - acc.lastTs) / (1000 * 60 * 60)))
  acc.generationKwh += generationKw * elapsedHours
  acc.consumptionKwh += consumptionKw * elapsedHours
  acc.gridImportKwh += gridImportKw * elapsedHours
  acc.lastTs = now
  saveJson(ACC_KEY, acc)

  const selfSufficiencyPct = calcSelfSufficiencyPct(acc.consumptionKwh, acc.gridImportKwh)
  const savingsWon = calcSavingsWon(acc.consumptionKwh, acc.gridImportKwh)

  const snapshots = loadJson<MonthlySnapshot[]>(HIST_KEY, []).sort((a, b) => a.monthKey.localeCompare(b.monthKey))
  const previous = snapshots.length > 0 ? snapshots[snapshots.length - 1] : null

  const generationDelta = previous ? percentDeltaText(acc.generationKwh, previous.generationKwh) : '—'
  const consumptionDelta = previous ? percentDeltaText(acc.consumptionKwh, previous.consumptionKwh) : '—'
  const selfSufficiencyDelta = previous ? pointDeltaText(selfSufficiencyPct, previous.selfSufficiencyPct) : '—'
  const savingsDelta = previous ? wonDeltaText(savingsWon, previous.savingsWon, locale) : '—'

  const today = new Date(now)
  const elapsedDays = today.getDate()
  const solarBaseline = solarInstalledKw(resources) * SOLAR_SUN_HOURS_PER_DAY * elapsedDays

  return [
    {
      id: 'generation',
      label: t('kpi.items.generation.label'),
      value: Math.round(acc.generationKwh).toLocaleString(locale),
      unit: t('kpi.units.kwh'),
      deltaText: generationDelta,
      deltaDirection: directionFromDelta(generationDelta),
      subText:
        solarBaseline > 0
          ? `예상 태양광(MTD) ${Math.round(solarBaseline).toLocaleString(locale)} kWh`
          : t('kpi.subText.vsLastMonth'),
      icon: 'generation'
    },
    {
      id: 'consumption',
      label: t('kpi.items.consumption.label'),
      value: Math.round(acc.consumptionKwh).toLocaleString(locale),
      unit: t('kpi.units.kwh'),
      deltaText: consumptionDelta,
      deltaDirection: directionFromDelta(consumptionDelta),
      subText: t('kpi.subText.vsLastMonth'),
      icon: 'consumption'
    },
    {
      id: 'self-sufficiency',
      label: t('kpi.items.selfSufficiency.label'),
      value: selfSufficiencyPct.toFixed(1),
      unit: '%',
      deltaText: selfSufficiencyDelta,
      deltaDirection: directionFromDelta(selfSufficiencyDelta),
      subText: t('kpi.subText.vsLastMonth'),
      icon: 'selfSufficiency'
    },
    {
      id: 'saving',
      label: t('kpi.items.saving.label'),
      value: savingsWon > 0 ? savingsWon.toLocaleString(locale) : t('common.noData'),
      unit: savingsWon > 0 ? t('kpi.units.won') : undefined,
      deltaText: savingsDelta,
      deltaDirection: directionFromDelta(savingsDelta),
      subText: t('kpi.subText.vsLastMonth'),
      icon: 'saving'
    }
  ]
}
