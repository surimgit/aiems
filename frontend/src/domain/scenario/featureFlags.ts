export const FEATURE_KEYS = {
  FORECAST: 'forecast',
  KPI: 'kpi',
  AI_PERFORMANCE: 'aiPerformance',
  TOPOLOGY: 'topology',
  ALARM: 'alarm',
  DETAIL: 'detail',
  HISTORY: 'history',
  RECOMMENDATION: 'recommendation'
} as const

export type FeatureKey = (typeof FEATURE_KEYS)[keyof typeof FEATURE_KEYS]
