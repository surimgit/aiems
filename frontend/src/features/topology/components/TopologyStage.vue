<template>
  <div class="relative h-full w-full overflow-hidden rounded-xl border border-white/10 bg-slate-950">
    <div
      class="absolute left-3 top-3 z-30 rounded-lg border border-white/10 bg-slate-950/85 p-2 text-xs text-white backdrop-blur"
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
      </div>
    </div>

    <Map3DViewer
      :equipment-data="equipmentData"
      :connections="connections"
      :is-edit-mode="isEditMode"
      :is-add-armed="isAddArmed"
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
      :is-edit-mode="isEditMode"
      @edit-equip="openEditModal"
    />

    <EquipFormModal
      v-if="modalConfig.show"
      :mode="modalConfig.mode"
      :initial-data="modalConfig.formData"
      @close="modalConfig.show = false"
      @save="handleSave"
      @delete="handleDelete"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import Map3DViewer from '@/features/map-dashboard/components/Map3DViewer.vue'
import MapStatusOverlay from '@/features/map-dashboard/components/MapStatusOverlay.vue'
import EquipFormModal from '@/features/map-dashboard/components/EquipFormModal.vue'
import type { TopologyData } from '@/types/common'
import type { ConnectionDirection, EquipmentFormData, MapConnection, MapEquipment } from '@/features/map-dashboard/types'

const props = defineProps<{
  topology: TopologyData | null
}>()

const emit = defineEmits<{
  (e: 'select-node', nodeId: string): void
  (e: 'select-line', lineId: string): void
}>()

const isEditMode = ref(false)
const isControlCollapsed = ref(false)
const defaultAddType = ref<MapEquipment['type']>('LOAD')
const isAddArmed = ref(false)
const selectedLineId = ref<string | null>(null)
const isUiVisible = ref(true)
const mapZoom = ref(16)
const uiPositions = ref<Record<string, { x: number; y: number }>>({})

const equipmentData = ref<MapEquipment[]>([
  { id: 'solar-1', name: 'SOLAR #1', type: 'GENERATOR', status: 'normal', power: '640 kW', lngLat: [129.074, 35.1795] },
  { id: 'solar-2', name: 'SOLAR #2', type: 'GENERATOR', status: 'stopped', power: '320 kW', lngLat: [129.074, 35.1785] },
  { id: 'ess-1', name: 'ESS', type: 'ESS', status: 'normal', power: '-120 kW', lngLat: [129.076, 35.178] },
  { id: 'load-1', name: 'LOAD #1', type: 'LOAD', status: 'normal', power: '420 kW', lngLat: [129.0775, 35.1795] },
  { id: 'load-2', name: 'LOAD #2', type: 'LOAD', status: 'normal', power: '350 kW', lngLat: [129.0775, 35.1785] },
  { id: 'load-3', name: 'LOAD #3', type: 'LOAD', status: 'error', power: '250 kW', lngLat: [129.0775, 35.1775] }
])

const connections = ref<MapConnection[]>([
  { id: 'line-solar1-ess', fromEquipmentId: 'solar-1', toEquipmentId: 'ess-1', direction: 'FORWARD', status: 'normal' },
  { id: 'line-solar2-ess', fromEquipmentId: 'solar-2', toEquipmentId: 'ess-1', direction: 'FORWARD', status: 'stopped' },
  { id: 'line-ess-load1', fromEquipmentId: 'ess-1', toEquipmentId: 'load-1', direction: 'FORWARD', status: 'normal' },
  { id: 'line-ess-load2', fromEquipmentId: 'ess-1', toEquipmentId: 'load-2', direction: 'FORWARD', status: 'normal' },
  { id: 'line-ess-load3', fromEquipmentId: 'ess-1', toEquipmentId: 'load-3', direction: 'FORWARD', status: 'error' }
])

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

const applyTopologyStatus = () => {
  if (!props.topology) return

  const nodeStatusByResource = new Map(props.topology.nodes.map((node) => [node.resource_id.toUpperCase(), nodeToStatus(node.status)]))
  equipmentData.value = equipmentData.value.map((item) => {
    const status = nodeStatusByResource.get(item.name.toUpperCase())
    return status ? { ...item, status } : item
  })

  const lineStatusList = props.topology.lines.map((line) => lineToStatus(line.status))
  connections.value = connections.value.map((line, idx) => ({
    ...line,
    status: lineStatusList[idx] ?? line.status
  }))
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

  emit('select-node', resolveResourceIdFromMapEquipment(id))
}

const handleLineClick = (lineId: string) => {
  selectedLineId.value = lineId
  emit('select-line', lineId)
}

const handleZoomChange = (value: number) => {
  mapZoom.value = value
  isUiVisible.value = value > 14.0
}

watch(
  () => props.topology,
  () => applyTopologyStatus(),
  { deep: true, immediate: true }
)

watch(isEditMode, (next) => {
  if (!next) isAddArmed.value = false
})
</script>
