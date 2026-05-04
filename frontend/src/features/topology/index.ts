/**
 * 토폴로지 (Topology) 피처
 * 
 * Responsibility:
 * - 설비 배치 및 연관 관계 데이터 제공
 */

import { computed, type ComputedRef } from 'vue'
import { useDashboardStore } from '@/stores/dashboard/dashboard.store'
import type { TopologyData } from '@/types/common'

export interface TopologyNode {
  id: string
  type: 'ess' | 'pv' | 'grid' | 'load'
  name: string
  power: number
  status: string
}

export interface TopologyLink {
  source: string
  target: string
  power: number
}

export interface UseTopologyFeature {
  topology: ComputedRef<TopologyData | null>
  nodes: ComputedRef<TopologyNode[]>
  links: ComputedRef<TopologyLink[]>
  initialize: () => Promise<void>
  selectNode: (nodeId: string) => void
}

export const useTopologyFeature = (): UseTopologyFeature => {
  const dashboardStore = useDashboardStore()
  
  const nodes = computed((): TopologyNode[] => {
    const topology = dashboardStore.topology
    if (topology && topology.nodes.length > 0) {
      return topology.nodes.map((node) => ({
        id: node.resource_id,
        type:
          node.node_type === 'STORAGE'
            ? 'ess'
            : node.node_type === 'GRID'
              ? 'grid'
              : node.node_type === 'LOAD'
                ? 'load'
                : 'pv',
        name: node.resource_id,
        power: 0,
        status: node.status
      }))
    }

    const summary = dashboardStore.powerSummary
    if (!summary) return []
    
    return [
      { id: 'grid', type: 'grid', name: 'Grid', power: summary.grid_power_kw, status: 'connected' },
      { id: 'pv', type: 'pv', name: 'PV', power: summary.pv_power_kw, status: 'producing' },
      { id: 'ess', type: 'ess', name: 'ESS', power: summary.ess_power_kw, status: 'active' },
      { id: 'load', type: 'load', name: 'Load', power: summary.load_power_kw, status: 'active' }
    ]
  })
  
  const links = computed((): TopologyLink[] => {
    const topology = dashboardStore.topology
    if (topology && topology.lines.length > 0) {
      return topology.lines.map((line) => ({
        source: line.from_node_id,
        target: line.to_node_id,
        power: line.flow_kw
      }))
    }

    const summary = dashboardStore.powerSummary
    if (!summary) return []
    
    return [
      { source: 'pv', target: 'ess', power: summary.pv_power_kw },
      { source: 'pv', target: 'load', power: summary.load_power_kw },
      { source: 'grid', target: 'load', power: summary.grid_power_kw > 0 ? summary.grid_power_kw : 0 }
    ].filter(link => link.power > 0)
  })
  
  const initialize = async (): Promise<void> => {
    await Promise.all([
      dashboardStore.fetchTopology(),
      dashboardStore.fetchPowerSummary()
    ])
  }

  const topology = computed(() => dashboardStore.topology)

  const selectNode = (nodeId: string) => {
    dashboardStore.selectEss(nodeId)
  }

  return {
    topology,
    nodes,
    links,
    initialize,
    selectNode
  }
}

export default useTopologyFeature
