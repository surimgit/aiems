<template>
  <div class="relative h-full w-full overflow-hidden rounded-xl border border-white/10 bg-slate-950">
    <div class="absolute left-3 top-3 z-30 w-[320px] rounded-lg border border-white/10 bg-slate-950/85 p-2 text-xs text-white backdrop-blur">
      <div class="mb-2 flex items-center justify-between">
        <strong>Map Control</strong>
        <div class="flex items-center gap-1.5">
          <button
            type="button"
            class="rounded bg-slate-700 px-2 py-1 font-semibold"
            @click="isControlCollapsed = !isControlCollapsed"
          >
            {{ isControlCollapsed ? '펼치기' : '접기' }}
          </button>
          <button
            type="button"
            class="rounded px-2 py-1 font-semibold"
            :class="isEditMode ? 'bg-rose-600' : 'bg-blue-600'"
            @click="isEditMode = !isEditMode"
          >
            {{ isEditMode ? '편집 종료' : '편집 시작' }}
          </button>
        </div>
      </div>

      <div v-if="!isControlCollapsed">
        <div class="mb-2 rounded border border-white/10 p-2">
          <p class="mb-1 text-slate-300">장비 추가 기본 타입</p>
          <div class="mb-1 grid grid-cols-2 gap-1.5">
            <button
              type="button"
              class="rounded px-2 py-1 font-semibold"
              :class="isAddArmed ? 'bg-emerald-600' : 'bg-slate-700'"
              :disabled="!isEditMode"
              @click="toggleAddArmed"
            >
              {{ isAddArmed ? '장비 추가 대기중' : '장비 추가' }}
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
          <select v-model="defaultAddType" class="w-full rounded bg-slate-800 px-2 py-1">
            <option value="GENERATOR">GENERATOR</option>
            <option value="ESS">ESS</option>
            <option value="LOAD">LOAD</option>
          </select>
          <p class="mt-1 text-[11px] text-slate-400">편집 시작 후 지도 빈 공간 클릭 시 추가 모달이 열립니다.</p>
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
        </div>
      </div>
    </div>

    <Map3DViewer
      :equipment-data="equipmentData"
      :connections="connections"
      :is-edit-mode="isEditMode"
      :is-add-armed="isAddArmed"
      @update-positions="(value) => (uiPositions = value)"
      @zoom-change="(value) => (isUiVisible = value > 16.0)"
      @map-click="handleMapClick"
      @equip-click="handleEquipClick"
    />

    <MapStatusOverlay
      v-show="isUiVisible"
      :equipment-data="equipmentData"
      :ui-positions="uiPositions"
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
const isUiVisible = ref(true)
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

const addEquipment = (type: MapEquipment['type'], lngLat: [number, number], status: MapEquipment['status'] = 'normal') => {
  equipmentData.value.push({
    id: `custom-${Date.now()}`,
    name: getNextEquipmentName(type),
    type,
    status,
    power: status === 'stopped' ? '0 kW' : '100 kW',
    lngLat
  })
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

const handleEquipClick = (id: string) => {
  if (isEditMode.value) {
    openEditModal(id)
    return
  }
  emit('select-node', id)
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
