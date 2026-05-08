import type { PowerSummary } from '@/types/common'
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

export const buildKpiSummary = (powerSummary: PowerSummary | null, activeAlarmCount: number): KpiSummaryItem[] => {
  const locale = i18n.global.locale.value === 'en' ? 'en-US' : 'ko-KR'
  const t = i18n.global.t

  const generationKw = powerSummary?.pv_power_kw ?? 0
  const loadKw = powerSummary?.load_power_kw ?? 0
  const netKw = powerSummary?.net_power_kw ?? 0

  const totalGeneration = generationKw > 0 ? `${(generationKw * 24).toLocaleString(locale, { maximumFractionDigits: 0 })}` : t('common.noData')
  const totalLoad = loadKw > 0 ? `${(loadKw * 24).toLocaleString(locale, { maximumFractionDigits: 0 })}` : t('common.noData')

  const selfSufficiency =
    typeof generationKw === 'number' && typeof loadKw === 'number' && loadKw > 0
      ? Math.max(0, Math.min(100, (generationKw / loadKw) * 100))
      : null

  const savingWon = typeof netKw === 'number'
    ? Math.max(0, Math.round(Math.max(netKw, 0) * 1200))
    : 0

  const alarmDelta = activeAlarmCount > 0
    ? `▲ ${activeAlarmCount}${t('kpi.units.count')}`
    : `▲ 0${t('kpi.units.count')}`

  return [
    {
      id: 'generation',
      label: t('kpi.items.generation.label'),
      value: totalGeneration,
      unit: t('kpi.units.kwh'),
      deltaText: '▲ 8.2%',
      deltaDirection: 'up',
      subText: t('kpi.subText.vsLastMonth'),
      icon: 'generation'
    },
    {
      id: 'consumption',
      label: t('kpi.items.consumption.label'),
      value: totalLoad,
      unit: t('kpi.units.kwh'),
      deltaText: '▲ 5.1%',
      deltaDirection: 'up',
      subText: t('kpi.subText.vsLastMonth'),
      icon: 'consumption'
    },
    {
      id: 'self-sufficiency',
      label: t('kpi.items.selfSufficiency.label'),
      value: selfSufficiency === null ? t('common.noData') : `${selfSufficiency.toFixed(1)}`,
      unit: selfSufficiency === null ? undefined : '%',
      deltaText: '▲ 6%p',
      deltaDirection: 'up',
      subText: t('kpi.subText.vsLastMonth'),
      icon: 'selfSufficiency'
    },
    {
      id: 'saving',
      label: t('kpi.items.saving.label'),
      value: savingWon > 0 ? savingWon.toLocaleString(locale) : t('common.noData'),
      unit: savingWon > 0 ? t('kpi.units.won') : undefined,
      deltaText: activeAlarmCount > 0 ? alarmDelta : `▲ ${locale === 'en-US' ? '320,000 KRW' : '320,000원'}`,
      deltaDirection: activeAlarmCount > 0 ? 'neutral' : 'up',
      subText: activeAlarmCount > 0 ? t('kpi.subText.basedOnCurrentAlarm') : t('kpi.subText.vsLastMonth'),
      icon: 'saving'
    }
  ]
}
