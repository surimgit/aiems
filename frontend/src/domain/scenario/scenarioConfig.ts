import { FEATURE_KEYS, type FeatureKey } from './featureFlags'
import { SCENARIO_KEYS, type ScenarioKey } from './scenarioTypes'

export type ScenarioFeatureConfig = Record<FeatureKey, boolean>

const allOff = (): ScenarioFeatureConfig => ({
  [FEATURE_KEYS.FORECAST]: false,
  [FEATURE_KEYS.KPI]: false,
  [FEATURE_KEYS.AI_PERFORMANCE]: false,
  [FEATURE_KEYS.TOPOLOGY]: false,
  [FEATURE_KEYS.ALARM]: false,
  [FEATURE_KEYS.DETAIL]: false,
  [FEATURE_KEYS.HISTORY]: false,
  [FEATURE_KEYS.RECOMMENDATION]: false
})

const withEnabled = (enabled: FeatureKey[]): ScenarioFeatureConfig => {
  const config = allOff()
  enabled.forEach((featureKey) => {
    config[featureKey] = true
  })
  return config
}

export const scenarioConfig: Record<ScenarioKey, ScenarioFeatureConfig> = {
  [SCENARIO_KEYS.DEFAULT]: withEnabled([
    FEATURE_KEYS.FORECAST,
    FEATURE_KEYS.KPI,
    FEATURE_KEYS.AI_PERFORMANCE,
    FEATURE_KEYS.TOPOLOGY,
    FEATURE_KEYS.ALARM,
    FEATURE_KEYS.RECOMMENDATION
  ]),
  [SCENARIO_KEYS.SPACE]: withEnabled([
    FEATURE_KEYS.KPI,
    FEATURE_KEYS.AI_PERFORMANCE,
    FEATURE_KEYS.ALARM,
    FEATURE_KEYS.RECOMMENDATION
  ]),
  [SCENARIO_KEYS.ZOMBIE]: withEnabled([
    FEATURE_KEYS.FORECAST,
    FEATURE_KEYS.KPI,
    FEATURE_KEYS.ALARM,
    FEATURE_KEYS.HISTORY
  ]),
  [SCENARIO_KEYS.VEHICLE]: withEnabled([
    FEATURE_KEYS.KPI,
    FEATURE_KEYS.TOPOLOGY,
    FEATURE_KEYS.DETAIL,
    FEATURE_KEYS.RECOMMENDATION
  ])
}

export const isFeatureEnabled = (scenario: ScenarioKey, feature: FeatureKey): boolean => {
  return scenarioConfig[scenario][feature]
}
