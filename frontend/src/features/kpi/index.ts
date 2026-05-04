export interface KpiSummaryItem {
  id: string
  label: string
  value: string
  trend?: string
}

export const buildKpiSummary = (): KpiSummaryItem[] => {
  return [
    { id: 'total-generation', label: '총 발전량', value: '--' },
    { id: 'total-consumption', label: '총 소비량', value: '--' },
    { id: 'self-sufficiency', label: '자립률', value: '--' },
    { id: 'cost-saving', label: '비용 절감', value: '--' }
  ]
}
