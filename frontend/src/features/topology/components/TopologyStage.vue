<template>
  <div class="relative h-full w-full overflow-hidden rounded-xl border border-white/10 bg-slate-950">
    <div
      class="absolute left-3 top-3 z-30 rounded-lg border border-slate-700 bg-slate-900/80 p-2 text-xs text-slate-100 backdrop-blur"
      :class="isControlCollapsed ? 'w-[96px]' : 'w-[208px]'"
    >
      <div v-if="isControlCollapsed" class="flex justify-center">
        <button type="button" class="w-full rounded bg-slate-700 px-2 py-1 font-semibold" @click="handleExpand">
          펼치기
        </button>
      </div>

      <div v-else>
        <div class="mb-2 flex items-center justify-between">
          <strong>Map</strong>
          <button type="button" class="rounded bg-rose-700 px-2 py-1 font-semibold" @click="handleComplete">
            완료
          </button>
        </div>

        <div class="mb-2 grid grid-cols-2 gap-1.5">
          <button
            type="button"
            class="rounded px-2 py-1 font-semibold"
            :class="isAddArmed ? 'bg-emerald-600' : 'bg-slate-700'"
            @click="toggleAddArmed"
          >
            {{ isAddArmed ? '추가 대기중' : '장비 추가' }}
          </button>
          <button
            type="button"
            class="rounded bg-slate-700 px-2 py-1 font-semibold"
            :disabled="!isAddArmed"
            @click="isAddArmed = false"
          >
            취소
          </button>
        </div>

        <div class="rounded border border-white/10 p-2">
          <p class="mb-1 text-slate-300">선 연결/방향</p>
          <div class="mb-1 grid grid-cols-2 gap-1.5">
            <select v-model="connectForm.fromEquipmentId" class="rounded bg-slate-800 px-2 py-1">
              <option value="">from</option>
              <option v-for="eq in equipmentData" :key="`f-${eq.id}`" :value="eq.id">{{ eq.name }}</option>
            </select>
            <select v-model="connectForm.toEquipmentId" class="rounded bg-slate-800 px-2 py-1">
              <option value="">to</option>
              <option v-for="eq in equipmentData" :key="`t-${eq.id}`" :value="eq.id">{{ eq.name }}</option>
            </select>
          </div>
          <div class="mb-1 grid grid-cols-2 gap-1.5">
            <select v-model="connectForm.direction" class="rounded bg-slate-800 px-2 py-1">
              <option value="FORWARD">FORWARD</option>
              <option value="REVERSE">REVERSE</option>
              <option value="BIDIRECTIONAL">BIDIRECTIONAL</option>
            </select>
            <select v-model="connectForm.status" class="rounded bg-slate-800 px-2 py-1">
              <option value="normal">normal</option>
              <option value="stopped">stopped</option>
              <option value="error">error</option>
            </select>
          </div>
          <button type="button" class="w-full rounded bg-blue-600 px-2 py-1 font-semibold" @click="upsertConnection">연결 반영</button>

          <div v-if="selectedLineId" class="mt-2 rounded border border-rose-400/40 bg-rose-900/20 p-2">
            <p class="mb-1 text-[11px] text-slate-200">선 선택됨: {{ selectedLineId }}</p>
            <button type="button" class="w-full rounded bg-rose-700 px-2 py-1 font-semibold" @click="removeSelectedLine">선 삭제</button>
          </div>
        </div>

        <div class="mt-2 rounded border border-white/10 p-2">
          <p class="mb-1 text-slate-300">상태창 표시</p>
          <div class="grid grid-cols-2 gap-1 text-[11px]">
            <label class="flex items-center gap-1"><input v-model="visibleMetrics.voltage" type="checkbox" />전압</label>
            <label class="flex items-center gap-1"><input v-model="visibleMetrics.current" type="checkbox" />전류</label>
            <label class="flex items-center gap-1"><input v-model="visibleMetrics.soc" type="checkbox" />SOC</label>
            <label class="flex items-center gap-1"><input v-model="visibleMetrics.frequency" type="checkbox" />주파수</label>
            <label class="flex items-center gap-1"><input v-model="visibleMetrics.pf" type="checkbox" />역률</label>
            <label class="flex items-center gap-1"><input v-model="visibleMetrics.mode" type="checkbox" />모드</label>
          </div>
        </div>
      </div>
    </div>

    <Map3DViewer
      :equipment-data="equipmentData"
      :connections="connections"
      :is-edit-mode="isEditMode"
      :is-add-armed="isAddArmed"
      :selected-equipment-id="selectedEquipmentId"
      :selected-line-id="selectedLineId"
      @update-positions="(value) => (uiPositions = value)"
      @zoom-change="handleZoomChange"
      @map-click="handleMapClick"
      @equip-click="handleEquipClick"
      @line-click="handleLineClick"
    />

    <MapStatusOverlay
      v-show="isUiVisible"
      :equipment-data="equipmentData"
      :ui-positions="uiPositions"
      :map-zoom="mapZoom"
      :visible-metrics="visibleMetrics"
      :is-edit-mode="isEditMode"
      @edit-equip="openEditModal"
    />

    <div class="absolute bottom-3 left-3 z-30">
      <slot name="overlay" />
    </div>

    <EquipFormModal
      v-if="modalConfig.show"
      :mode="modalConfig.mode"
      :initial-data="modalConfig.formData"
      @close="modalConfig.show = false"
      @save="handleSave"
      @delete="handleDelete"
    />

    <div class="absolute right-3 top-3 z-30 rounded-lg border border-slate-700 bg-slate-900/80 px-2 py-1.5 text-[11px] text-slate-100 backdrop-blur">
      <p>site: {{ props.topology?.site_id ?? 'n/a' }}</p>
      <p>topology nodes/lines: {{ props.topology?.nodes.length ?? 0 }} / {{ props.topology?.lines.length ?? 0 }}</p>
      <p>resources: {{ props.resources?.length ?? 0 }}</p>
      <p>rendered equipments/lines: {{ equipmentData.length }} / {{ connections.length }}</p>
    </div>

    <div
      v-if="equipmentData.length === 0"
      class="absolute inset-x-0 bottom-16 z-20 mx-auto w-fit rounded border border-amber-300/30 bg-amber-900/20 px-3 py-2 text-xs text-amber-100"
    >
      표시 가능한 장비 데이터가 없습니다. site_id와 API 응답을 확인하세요.
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import Map3DViewer from '@/features/map-dashboard/components/Map3DViewer.vue'
import MapStatusOverlay from '@/features/map-dashboard/components/MapStatusOverlay.vue'
import EquipFormModal from '@/features/map-dashboard/components/EquipFormModal.vue'
import type { ResourceInfo, TopologyData } from '@/types/common'
import type { ConnectionDirection, EquipmentFormData, MapConnection, MapEquipment } from '@/features/map-dashboard/types'
import { useControlStore } from '@/stores/control/control.store'

const props = defineProps<{
  topology: TopologyData | null
  resources?: ResourceInfo[]
  resourcesLastFetchedAt?: number | null
  topologyLastFetchedAt?: number | null
  resourcesFetchFailStreak?: number
  topologyFetchFailStreak?: number
}>()

const emit = defineEmits<{
  (e: 'select-node', nodeId: string): void
  (e: 'select-line', lineId: string): void
}>()

const controlStore = useControlStore()
const { pendingCommands, commandHistory } = storeToRefs(controlStore)

const commandStatusPriority: Record<string, number> = {
  CREATED: 1,
  ACCEPTED: 2,
  IN_PROGRESS: 3,
  RUNNING: 4,
  COMPLETED: 5,
  REJECTED: 6,
  FAILED: 7,
  TIMED_OUT: 8,
  BLOCKED: 9,
  EXPIRED: 10,
  IGNORED: 11
}

const sortedControlSignals = computed(() => {
  const all = [...pendingCommands.value, ...commandHistory.value]
  return all.sort((a, b) => {
    const ts = (Date.parse(b.created_at ?? '') || 0) - (Date.parse(a.created_at ?? '') || 0)
    if (ts !== 0) return ts
    return (commandStatusPriority[b.status] ?? 0) - (commandStatusPriority[a.status] ?? 0)
  })
})

const CONTROL_SIGNAL_TTL_MS = 30_000

const isSignalFresh = (createdAt?: string): boolean => {
  const ts = Date.parse(createdAt ?? '')
  if (!Number.isFinite(ts)) return false
  return Date.now() - ts <= CONTROL_SIGNAL_TTL_MS
}

const latestSignalByResource = computed(() => {
  const byResource = new Map<string, (typeof sortedControlSignals.value)[number]>()
  for (const command of sortedControlSignals.value) {
    if (!isSignalFresh(command.created_at)) continue
    const key = (command.target_resource_id ?? '').toLowerCase()
    if (!key || byResource.has(key)) continue
    byResource.set(key, command)
  }
  return byResource
})

const COMM_FAILURE_THRESHOLD = 3
const COMM_STALE_TTL_MS = 8_000
const nowTs = ref(Date.now())
const nowTicker = setInterval(() => {
  nowTs.value = Date.now()
}, 1_000)
onUnmounted(() => {
  clearInterval(nowTicker)
})

const hasUnintendedCommDisconnect = computed(() => {
  const resourcesFail = props.resourcesFetchFailStreak ?? 0
  const topologyFail = props.topologyFetchFailStreak ?? 0
  if (resourcesFail >= COMM_FAILURE_THRESHOLD || topologyFail >= COMM_FAILURE_THRESHOLD) return true

  const latestFetchedAt = Math.max(props.resourcesLastFetchedAt ?? 0, props.topologyLastFetchedAt ?? 0)
  if (latestFetchedAt <= 0) return false
  return nowTs.value - latestFetchedAt > COMM_STALE_TTL_MS
})

const isEditMode = ref(false)
const isControlCollapsed = ref(true)
const defaultAddType = ref<MapEquipment['type']>('LOAD')
const isAddArmed = ref(false)
const selectedEquipmentId = ref<string | null>(null)
const selectedLineId = ref<string | null>(null)
const isUiVisible = ref(true)
const mapZoom = ref(16)
const visibleMetrics = ref({
  voltage: true,
  current: true,
  soc: true,
  frequency: false,
  pf: false,
  mode: false
})
const uiPositions = ref<Record<string, { x: number; y: number }>>({})

const equipmentData = ref<MapEquipment[]>([])

const connections = ref<MapConnection[]>([])

const isCustomEquipment = (id: string) => id.startsWith('custom-') || id.startsWith('reserve-')
const isCustomLine = (id: string) => id.startsWith('custom-') || id.startsWith('custom-line-')

const connectForm = ref({
  fromEquipmentId: '',
  toEquipmentId: '',
  direction: 'FORWARD' as ConnectionDirection,
  status: 'normal' as MapConnection['status']
})

const modalConfig = ref<{ show: boolean; mode: 'add' | 'edit'; formData: EquipmentFormData }>({
  show: false,
  mode: 'add',
  formData: { name: '', type: 'LOAD', status: 'normal', power: '100 kW', lngLat: [129.0755, 35.1785] }
})

const nodeToStatus = (status: string): MapEquipment['status'] => {
  if (status === 'EMERGENCY') return 'error'
  if (status === 'WARNING' || status === 'UNKNOWN') return 'stopped'
  return 'normal'
}

const lineToStatus = (status: string): MapConnection['status'] => {
  if (status === 'FAULT') return 'error'
  if (status === 'OPEN' || status === 'BLOCKED' || status === 'UNKNOWN') return 'stopped'
  return 'normal'
}

const nodeTypeToEquipmentType = (nodeType: string): MapEquipment['type'] | null => {
  if (nodeType === 'STORAGE') return 'ESS'
  if (nodeType === 'LOAD') return 'LOAD'
  if (nodeType === 'GENERATION') return 'GENERATOR'
  return null
}

const resourceTypeToEquipmentType = (resourceType?: string): MapEquipment['type'] | null => {
  if (!resourceType) return null
  const upper = resourceType.toUpperCase()
  if (upper === 'ESS') return 'ESS'
  if (upper === 'LOAD') return 'LOAD'
  if (upper === 'SOLAR' || upper === 'DIESEL_GENERATOR' || upper === 'DIESEL') return 'GENERATOR'
  return null
}

const resourceStatusToEquipmentStatus = (status?: string): MapEquipment['status'] => {
  const upper = (status ?? '').toUpperCase()
  if (upper.includes('EMERGENCY') || upper.includes('FAULT') || upper.includes('ERROR') || upper.includes('OFFLINE')) return 'error'
  if (upper.includes('WARNING') || upper.includes('OPEN') || upper.includes('BLOCKED')) return 'stopped'
  return 'normal'
}

const applyUnintendedDisconnectStatus = <T extends MapEquipment['status'] | MapConnection['status']>(status: T): T => {
  if (!hasUnintendedCommDisconnect.value) return status
  return 'error' as T
}

const applyCommandToEquipmentStatus = (resourceId: string, baseStatus: MapEquipment['status']): MapEquipment['status'] => {
  const signal = latestSignalByResource.value.get(resourceId.toLowerCase())
  if (!signal) return applyUnintendedDisconnectStatus(baseStatus)

  if (signal.status === 'FAILED' || signal.status === 'TIMED_OUT' || signal.status === 'BLOCKED' || signal.status === 'REJECTED') {
    return applyUnintendedDisconnectStatus('error')
  }

  if (signal.status !== 'COMPLETED' && signal.status !== 'RUNNING' && signal.status !== 'IN_PROGRESS' && signal.status !== 'ACCEPTED') {
    return applyUnintendedDisconnectStatus(baseStatus)
  }

  if (
    signal.action === 'STOP_CHARGE' ||
    signal.action === 'STOP_DISCHARGE' ||
    signal.action === 'STOP_GENERATOR' ||
    signal.action === 'SHED_LOAD' ||
    signal.action === 'OPEN_SWITCH' ||
    signal.action === 'STANDBY'
  ) {
    return hasUnintendedCommDisconnect.value ? 'error' : 'stopped'
  }

  if (
    signal.action === 'START_CHARGE' ||
    signal.action === 'START_DISCHARGE' ||
    signal.action === 'START_GENERATOR' ||
    signal.action === 'RESTORE_LOAD' ||
    signal.action === 'CLOSE_SWITCH'
  ) {
    return applyUnintendedDisconnectStatus(baseStatus === 'error' ? 'error' : 'normal')
  }

  return applyUnintendedDisconnectStatus(baseStatus)
}

const applyCommandToLineStatus = (lineId: string, fromResourceId: string, toResourceId: string, baseStatus: MapConnection['status']): MapConnection['status'] => {
  const fromSignal = latestSignalByResource.value.get(fromResourceId.toLowerCase())
  const toSignal = latestSignalByResource.value.get(toResourceId.toLowerCase())
  const lineSignal = latestSignalByResource.value.get(lineId.toLowerCase())
  const signal = lineSignal ?? fromSignal ?? toSignal
  if (!signal) return applyUnintendedDisconnectStatus(baseStatus)

  if (signal.status === 'FAILED' || signal.status === 'TIMED_OUT' || signal.status === 'BLOCKED' || signal.status === 'REJECTED') {
    return applyUnintendedDisconnectStatus('error')
  }
  if (signal.status !== 'COMPLETED' && signal.status !== 'RUNNING' && signal.status !== 'IN_PROGRESS' && signal.status !== 'ACCEPTED') {
    return applyUnintendedDisconnectStatus(baseStatus)
  }
  if (signal.action === 'OPEN_SWITCH' || signal.action === 'SHED_LOAD' || signal.action === 'STOP_GENERATOR' || signal.action === 'STANDBY') {
    return hasUnintendedCommDisconnect.value ? 'error' : 'stopped'
  }
  if (signal.action === 'CLOSE_SWITCH' || signal.action === 'RESTORE_LOAD' || signal.action === 'START_GENERATOR') {
    return applyUnintendedDisconnectStatus(baseStatus === 'error' ? 'error' : 'normal')
  }
  return applyUnintendedDisconnectStatus(baseStatus)
}

const DEFAULT_BASE_LNG = 129.0755
const DEFAULT_BASE_LAT = 35.1785

const hasValidLngLat = (lng: number, lat: number) => {
  if (!Number.isFinite(lng) || !Number.isFinite(lat)) return false
  if (Math.abs(lng) <= 0.001 && Math.abs(lat) <= 0.001) return false
  return lng >= -180 && lng <= 180 && lat >= -85 && lat <= 85
}

const resolveAnchorLngLat = (
  resources: ResourceInfo[],
  nodes: TopologyData['nodes']
): [number, number] => {
  const resourceCoords = resources
    .map((resource) => resolveResourceLngLat(resource))
    .filter((value): value is [number, number] => value !== null)

  if (resourceCoords.length > 0) {
    const sum = resourceCoords.reduce(
      (acc, [lng, lat]) => {
        acc.lng += lng
        acc.lat += lat
        return acc
      },
      { lng: 0, lat: 0 }
    )
    return [sum.lng / resourceCoords.length, sum.lat / resourceCoords.length]
  }

  const nodeLngLat = nodes
    .map((node) => [toNumber(node.position?.x), toNumber(node.position?.y)] as const)
    .filter((coords): coords is [number, number] => {
      const [lng, lat] = coords
      return lng !== undefined && lat !== undefined && hasValidLngLat(lng, lat)
    })

  if (nodeLngLat.length > 0) {
    const sum = nodeLngLat.reduce(
      (acc, [lng, lat]) => {
        acc.lng += lng
        acc.lat += lat
        return acc
      },
      { lng: 0, lat: 0 }
    )
    return [sum.lng / nodeLngLat.length, sum.lat / nodeLngLat.length]
  }

  return [DEFAULT_BASE_LNG, DEFAULT_BASE_LAT]
}

const buildTopologyCoordinateMapper = (nodes: TopologyData['nodes'], anchor: [number, number]) => {
  const rawPositions = nodes
    .map((node) => ({ x: node.position?.x, y: node.position?.y }))
    .filter((position): position is { x: number; y: number } => Number.isFinite(position.x) && Number.isFinite(position.y))

  if (rawPositions.length === 0) {
    return (_x?: number, _y?: number): [number, number] | null => null
  }

  const allAreLngLat = rawPositions.every((position) => hasValidLngLat(position.x, position.y))
  if (allAreLngLat) {
    return (x?: number, y?: number): [number, number] | null => {
      const lng = toNumber(x)
      const lat = toNumber(y)
      if (lng === undefined || lat === undefined) return null
      return hasValidLngLat(lng, lat) ? [lng, lat] : null
    }
  }

  const xs = rawPositions.map((position) => position.x)
  const ys = rawPositions.map((position) => position.y)
  const minX = Math.min(...xs)
  const maxX = Math.max(...xs)
  const minY = Math.min(...ys)
  const maxY = Math.max(...ys)
  const spanX = Math.max(1, maxX - minX)
  const spanY = Math.max(1, maxY - minY)

  const targetWidth = 0.0032
  const targetHeight = 0.0024

  return (x?: number, y?: number): [number, number] | null => {
    const sourceX = toNumber(x)
    const sourceY = toNumber(y)
    if (sourceX === undefined || sourceY === undefined) return null
    const normalizedX = (sourceX - minX) / spanX
    const normalizedY = (sourceY - minY) / spanY

    const lng = anchor[0] + (normalizedX - 0.5) * targetWidth
    const lat = anchor[1] + (0.5 - normalizedY) * targetHeight
    return [lng, lat]
  }
}

const fallbackPositionByType = (type: MapEquipment['type'], index: number, anchor: [number, number]): [number, number] => {
  const baseLng = anchor[0]
  const baseLat = anchor[1]

  if (type === 'GENERATOR') {
    return [baseLng - 0.0016, baseLat + 0.0007 - index * 0.0008]
  }
  if (type === 'ESS') {
    return [baseLng, baseLat]
  }
  return [baseLng + 0.0016, baseLat + 0.0009 - index * 0.0008]
}

const toNumber = (value: unknown): number | undefined => {
  if (typeof value === 'number' && Number.isFinite(value)) return value
  if (typeof value === 'string' && value.trim() !== '') {
    const parsed = Number(value)
    if (Number.isFinite(parsed)) return parsed
  }
  return undefined
}

const resolveResourceLngLat = (resource?: ResourceInfo): [number, number] | null => {
  if (!resource) return null
  const lng = toNumber(resource.longitude)
  const lat = toNumber(resource.latitude)
  if (lng !== undefined && lat !== undefined && hasValidLngLat(lng, lat)) return [lng, lat]

  const location = resource.location ?? undefined
  if (!location || typeof location !== 'object') return null

  const locationRecord = location as Record<string, unknown>
  const locationLng = toNumber(locationRecord.longitude) ?? toNumber(locationRecord.lng) ?? toNumber(locationRecord.x)
  const locationLat = toNumber(locationRecord.latitude) ?? toNumber(locationRecord.lat) ?? toNumber(locationRecord.y)
  if (locationLng !== undefined && locationLat !== undefined && hasValidLngLat(locationLng, locationLat)) {
    return [locationLng, locationLat]
  }

  return null
}

const switchPositionToLineStatus = (position?: string): MapConnection['status'] | null => {
  const upper = (position ?? '').toUpperCase()
  if (upper === 'OPEN') return 'stopped'
  if (upper === 'CLOSED') return 'normal'
  return null
}

const applyTopologyData = () => {
  const customEquipments = equipmentData.value.filter((item) => isCustomEquipment(item.id))
  const customLines = connections.value.filter((line) => isCustomLine(line.id))

  const resources = props.resources ?? []
  const resourceById = new Map(resources.map((resource) => [resource.resource_id.toLowerCase(), resource]))
  const hasTopologyNodes = Boolean(props.topology && props.topology.nodes.length > 0)
  const anchor = resolveAnchorLngLat(resources, props.topology?.nodes ?? [])

  if (hasTopologyNodes && props.topology) {
    const mapTopologyPosition = buildTopologyCoordinateMapper(props.topology.nodes, anchor)
    const flowByNodeId = new Map<string, number>()
    props.topology.lines.forEach((line) => {
      const value = Math.abs(line.flow_kw ?? 0)
      flowByNodeId.set(line.from_node_id, (flowByNodeId.get(line.from_node_id) ?? 0) + value)
      flowByNodeId.set(line.to_node_id, (flowByNodeId.get(line.to_node_id) ?? 0) + value)
    })

    const topologyEquipments: MapEquipment[] = []
    const typeCounts: Record<MapEquipment['type'], number> = {
      GENERATOR: 0,
      ESS: 0,
      LOAD: 0
    }

    props.topology.nodes.forEach((node) => {
      const type = nodeTypeToEquipmentType(node.node_type)
      if (!type) return
      const linkedResource = resourceById.get(node.resource_id.toLowerCase())
      const powerKw = toNumber(linkedResource?.telemetry?.p_kw) ?? flowByNodeId.get(node.node_id) ?? 0
      const fallbackIndex = typeCounts[type]
      typeCounts[type] += 1
      const fallback = fallbackPositionByType(type, fallbackIndex, anchor)
      const mappedPosition = mapTopologyPosition(node.position?.x, node.position?.y)
      const resourcePosition = resolveResourceLngLat(linkedResource)
      const lng = resourcePosition?.[0] ?? mappedPosition?.[0] ?? fallback[0]
      const lat = resourcePosition?.[1] ?? mappedPosition?.[1] ?? fallback[1]

      const equipmentStatus = applyCommandToEquipmentStatus(
        node.resource_id,
        linkedResource ? resourceStatusToEquipmentStatus(linkedResource.status) : nodeToStatus(node.status)
      )

      topologyEquipments.push({
        id: node.node_id,
        name: linkedResource?.name ?? node.resource_id,
        type,
        status: equipmentStatus,
        power: `${Math.round(Math.abs(powerKw))} kW`,
        lngLat: [lng, lat],
        metrics: {
          voltage: toNumber(linkedResource?.telemetry?.v_volt),
          current: toNumber(linkedResource?.telemetry?.i_amp),
          soc: toNumber(linkedResource?.telemetry?.soc),
          frequency: toNumber(linkedResource?.telemetry?.f_hz),
          pf: toNumber(linkedResource?.telemetry?.pf),
          mode: linkedResource?.telemetry?.operating_mode
        }
      })
    })

    const nodeToResourceId = new Map(props.topology.nodes.map((node) => [node.node_id, node.resource_id]))
    const switchByLineId = new Map((props.topology.switches ?? []).map((item) => [item.line_id, item]))
    const topologyLines: MapConnection[] = props.topology.lines.map((line) => {
      const fromResourceId = nodeToResourceId.get(line.from_node_id) ?? line.from_node_id
      const toResourceId = nodeToResourceId.get(line.to_node_id) ?? line.to_node_id
      const switchInfo = switchByLineId.get(line.line_id)
      const switchResource = switchInfo
        ? resourceById.get(switchInfo.switch_id.toLowerCase()) ?? resourceById.get(switchInfo.line_id.toLowerCase())
        : undefined
      const switchDrivenStatus = switchPositionToLineStatus(switchResource?.position)
      return {
        id: line.line_id,
        fromEquipmentId: line.from_node_id,
        toEquipmentId: line.to_node_id,
        direction: line.direction,
        status: applyCommandToLineStatus(
          line.line_id,
          fromResourceId,
          toResourceId,
          switchDrivenStatus ?? lineToStatus(line.status)
        )
      }
    })

    equipmentData.value = [...topologyEquipments, ...customEquipments]
    connections.value = [...topologyLines, ...customLines]
    return
  }

  const filteredResources = resources.filter((resource) => resourceTypeToEquipmentType(resource.resource_type) !== null)
  if (filteredResources.length === 0) {
    equipmentData.value = customEquipments
    connections.value = customLines
    return
  }

  const typeCounts: Record<MapEquipment['type'], number> = {
    GENERATOR: 0,
    ESS: 0,
    LOAD: 0
  }

  const fallbackEquipments: MapEquipment[] = filteredResources.map((resource) => {
    const type = resourceTypeToEquipmentType(resource.resource_type) as MapEquipment['type']
    const fallback = fallbackPositionByType(type, typeCounts[type], anchor)
    typeCounts[type] += 1
    const powerKw = Math.abs(toNumber(resource.telemetry?.p_kw) ?? 0)
    return {
      id: resource.resource_id,
      name: resource.name ?? resource.resource_id,
      type,
      status: applyCommandToEquipmentStatus(resource.resource_id, resourceStatusToEquipmentStatus(resource.status)),
      power: `${Math.round(powerKw)} kW`,
      lngLat: fallback,
      metrics: {
        voltage: toNumber(resource.telemetry?.v_volt),
        current: toNumber(resource.telemetry?.i_amp),
        soc: toNumber(resource.telemetry?.soc),
        frequency: toNumber(resource.telemetry?.f_hz),
        pf: toNumber(resource.telemetry?.pf),
        mode: resource.telemetry?.operating_mode
      }
    }
  })

  const ess = fallbackEquipments.find((item) => item.type === 'ESS')
  const generators = fallbackEquipments.filter((item) => item.type === 'GENERATOR')
  const loads = fallbackEquipments.filter((item) => item.type === 'LOAD')

  const fallbackLines: MapConnection[] = []
  if (ess) {
    generators.forEach((generator) => {
      fallbackLines.push({
        id: `line-${generator.id}-${ess.id}`,
        fromEquipmentId: generator.id,
        toEquipmentId: ess.id,
        direction: 'FORWARD',
        status: generator.status === 'error' || ess.status === 'error' ? 'error' : generator.status === 'stopped' || ess.status === 'stopped' ? 'stopped' : 'normal'
      })
    })
    loads.forEach((load) => {
      fallbackLines.push({
        id: `line-${ess.id}-${load.id}`,
        fromEquipmentId: ess.id,
        toEquipmentId: load.id,
        direction: 'FORWARD',
        status: load.status === 'error' || ess.status === 'error' ? 'error' : load.status === 'stopped' || ess.status === 'stopped' ? 'stopped' : 'normal'
      })
    })
  }

  equipmentData.value = [...fallbackEquipments, ...customEquipments]
  connections.value = [...fallbackLines, ...customLines]
}

const typePrefix: Record<MapEquipment['type'], string> = {
  GENERATOR: 'GENERATOR',
  ESS: 'ESS',
  LOAD: 'LOAD'
}

const getNextEquipmentName = (type: MapEquipment['type']) => {
  const prefix = typePrefix[type]
  const maxNumber = equipmentData.value
    .filter((item) => item.type === type)
    .map((item) => {
      const matched = item.name.match(/#(\d+)$/)
      return matched ? Number(matched[1]) : 0
    })
    .reduce((acc, value) => Math.max(acc, value), 0)
  return `${prefix} #${maxNumber + 1}`
}

const upsertConnection = () => {
  const { fromEquipmentId, toEquipmentId, direction, status } = connectForm.value
  if (!fromEquipmentId || !toEquipmentId || fromEquipmentId === toEquipmentId) return
  const id = `custom-line-${fromEquipmentId}-${toEquipmentId}`
  const index = connections.value.findIndex((item) => item.id === id)
  if (index === -1) {
    connections.value.push({ id, fromEquipmentId, toEquipmentId, direction, status })
  } else {
    connections.value[index] = { ...connections.value[index], direction, status }
  }
}

const removeSelectedLine = () => {
  if (!selectedLineId.value) return
  connections.value = connections.value.filter((line) => line.id !== selectedLineId.value)
  selectedLineId.value = null
}

const openAddModal = (lngLat: [number, number]) => {
  modalConfig.value = {
    show: true,
    mode: 'add',
    formData: { name: '', type: defaultAddType.value, status: 'normal', power: '100 kW', lngLat }
  }
}

const toggleAddArmed = () => {
  if (!isEditMode.value) return
  isAddArmed.value = !isAddArmed.value
}

const handleExpand = () => {
  isControlCollapsed.value = false
  isEditMode.value = true
}

const handleComplete = () => {
  isAddArmed.value = false
  isEditMode.value = false
  isControlCollapsed.value = true
}

const handleMapClick = (lngLat: [number, number]) => {
  if (!isEditMode.value || !isAddArmed.value) return
  openAddModal(lngLat)
  isAddArmed.value = false
}

const openEditModal = (id: string) => {
  const target = equipmentData.value.find((item) => item.id === id)
  if (!target) return
  modalConfig.value = { show: true, mode: 'edit', formData: { ...target } }
}

const handleSave = (formData: EquipmentFormData) => {
  if (modalConfig.value.mode === 'add') {
    equipmentData.value.push({ ...formData, id: `custom-${Date.now()}` })
  } else {
    const index = equipmentData.value.findIndex((item) => item.id === formData.id)
    if (index !== -1) equipmentData.value[index] = { ...equipmentData.value[index], ...formData } as MapEquipment
  }
  modalConfig.value.show = false
}

const handleDelete = () => {
  const id = modalConfig.value.formData.id
  if (!id) return
  equipmentData.value = equipmentData.value.filter((item) => item.id !== id)
  connections.value = connections.value.filter((line) => line.fromEquipmentId !== id && line.toEquipmentId !== id)
  modalConfig.value.show = false
}

const resolveResourceIdFromMapEquipment = (id: string): string => {
  const directMatch = props.topology?.nodes.find((node) => node.node_id === id || node.resource_id === id)
  if (directMatch) return directMatch.resource_id

  if (!props.topology) return id

  const mapEquipment = equipmentData.value.find((item) => item.id === id)
  if (!mapEquipment) return id

  const typeFilteredNodes = props.topology.nodes.filter((node) => {
    if (mapEquipment.type === 'ESS') return node.node_type === 'STORAGE'
    if (mapEquipment.type === 'LOAD') return node.node_type === 'LOAD'
    return node.node_type === 'GENERATION' || node.node_type === 'GRID'
  })

  const seqMatch = id.match(/-(\d+)$/)
  const index = seqMatch ? Number(seqMatch[1]) - 1 : 0
  return typeFilteredNodes[index]?.resource_id ?? typeFilteredNodes[0]?.resource_id ?? id
}

const handleEquipClick = (id: string) => {
  if (isEditMode.value) {
    openEditModal(id)
    return
  }
  if (selectedEquipmentId.value === id) {
    selectedEquipmentId.value = null
    selectedLineId.value = null
    emit('select-node', '')
    return
  }

  selectedEquipmentId.value = id
  selectedLineId.value = null
  emit('select-node', resolveResourceIdFromMapEquipment(id))
}

const handleLineClick = (lineId: string) => {
  if (selectedLineId.value === lineId) {
    selectedLineId.value = null
    selectedEquipmentId.value = null
    emit('select-line', '')
    return
  }

  selectedLineId.value = lineId
  selectedEquipmentId.value = null
  emit('select-line', lineId)
}

const handleZoomChange = (value: number) => {
  mapZoom.value = value
  isUiVisible.value = value > 14.0
}

watch(
  () => props.topology,
  () => applyTopologyData(),
  { deep: true, immediate: true }
)

watch(
  () => props.resources,
  () => applyTopologyData(),
  { deep: true }
)

watch(
  () => sortedControlSignals.value,
  () => applyTopologyData(),
  { deep: true }
)

watch(isEditMode, (next) => {
  if (!next) isAddArmed.value = false
})
</script>
