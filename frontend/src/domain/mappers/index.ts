/**
 * API DTO -> UI/domain mapper
 */

import type {
  EventDto,
  PlantSummaryDto,
  ResourceDto,
  TopologyDto
} from '@/types/api-contracts'
import type {
  EventData,
  ForecastData,
  PowerSummary,
  ResourceInfo,
  TopologyData
} from '@/types/common'

export const mapPowerSummaryDto = (dto: PlantSummaryDto): PowerSummary => ({
  timestamp: dto.timestamp,
  net_power_kw: dto.net_power_kw,
  pv_power_kw: dto.pv_power_kw,
  ess_power_kw: dto.ess_power_kw,
  grid_power_kw: dto.grid_power_kw,
  load_power_kw: dto.load_power_kw
})

export const mapResourceDto = (dto: ResourceDto): ResourceInfo => ({
  // backend/simulator variations normalize
  // - DIESEL -> DIESEL_GENERATOR
  // - lowercase types/status -> uppercase
  resource_id: dto.resource_id,
  edge_id: dto.edge_id,
  resource_type: ((dto.resource_type ?? '').toUpperCase() === 'DIESEL'
    ? 'DIESEL_GENERATOR'
    : (dto.resource_type ?? '').toUpperCase()) as ResourceInfo['resource_type'],
  name: dto.name,
  status: dto.status ? dto.status.toUpperCase() : dto.status,
  comms_health: dto.comms_health,
  location: dto.location,
  latitude: dto.latitude,
  longitude: dto.longitude,
  position: dto.position,
  controllable: dto.controllable,
  interlock_blocked: dto.interlock_blocked,
  from_node: dto.from_node,
  to_node: dto.to_node,
  flow_kw: dto.flow_kw,
  import_kw: dto.import_kw,
  export_kw: dto.export_kw,
  limit_kw: dto.limit_kw,
  telemetry: dto.telemetry
})

export const mapEventDto = (dto: EventDto): EventData => ({
  event_id: dto.event_id,
  event_code: dto.event_code,
  severity: dto.severity,
  message: dto.message,
  timestamp: dto.timestamp,
  site_id: dto.site_id,
  resource_id: dto.resource_id,
  trace_id: dto.trace_id,
  reason_code: dto.reason_code,
  payload: dto.payload
})

export const mapTopologyDto = (dto: TopologyDto): TopologyData => {
  const safeNodes = Array.isArray(dto?.nodes) ? dto.nodes : []
  const safeLines = Array.isArray(dto?.lines) ? dto.lines : []
  const safeSwitches = Array.isArray(dto?.switches) ? dto.switches : []

  return {
    site_id: dto?.site_id ?? 'unknown',
    nodes: safeNodes.map((node) => ({
    node_id: node.node_id,
    node_type: node.node_type,
    resource_id: node.resource_id,
    position: { x: node.position.x, y: node.position.y },
    status: node.status
    })),
    lines: safeLines.map((line) => ({
    line_id: line.line_id,
    from_node_id: line.from_node_id,
    to_node_id: line.to_node_id,
    direction: line.direction,
    flow_kw: line.flow_kw,
    status: line.status
    })),
    switches: safeSwitches.map((sw) => ({
    switch_id: sw.switch_id,
    line_id: sw.line_id,
    position: sw.position,
    controllable: sw.controllable,
    interlock_blocked: sw.interlock_blocked
    }))
  }
}

export const mapForecastSeriesToUi = (
  points: Array<{ timestamp: string; generation_kw?: number; load_kw?: number }>,
  confidence?: number
): ForecastData[] => {
  const result: ForecastData[] = []
  for (const point of points) {
    if (typeof point.generation_kw === 'number') {
      result.push({
        timestamp: point.timestamp,
        type: 'generation',
        predicted_kw: point.generation_kw,
        confidence
      })
    }
    if (typeof point.load_kw === 'number') {
      result.push({
        timestamp: point.timestamp,
        type: 'demand',
        predicted_kw: point.load_kw,
        confidence
      })
    }
  }
  return result
}
