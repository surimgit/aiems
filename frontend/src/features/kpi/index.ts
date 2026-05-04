import type { PowerSummary } from '@/types/common'

export interface KpiSummaryItem {
  id: string
  label: string
  value: string
  trend?: string
}

export const buildKpiSummary = (powerSummary: PowerSummary | null, activeAlarmCount: number): KpiSummaryItem[] => {
  const netPower = powerSummary ? `${powerSummary.net_power_kw.toFixed(1)} kW` : '데이터 없음'
  const generation = powerSummary ? `${powerSummary.pv_power_kw.toFixed(1)} kW` : '데이터 없음'
  const load = powerSummary ? `${powerSummary.load_power_kw.toFixed(1)} kW` : '데이터 없음'
  const alertState = activeAlarmCount > 0 ? `${activeAlarmCount}건` : '정상'

  return [
    { id: 'net-power', label: '순전력', value: netPower },
    { id: 'generation', label: 'PV 발전', value: generation },
    { id: 'consumption', label: '부하 소비', value: load },
    { id: 'active-alarms', label: '활성 알람', value: alertState }
  ]
}
