/**
 * UI/domain-facing types.
 * Contract DTO types are defined in `types/api-contracts.ts`.
 */

import type {
  EventSeverity,
  ResourceType,
  TopologyLineStatus,
  TopologyNodeStatus,
  TopologyNodeType,
  TopologySwitchPosition
} from './api-contracts'

// ============ Power ============

export interface PowerSummary {
  timestamp: string
  net_power_kw: number
  pv_power_kw: number
  ess_power_kw: number
  grid_power_kw: number
  load_power_kw: number
}

export interface PowerData extends PowerSummary {}

// ============ Core plant/resource ============

export interface ESSStatus {
  ess_id: string
  edge_id?: string
  name?: string
  capacity_kwh: number
  max_power_kw: number
  soc: number
  soh?: number
  status: 'idle' | 'charging' | 'discharging' | 'fault'
  power_kw?: number
  location?: Record<string, unknown> | null
  latitude?: number | null
  longitude?: number | null
  created_at?: string
  updated_at?: string
}

export interface PlantInfo {
  site_id: string
  name?: string
  location?: string
}

export interface ResourceMetrics {
  p_kw?: number
  q_kvar?: number
  v_volt?: number
  i_amp?: number
  f_hz?: number
  pf?: number
  kwh?: number
  soc?: number
  operating_mode?: string
}

export interface ResourceInfo {
  resource_id: string
  edge_id?: string
  resource_type: ResourceType
  name?: string
  status?: string
  comms_health?: string
  location?: Record<string, unknown> | null
  latitude?: number | null
  longitude?: number | null
  position?: TopologySwitchPosition | 'UNKNOWN'
  controllable?: boolean
  interlock_blocked?: boolean
  from_node?: string
  to_node?: string
  flow_kw?: number
  import_kw?: number
  export_kw?: number
  limit_kw?: number
  telemetry?: ResourceMetrics
}

export interface PlantState {
  site_id: string
  timestamp: string
  ess_list?: ESSStatus[]
  resources?: ResourceInfo[]
  summary?: PowerSummary
}

// ============ Topology ============

export interface TopologyPosition {
  x: number
  y: number
}

export interface TopologyNode {
  node_id: string
  node_type: TopologyNodeType
  resource_id: string
  position: TopologyPosition
  status: TopologyNodeStatus
}

export interface TopologyLine {
  line_id: string
  from_node_id: string
  to_node_id: string
  direction: 'FORWARD' | 'REVERSE' | 'BIDIRECTIONAL'
  flow_kw: number
  status: TopologyLineStatus
}

export interface TopologySwitch {
  switch_id: string
  line_id: string
  position: TopologySwitchPosition
  controllable: boolean
  interlock_blocked: boolean
}

export interface TopologyData {
  site_id: string
  nodes: TopologyNode[]
  lines: TopologyLine[]
  switches: TopologySwitch[]
}

// ============ Event/Alarm ============

export interface EventData {
  event_id: string
  event_code: string
  severity: EventSeverity
  message?: string
  timestamp: string
  site_id?: string
  resource_id?: string
  trace_id?: string
  reason_code?: string
  payload?: Record<string, unknown>
}

export interface AlarmData {
  alarm_id?: string
  level: 'info' | 'warning' | 'critical'
  code: string
  message: string
  ess_id?: string
  device_id?: string
  resource_type?: ResourceType
  timestamp: string
  acknowledged?: boolean
}

// ============ Control ============

export type CommandAction =
  | 'START_CHARGE'
  | 'STOP_CHARGE'
  | 'START_DISCHARGE'
  | 'STOP_DISCHARGE'
  | 'START_GENERATOR'
  | 'STOP_GENERATOR'
  | 'OPEN_SWITCH'
  | 'CLOSE_SWITCH'
  | 'SHED_LOAD'
  | 'RESTORE_LOAD'
  | 'SET_POWER_LIMIT'
  | 'STANDBY'

export type CommandStatus =
  | 'CREATED'
  | 'SENT'
  | 'ACCEPTED'
  | 'REJECTED'
  | 'IN_PROGRESS'
  | 'RUNNING'
  | 'COMPLETED'
  | 'FAILED'
  | 'TIMED_OUT'
  | 'IGNORED'
  | 'BLOCKED'
  | 'EXPIRED'

export interface ControlCommand {
  action: CommandAction
  power_kw?: number
  duration_min?: number
}

export interface OperatorCommandRequest {
  site_id: string
  device_id: string
  resource_type: ResourceType
  action: CommandAction
  requested_by: string
  reason?: string
  source_recommendation_id?: string | null
}

export interface ControlResult {
  command_id: string
  status: CommandStatus
  site_id: string
  device_id?: string
  target_resource_id: string
  action: CommandAction
  created_at: string
  issued_by?: string | null
}

// ============ AI ============

export interface ForecastData {
  timestamp: string
  type: 'generation' | 'demand'
  predicted_kw: number
  confidence?: number
}

export interface ForecastContract {
  message_type: 'forecast'
  schema_version: string
  forecast_id: string
  site_id: string
  created_at: string
  horizon: string
  interval: string
  targets: string[]
  series: Array<{
    timestamp: string
    load_kw?: number
    generation_kw?: number
    ess_soc?: number
    net_power_kw?: number
  }>
  confidence?: number
}

export interface Recommendation {
  recommendation_id: string
  action: string
  confidence: number
  priority: 'high' | 'medium' | 'low'
  valid_for_sec: number
  expected_effect: string
  reason: string
}

export interface InferenceRequest {
  site_id: string
  targets: string[]
  horizon: string
  interval: string
}

export interface InferenceResult {
  message_type: 'inference_result'
  schema_version: string
  inference_id: string
  site_id: string
  model_id: string
  model_version: string
  created_at: string
  status: CommandStatus
  forecast_id?: string
  recommendation_ids?: string[]
  error_code?: string
  error_message?: string
}

export interface InferenceAcceptedResponse {
  inference_id: string
  status: CommandStatus
  site_id: string
  created_at: string
}

export interface SiteLatestAi {
  site_id: string
  inference?: InferenceResult
  forecasts?: ForecastContract[]
  recommendations?: Recommendation[]
}

export interface DashboardData {
  power_summary: PowerSummary
  ess_list: ESSStatus[]
  active_alarms: AlarmData[]
  generation_forecast?: ForecastContract[]
  demand_forecast?: ForecastContract[]
  recommendations?: Recommendation[]
}
