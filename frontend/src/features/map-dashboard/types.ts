import type { TopologyData } from '@/types/common'

export type EquipmentStatus = 'normal' | 'stopped' | 'error'
export type EquipmentType = 'GENERATOR' | 'ESS' | 'LOAD'

export interface MapEquipment {
  id: string
  name: string
  type: EquipmentType
  status: EquipmentStatus
  power: string
  lngLat: [number, number]
}

export type ConnectionDirection = 'FORWARD' | 'REVERSE' | 'BIDIRECTIONAL'

export interface MapConnection {
  id: string
  fromEquipmentId: string
  toEquipmentId: string
  direction: ConnectionDirection
  status: EquipmentStatus
}

export interface EquipmentFormData {
  id?: string
  name: string
  type: EquipmentType
  status: EquipmentStatus
  power: string
  lngLat: [number, number]
}

export interface MapDashboardTopologyPayload {
  topology: TopologyData | null
}
