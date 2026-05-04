import type { PowerSummary } from '@/types/common'

export interface KpiSummaryItem {
  id: string
  label: string
  value: string
  trend?: string
}

const formatKw = (value: unknown): string => {
  if (typeof value !== 'number' || Number.isNaN(value)) {
    return '데이터 없음'
  }
  return `${value.toFixed(1)} kW`
}

export const buildKpiSummary = (powerSummary: PowerSummary | null, activeAlarmCount: number): KpiSummaryItem[] => {
  const netPower = formatKw(powerSummary?.net_power_kw)
  const generation = formatKw(powerSummary?.pv_power_kw)
  const load = formatKw(powerSummary?.load_power_kw)
  const alertState = activeAlarmCount > 0 ? `${activeAlarmCount}건` : '정상'

  return [
    { id: 'net-power', label: '순전력', value: netPower },
    { id: 'generation', label: 'PV 발전', value: generation },
    { id: 'consumption', label: '부하 소비', value: load },
    { id: 'active-alarms', label: '활성 알람', value: alertState }
  ]
}
