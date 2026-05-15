/**
 * 대시보드 스토어
 * 
 * Responsibility:
 * - 전력 데이터 조회 관리
 * - ESS 상태 관리
 * - 실시간 데이터 업데이트
 */

import { defineStore } from 'pinia'
import { DEFAULT_SITE_ID } from '@/app/config'
import type { DeviceStateSnapshot, StateUpdateEvent } from '@/realtime/types'
import type { ResourceType, TopologySwitchPosition } from '@/types/api-contracts'
import type {
  DashboardData,
  ESSStatus,
  EventData,
  PowerSummary,
  ResourceInfo,
  TopologyData
} from '@/types/common'
import {
  getDashboardData,
  getEssStatusList,
  getEventList,
  getPowerSummary,
  getResources,
  getTopology
} from '@/api/dashboard.client'

const round2 = (value: number): number => Math.round(value * 100) / 100

const numberOrUndefined = (value: unknown): number | undefined => {
  if (typeof value === 'number' && Number.isFinite(value)) return value
  if (typeof value === 'string' && value.trim() !== '') {
    const parsed = Number(value)
    return Number.isFinite(parsed) ? parsed : undefined
  }
  return undefined
}

const stringOrUndefined = (value: unknown): string | undefined => {
  return typeof value === 'string' && value.length > 0 ? value : undefined
}

const booleanOrUndefined = (value: unknown): boolean | undefined => {
  return typeof value === 'boolean' ? value : undefined
}

const normalizeResourceType = (value: string | undefined): ResourceType | null => {
  const upper = (value ?? '').toUpperCase()
  if (upper === 'DIESEL') return 'DIESEL_GENERATOR'
  if (['LOAD', 'SOLAR', 'ESS', 'DIESEL_GENERATOR', 'SWITCH', 'LINE', 'GRID'].includes(upper)) {
    return upper as ResourceType
  }
  return null
}

const normalizeSwitchPosition = (value: unknown): TopologySwitchPosition | 'UNKNOWN' => {
  const upper = typeof value === 'string' ? value.toUpperCase() : ''
  return upper === 'OPEN' || upper === 'CLOSED' ? upper : 'UNKNOWN'
}

const snapshotStatus = (snapshot: DeviceStateSnapshot): string => {
  if (snapshot.emergency) return 'EMERGENCY'
  const comms = String(snapshot.comms_health ?? '').toLowerCase()
  if (comms === 'stale' || comms.includes('stale') || comms === 'offline') return 'OFFLINE'
  return 'NORMAL'
}

const resolveSnapshotFromEvent = (event: StateUpdateEvent): DeviceStateSnapshot | null => {
  const payload = event.data as unknown
  if (Array.isArray(payload)) {
    const first = payload[0]
    return first && typeof first === 'object' ? (first as DeviceStateSnapshot) : null
  }

  if (payload && typeof payload === 'object') {
    return payload as DeviceStateSnapshot
  }

  const topLevelCandidate: DeviceStateSnapshot = {
    site_id: event.site_id,
    edge_id: event.edge_id,
    device_id: event.device_id,
    resource_type: event.resource_type,
    location: event.location,
    latitude: event.latitude,
    longitude: event.longitude,
    timestamp: event.timestamp
  }

  return topLevelCandidate.device_id ? topLevelCandidate : null
}

const snapshotTimestamp = (snapshot: DeviceStateSnapshot, fallback?: string): string => {
  return snapshot.calculated_at ?? snapshot.timestamp ?? fallback ?? new Date().toISOString()
}

const mapSnapshotToResource = (snapshot: DeviceStateSnapshot): ResourceInfo | null => {
  if (!snapshot.device_id) return null

  const reported = snapshot.reported_state ?? {}
  const resourceType = normalizeResourceType(snapshot.resource_type)
  if (!resourceType) return null

  if (resourceType === 'SWITCH') {
    return {
      resource_id: snapshot.device_id,
      edge_id: snapshot.edge_id,
      resource_type: resourceType,
      name: snapshot.device_id,
      status: snapshotStatus(snapshot),
      comms_health: snapshot.comms_health,
      location: snapshot.location,
      latitude: snapshot.latitude,
      longitude: snapshot.longitude,
      position: normalizeSwitchPosition(reported.switch_state),
      controllable: booleanOrUndefined(reported.controllable),
      interlock_blocked: booleanOrUndefined(reported.interlock_blocked)
    }
  }

  const telemetry = {
    p_kw: numberOrUndefined(reported.P),
    q_kvar: numberOrUndefined(reported.Q),
    v_volt: numberOrUndefined(reported.V),
    i_amp: numberOrUndefined(reported.I),
    f_hz: numberOrUndefined(reported.f),
    pf: numberOrUndefined(reported.PF),
    soc: numberOrUndefined(reported.SOC),
    operating_mode: stringOrUndefined(reported.operating_mode)
  }

  return {
    resource_id: snapshot.device_id,
    edge_id: snapshot.edge_id,
    resource_type: resourceType,
    name: snapshot.device_id,
    status: snapshotStatus(snapshot),
    comms_health: snapshot.comms_health,
    location: snapshot.location,
    latitude: snapshot.latitude,
    longitude: snapshot.longitude,
    telemetry: Object.fromEntries(
      Object.entries(telemetry).filter(([, value]) => value !== undefined)
    ) as ResourceInfo['telemetry']
  }
}

const mapSnapshotToEss = (snapshot: DeviceStateSnapshot, fallbackTimestamp?: string): ESSStatus | null => {
  if (!snapshot.device_id || normalizeResourceType(snapshot.resource_type) !== 'ESS') return null

  const reported = snapshot.reported_state ?? {}
  const powerKw = numberOrUndefined(reported.P) ?? 0
  const soc = numberOrUndefined(reported.SOC) ?? 0
  const mode = String(reported.operating_mode ?? '').toLowerCase()
  const status: ESSStatus['status'] = snapshot.emergency
    ? 'fault'
    : mode === 'charge' || powerKw < 0
      ? 'charging'
      : mode === 'discharge' || powerKw > 0
        ? 'discharging'
        : 'idle'

  return {
    ess_id: snapshot.device_id,
    edge_id: snapshot.edge_id,
    name: snapshot.device_id,
    capacity_kwh: numberOrUndefined(reported.capacity_kwh) ?? 0,
    max_power_kw: numberOrUndefined(reported.power_limit_kw) ?? 0,
    soc,
    soh: numberOrUndefined(reported.SOH),
    status,
    power_kw: powerKw,
    location: snapshot.location,
    latitude: snapshot.latitude,
    longitude: snapshot.longitude,
    updated_at: snapshotTimestamp(snapshot, fallbackTimestamp)
  }
}

const computeSummaryFromResources = (
  siteId: string,
  resources: ResourceInfo[],
  timestamp: string
): PowerSummary => {
  let pvPower = 0
  let essPower = 0
  let loadPower = 0
  let dieselPower = 0

  resources.forEach((resource) => {
    const power = resource.telemetry?.p_kw ?? 0
    if (resource.resource_type === 'SOLAR') {
      pvPower += power
    } else if (resource.resource_type === 'ESS') {
      essPower += power
    } else if (resource.resource_type === 'LOAD') {
      loadPower += Math.abs(power)
    } else if (resource.resource_type === 'DIESEL_GENERATOR') {
      dieselPower += power
    }
  })

  return {
    timestamp,
    net_power_kw: round2(pvPower + essPower + dieselPower - loadPower),
    pv_power_kw: round2(pvPower),
    ess_power_kw: round2(essPower),
    grid_power_kw: 0,
    load_power_kw: round2(loadPower)
  }
}

const upsertById = <T>(items: T[], nextItem: T, idOf: (item: T) => string): T[] => {
  const targetId = idOf(nextItem)
  const index = items.findIndex((item) => idOf(item) === targetId)
  if (index === -1) return [...items, nextItem]

  const nextItems = [...items]
  nextItems[index] = {
    ...items[index],
    ...nextItem
  }
  return nextItems
}

interface DashboardState {
  siteId: string
  powerSummary: PowerSummary | null
  essList: ESSStatus[]
  resources: ResourceInfo[]
  topology: TopologyData | null
  events: EventData[]
  dashboardData: DashboardData | null
  loading: boolean
  error: string | null
  pollingInterval: number
  selectedEssId: string | null
  resourcesLastFetchedAt: number | null
  topologyLastFetchedAt: number | null
  resourcesFetchFailStreak: number
  topologyFetchFailStreak: number
}

interface DashboardGetters {
  netPower: number
  pvPower: number
  essPower: number
  gridPower: number
  loadPower: number
  essCount: number
  selectedEss: ESSStatus | null
  selectedResource: ResourceInfo | null
}

interface DashboardActions {
  setSiteId(siteId: string): void
  fetchPowerSummary(siteId?: string): Promise<void>
  fetchEssList(siteId?: string): Promise<void>
  fetchResources(siteId?: string): Promise<void>
  fetchTopology(siteId?: string): Promise<void>
  fetchEvents(siteId?: string): Promise<void>
  fetchDashboardData(siteId?: string): Promise<void>
  applyRealtimeStateUpdate(event: StateUpdateEvent): void
  startPolling(interval?: number): void
  stopPolling(): void
  selectEss(essId: string | null): void
}

export const useDashboardStore = defineStore(
  'dashboard',
  {
    state: (): DashboardState => ({
      siteId: DEFAULT_SITE_ID,
      powerSummary: null,
      essList: [],
      resources: [],
      topology: null,
      events: [],
      dashboardData: null,
      loading: false,
      error: null,
      pollingInterval: 5000,
      selectedEssId: null,
      resourcesLastFetchedAt: null,
      topologyLastFetchedAt: null,
      resourcesFetchFailStreak: 0,
      topologyFetchFailStreak: 0
    }),
    
    getters: {
      netPower(): number {
        return this.powerSummary?.net_power_kw ?? 0
      },
      
      pvPower(): number {
        return this.powerSummary?.pv_power_kw ?? 0
      },
      
      essPower(): number {
        return this.powerSummary?.ess_power_kw ?? 0
      },
      
      gridPower(): number {
        return this.powerSummary?.grid_power_kw ?? 0
      },
      
      loadPower(): number {
        return this.powerSummary?.load_power_kw ?? 0
      },
      
      essCount(): number {
        return this.essList.length
      },

      selectedEss(): ESSStatus | null {
        if (!this.selectedEssId) return null

        const topologyMatchedResourceId = this.topology?.nodes.find(
          (node) => node.node_id === this.selectedEssId || node.resource_id === this.selectedEssId
        )?.resource_id

        const candidateResourceIds = [this.selectedEssId, topologyMatchedResourceId].filter(
          (value): value is string => typeof value === 'string' && value.length > 0
        )

        return this.essList.find((ess) => candidateResourceIds.includes(ess.ess_id)) ?? null
      },

      selectedResource(): ResourceInfo | null {
        if (!this.selectedEssId) return null

        const topologyMatchedResourceId = this.topology?.nodes.find(
          (node) => node.node_id === this.selectedEssId || node.resource_id === this.selectedEssId
        )?.resource_id

        const candidateResourceIds = [this.selectedEssId, topologyMatchedResourceId].filter(
          (value): value is string => typeof value === 'string' && value.length > 0
        )

        const fromResources = this.resources.find((resource) =>
          candidateResourceIds.includes(resource.resource_id)
        )
        if (fromResources) return fromResources

        const ess = this.essList.find((item) => candidateResourceIds.includes(item.ess_id))
        if (!ess) return null

        return {
          resource_id: ess.ess_id,
          resource_type: 'ESS',
          name: ess.name,
          status: ess.status,
          telemetry: {
            soc: ess.soc,
            p_kw: ess.power_kw
          }
        }
      }
    },
    
    actions: {
      setSiteId(siteId: string): void {
        this.siteId = siteId
      },

      selectEss(essId: string | null): void {
        this.selectedEssId = essId
      },

      async fetchPowerSummary(siteId?: string): Promise<void> {
        this.loading = true
        this.error = null
        
        try {
          this.powerSummary = await getPowerSummary(siteId ?? this.siteId)
        } catch (error) {
          this.error = (error as Error).message
          console.error('[DashboardStore] Fetch power summary error:', error)
        } finally {
          this.loading = false
        }
      },
      
      async fetchEssList(siteId?: string): Promise<void> {
        this.loading = true
        this.error = null
        
        try {
          this.essList = await getEssStatusList(siteId ?? this.siteId)
        } catch (error) {
          this.error = (error as Error).message
          console.error('[DashboardStore] Fetch ESS list error:', error)
        } finally {
          this.loading = false
        }
      },

      async fetchResources(siteId?: string): Promise<void> {
        this.loading = true
        this.error = null

        try {
          this.resources = await getResources(siteId ?? this.siteId)
          this.resourcesLastFetchedAt = Date.now()
          this.resourcesFetchFailStreak = 0
        } catch (error) {
          this.error = (error as Error).message
          this.resourcesFetchFailStreak += 1
          console.error('[DashboardStore] Fetch resources error:', error)
        } finally {
          this.loading = false
        }
      },

      async fetchTopology(siteId?: string): Promise<void> {
        this.loading = true
        this.error = null

        try {
          this.topology = await getTopology(siteId ?? this.siteId)
          this.topologyLastFetchedAt = Date.now()
          this.topologyFetchFailStreak = 0
        } catch (error) {
          this.error = (error as Error).message
          this.topologyFetchFailStreak += 1
          console.error('[DashboardStore] Fetch topology error:', error)
        } finally {
          this.loading = false
        }
      },

      async fetchEvents(siteId?: string): Promise<void> {
        this.loading = true
        this.error = null

        try {
          this.events = await getEventList(siteId ?? this.siteId)
        } catch (error) {
          this.error = (error as Error).message
          console.error('[DashboardStore] Fetch events error:', error)
        } finally {
          this.loading = false
        }
      },
      
      async fetchDashboardData(siteId?: string): Promise<void> {
        this.loading = true
        this.error = null
        
        try {
          this.dashboardData = await getDashboardData(siteId ?? this.siteId)
          this.resources = this.dashboardData.ess_list.map((ess) => ({
            resource_id: ess.ess_id,
            resource_type: 'ESS',
            name: ess.name,
            status: ess.status,
            telemetry: {
              soc: ess.soc
            }
          }))
        } catch (error) {
          this.error = (error as Error).message
          console.error('[DashboardStore] Fetch dashboard data error:', error)
        } finally {
          this.loading = false
        }
      },

      applyRealtimeStateUpdate(event: StateUpdateEvent): void {
        const snapshot = resolveSnapshotFromEvent(event)
        if (!snapshot) return
        if (snapshot.site_id && snapshot.site_id !== this.siteId) return

        const resource = mapSnapshotToResource(snapshot)
        if (!resource) return

        this.resources = upsertById(this.resources, resource, (item) => item.resource_id)
        this.resourcesLastFetchedAt = Date.now()
        this.resourcesFetchFailStreak = 0

        const ess = mapSnapshotToEss(snapshot, event.timestamp)
        if (ess) {
          this.essList = upsertById(this.essList, ess, (item) => item.ess_id)
        }

        this.powerSummary = computeSummaryFromResources(
          this.siteId,
          this.resources,
          snapshotTimestamp(snapshot, event.timestamp)
        )
      },

      startPolling(interval?: number): void {
        console.warn('[DashboardStore] startPolling is deprecated. Use overview realtime source instead.', interval)
      },

      stopPolling(): void {
        // TODO: Polling 정지 로직 구현
      }
    }
  }
)

export default useDashboardStore
