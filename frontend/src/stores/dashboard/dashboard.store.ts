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
  getTopology,
  startPowerPolling
} from '@/api/dashboard.client'

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
      selectedEssId: null
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
        } catch (error) {
          this.error = (error as Error).message
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
        } catch (error) {
          this.error = (error as Error).message
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
      
      startPolling(interval?: number): void {
        const intervalMs = interval ?? this.pollingInterval
        
        startPowerPolling(
          this.siteId,
          intervalMs,
          (data) => {
            this.powerSummary = data
          },
          (error) => {
            console.error('[DashboardStore] Polling error:', error)
          }
        )
      },
      
      stopPolling(): void {
        // TODO: Polling 정지 로직 구현
      }
    }
  }
)

export default useDashboardStore
