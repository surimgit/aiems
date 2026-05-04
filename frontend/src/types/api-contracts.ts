/**
 * ProjectDocs HTTP contract DTOs
 * Source:
 * - ProjectDocs/11-api/*.md
 * - ProjectDocs/08-domain-detail/*.md
 * - ProjectDocs/07-appendix/enum-codes.md
 */

export type ResourceType =
  | 'LOAD'
  | 'SOLAR'
  | 'ESS'
  | 'DIESEL_GENERATOR'
  | 'SWITCH'
  | 'LINE'
  | 'GRID'

export type TopologyNodeType = 'GENERATION' | 'STORAGE' | 'LOAD' | 'GRID' | 'BUS'

export type TopologyNodeStatus = 'NORMAL' | 'WARNING' | 'EMERGENCY'

export type TopologyLineStatus = 'NORMAL' | 'OPEN' | 'BLOCKED' | 'FAULT' | 'UNKNOWN'

export type TopologySwitchPosition = 'OPEN' | 'CLOSED'

export type EventSeverity = 'INFO' | 'WARNING' | 'ALARM' | 'EMERGENCY'

export interface PositionDto {
  x: number
  y: number
}

export interface PlantSummaryDto {
  timestamp: string
  net_power_kw: number
  pv_power_kw: number
  ess_power_kw: number
  grid_power_kw: number
  load_power_kw: number
}

export interface ResourceDto {
  resource_id: string
  resource_type: ResourceType
  name?: string
  status?: string
  comms_health?: string
  position?: TopologySwitchPosition | 'UNKNOWN'
  controllable?: boolean
  interlock_blocked?: boolean
  from_node?: string
  to_node?: string
  flow_kw?: number
  import_kw?: number
  export_kw?: number
  limit_kw?: number
  telemetry?: {
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
}

export interface EssStatusDto {
  ess_id: string
  name?: string
  capacity_kwh: number
  max_power_kw: number
  soc: number
  soh?: number
  status: 'idle' | 'charging' | 'discharging' | 'fault'
  power_kw?: number
  created_at?: string
  updated_at?: string
}

export interface PlantStateDto {
  site_id: string
  timestamp: string
  ess_list?: EssStatusDto[]
  resources?: ResourceDto[]
  summary?: PlantSummaryDto
}

export interface TopologyNodeDto {
  node_id: string
  node_type: TopologyNodeType
  resource_id: string
  position: PositionDto
  status: TopologyNodeStatus
}

export interface TopologyLineDto {
  line_id: string
  from_node_id: string
  to_node_id: string
  direction: 'FORWARD' | 'REVERSE' | 'BIDIRECTIONAL'
  flow_kw: number
  status: TopologyLineStatus
}

export interface TopologySwitchDto {
  switch_id: string
  line_id: string
  position: TopologySwitchPosition
  controllable: boolean
  interlock_blocked: boolean
}

export interface TopologyDto {
  site_id: string
  nodes: TopologyNodeDto[]
  lines: TopologyLineDto[]
  switches?: TopologySwitchDto[]
}

export interface EventDto {
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
