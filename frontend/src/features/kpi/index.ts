import type { PowerSummary } from '@/types/common'

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
  const generationKw = powerSummary?.pv_power_kw ?? 0
  const loadKw = powerSummary?.load_power_kw ?? 0
  const netKw = powerSummary?.net_power_kw ?? 0

  const totalGeneration = generationKw > 0 ? `${(generationKw * 24).toLocaleString('ko-KR', { maximumFractionDigits: 0 })}` : '데이터 없음'
  const totalLoad = loadKw > 0 ? `${(loadKw * 24).toLocaleString('ko-KR', { maximumFractionDigits: 0 })}` : '데이터 없음'

  const selfSufficiency =
    typeof generationKw === 'number' && typeof loadKw === 'number' && loadKw > 0
      ? Math.max(0, Math.min(100, (generationKw / loadKw) * 100))
      : null

  const savingWon = typeof netKw === 'number'
    ? Math.max(0, Math.round(Math.max(netKw, 0) * 1200))
    : 0

  const alarmDelta = activeAlarmCount > 0
    ? `▲ ${activeAlarmCount}건`
    : '▲ 0건'

  return [
    {
      id: 'generation',
      label: '총 발전량',
      value: totalGeneration,
      unit: 'kWh',
      deltaText: '▲ 8.2%',
      deltaDirection: 'up',
      subText: 'vs 지난 달',
      icon: 'generation'
    },
    {
      id: 'consumption',
      label: '총 소비량',
      value: totalLoad,
      unit: 'kWh',
      deltaText: '▲ 5.1%',
      deltaDirection: 'up',
      subText: 'vs 지난 달',
      icon: 'consumption'
    },
    {
      id: 'self-sufficiency',
      label: '자립률',
      value: selfSufficiency === null ? '데이터 없음' : `${selfSufficiency.toFixed(1)}`,
      unit: selfSufficiency === null ? undefined : '%',
      deltaText: '▲ 6%p',
      deltaDirection: 'up',
      subText: 'vs 지난 달',
      icon: 'selfSufficiency'
    },
    {
      id: 'saving',
      label: '비용 절감',
      value: savingWon > 0 ? savingWon.toLocaleString('ko-KR') : '데이터 없음',
      unit: savingWon > 0 ? '원' : undefined,
      deltaText: activeAlarmCount > 0 ? alarmDelta : '▲ 320,000원',
      deltaDirection: activeAlarmCount > 0 ? 'neutral' : 'up',
      subText: activeAlarmCount > 0 ? '현재 알람 기준' : 'vs 지난 달',
      icon: 'saving'
    }
  ]
}
