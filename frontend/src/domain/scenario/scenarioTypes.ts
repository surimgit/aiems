export const SCENARIO_KEYS = {
  DEFAULT: 'default',
  SPACE: 'space',
  ZOMBIE: 'zombie',
  VEHICLE: 'vehicle'
} as const

export type ScenarioKey = (typeof SCENARIO_KEYS)[keyof typeof SCENARIO_KEYS]
