<template>
  <div class="relative h-screen w-full overflow-hidden bg-black">
    <div class="absolute left-4 top-4 z-30 w-[360px] rounded-xl border border-white/10 bg-slate-950/88 p-3 text-white backdrop-blur">
      <div class="mb-2 flex items-center justify-between">
        <h2 class="text-sm font-bold">관제 맵 빌더</h2>
        <button
          type="button"
          class="rounded px-2 py-1 text-xs font-semibold"
          :class="isEditMode ? 'bg-rose-600' : 'bg-blue-600'"
          @click="isEditMode = !isEditMode"
        >
          {{ isEditMode ? '편집 종료' : '편집 시작' }}
        </button>
      </div>

      <div class="mb-3 grid grid-cols-4 gap-2">
        <button type="button" class="rounded bg-slate-700 px-2 py-1 text-xs" @click="spawnTemplate('SOLAR')">예비 태양광</button>
        <button type="button" class="rounded bg-slate-700 px-2 py-1 text-xs" @click="spawnTemplate('DIESEL')">예비 디젤</button>
        <button type="button" class="rounded bg-slate-700 px-2 py-1 text-xs" @click="spawnTemplate('ESS')">예비 ESS</button>
        <button type="button" class="rounded bg-slate-700 px-2 py-1 text-xs" @click="spawnTemplate('LOAD')">예비 LOAD</button>
      </div>

      <div class="mb-3 rounded border border-white/10 p-2">
        <p class="mb-2 text-xs text-slate-300">좌표 입력 추가</p>
        <div class="mb-2 grid grid-cols-2 gap-2">
          <input v-model.number="coordForm.lng" type="number" step="0.0001" class="rounded bg-slate-800 px-2 py-1 text-xs" placeholder="경도" />
          <input v-model.number="coordForm.lat" type="number" step="0.0001" class="rounded bg-slate-800 px-2 py-1 text-xs" placeholder="위도" />
        </div>
        <div class="mb-2 grid grid-cols-2 gap-2">
          <select v-model="coordForm.type" class="rounded bg-slate-800 px-2 py-1 text-xs">
            <option value="SOLAR">태양광</option>
            <option value="DIESEL">디젤 발전기</option>
            <option value="GENERATOR">발전기</option>
            <option value="ESS">ESS</option>
            <option value="LOAD">LOAD</option>
          </select>
          <button type="button" class="rounded bg-emerald-600 px-2 py-1 text-xs font-semibold" @click="addByCoordinate">좌표로 추가</button>
        </div>
      </div>

      <div class="rounded border border-white/10 p-2">
        <p class="mb-2 text-xs text-slate-300">선 연결/방향 설정</p>
        <div class="mb-2 grid grid-cols-2 gap-2">
          <select v-model="connectForm.fromEquipmentId" class="rounded bg-slate-800 px-2 py-1 text-xs">
            <option value="">출발 장비</option>
            <option v-for="eq in equipmentData" :key="`from-${eq.id}`" :value="eq.id">{{ eq.name }}</option>
          </select>
          <select v-model="connectForm.toEquipmentId" class="rounded bg-slate-800 px-2 py-1 text-xs">
            <option value="">도착 장비</option>
            <option v-for="eq in equipmentData" :key="`to-${eq.id}`" :value="eq.id">{{ eq.name }}</option>
          </select>
        </div>
        <div class="mb-2 grid grid-cols-2 gap-2">
          <select v-model="connectForm.direction" class="rounded bg-slate-800 px-2 py-1 text-xs">
            <option value="FORWARD">FORWARD</option>
            <option value="REVERSE">REVERSE</option>
            <option value="BIDIRECTIONAL">BIDIRECTIONAL</option>
          </select>
          <select v-model="connectForm.status" class="rounded bg-slate-800 px-2 py-1 text-xs">
            <option value="normal">정상</option>
            <option value="stopped">중지</option>
            <option value="error">이상</option>
          </select>
        </div>
        <button type="button" class="w-full rounded bg-blue-600 px-2 py-1 text-xs font-semibold" @click="upsertConnection">선 연결 반영</button>
      </div>
    </div>

    <Map3DViewer
      :equipment-data="equipmentData"
      :connections="connections"
      :is-edit-mode="isEditMode"
      :is-add-armed="isAddArmed"
      @update-positions="(value) => (uiPositions = value)"
      @zoom-change="handleZoomChange"
      @map-click="openAddModal"
      @equip-click="openEditModal"
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
import { onMounted, ref } from 'vue'
import { useTopologyFeature } from '@/features/topology'
import Map3DViewer from '../components/Map3DViewer.vue'
import MapStatusOverlay from '../components/MapStatusOverlay.vue'
import EquipFormModal from '../components/EquipFormModal.vue'
import type { ConnectionDirection, EquipmentFormData, MapConnection, MapEquipment } from '../types'

const topologyFeature = useTopologyFeature()
const isEditMode = ref(false)
const isAddArmed = ref(false)
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
const equipmentData = ref<MapEquipment[]>([
  { id: 'solar-1', name: 'SOLAR #1', type: 'SOLAR', status: 'normal', power: '640 kW', lngLat: [129.074, 35.1795] },
  { id: 'solar-2', name: 'SOLAR #2', type: 'SOLAR', status: 'stopped', power: '320 kW', lngLat: [129.074, 35.1785] },
  { id: 'ess-1', name: 'ESS', type: 'ESS', status: 'normal', power: '-120 kW', lngLat: [129.076, 35.178] },
  { id: 'diesel-1', name: 'DIESEL #1', type: 'DIESEL', status: 'normal', power: '180 kW', lngLat: [129.0752, 35.1774] },
  { id: 'load-1', name: 'LOAD #1', type: 'LOAD', status: 'normal', power: '420 kW', lngLat: [129.0775, 35.1795] },
  { id: 'load-2', name: 'LOAD #2', type: 'LOAD', status: 'normal', power: '350 kW', lngLat: [129.0775, 35.1785] },
  { id: 'load-3', name: 'LOAD #3', type: 'LOAD', status: 'error', power: '250 kW', lngLat: [129.0775, 35.1775] }
])
const connections = ref<MapConnection[]>([
  { id: 'line-solar1-ess', fromEquipmentId: 'solar-1', toEquipmentId: 'ess-1', direction: 'FORWARD', status: 'normal' },
  { id: 'line-solar2-ess', fromEquipmentId: 'solar-2', toEquipmentId: 'ess-1', direction: 'FORWARD', status: 'stopped' },
  { id: 'line-diesel-ess', fromEquipmentId: 'diesel-1', toEquipmentId: 'ess-1', direction: 'FORWARD', status: 'normal' },
  { id: 'line-ess-load1', fromEquipmentId: 'ess-1', toEquipmentId: 'load-1', direction: 'FORWARD', status: 'normal' },
  { id: 'line-ess-load2', fromEquipmentId: 'ess-1', toEquipmentId: 'load-2', direction: 'FORWARD', status: 'normal' },
  { id: 'line-ess-load3', fromEquipmentId: 'ess-1', toEquipmentId: 'load-3', direction: 'FORWARD', status: 'error' }
])

const coordForm = ref({ lng: 129.0755, lat: 35.1785, type: 'LOAD' as MapEquipment['type'] })
const connectForm = ref({
  fromEquipmentId: '',
  toEquipmentId: '',
  direction: 'FORWARD' as ConnectionDirection,
  status: 'normal' as MapConnection['status']
})

const modalConfig = ref<{
  show: boolean
  mode: 'add' | 'edit'
  formData: EquipmentFormData
}>({
  show: false,
  mode: 'add',
  formData: { name: '', type: 'LOAD', status: 'normal', power: '0 kW', lngLat: [129.0755, 35.1785] }
})

const nodeToType = (resourceId: string): MapEquipment['type'] => {
  const id = resourceId.toUpperCase()
  if (id.includes('ESS')) return 'ESS'
  if (id.includes('LOAD')) return 'LOAD'
  if (id.includes('SOLAR') || id.includes('PV')) return 'SOLAR'
  if (id.includes('DIESEL') || id.includes('GENERATOR')) return 'DIESEL'
  return 'GENERATOR'
}

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

const syncStatusFromTopology = () => {
  const topology = topologyFeature.topology.value
  if (!topology) return
  const nodeStatusByKey = new Map(topology.nodes.map((node) => [node.resource_id.toUpperCase(), nodeToStatus(node.status)]))
  equipmentData.value = equipmentData.value.map((item) => {
    const status = nodeStatusByKey.get(item.name.toUpperCase())
    return status ? { ...item, status } : item
  })
}

const spawnTemplate = (type: MapEquipment['type']) => {
  const seed = Date.now()
  const offset = (equipmentData.value.filter((item) => item.type === type).length + 1) * 0.00035
  const lng = 129.0755 + offset
  const lat = 35.1785 - offset * 0.6
  equipmentData.value.push({
    id: `reserve-${type.toLowerCase()}-${seed}`,
    name: `RESERVE ${type}`,
    type,
    status: 'stopped',
    power: '0 kW',
    lngLat: [lng, lat]
  })
}

const addByCoordinate = () => {
  equipmentData.value.push({
    id: `custom-${Date.now()}`,
    name: `CUSTOM ${coordForm.value.type}`,
    type: coordForm.value.type,
    status: 'normal',
    power: '100 kW',
    lngLat: [coordForm.value.lng, coordForm.value.lat]
  })
}

const upsertConnection = () => {
  const { fromEquipmentId, toEquipmentId, direction, status } = connectForm.value
  if (!fromEquipmentId || !toEquipmentId || fromEquipmentId === toEquipmentId) return
  const id = `custom-${fromEquipmentId}-${toEquipmentId}`
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
    formData: { name: '', type: 'LOAD', status: 'normal', power: '100 kW', lngLat }
  }
}

const openEditModal = (id: string) => {
  const target = equipmentData.value.find((item) => item.id === id)
  if (!target) return
  modalConfig.value = { show: true, mode: 'edit', formData: { ...target } }
}

const handleZoomChange = (value: number) => {
  mapZoom.value = value
  isUiVisible.value = value > 14.0
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
  connections.value = connections.value.filter((item) => item.fromEquipmentId !== id && item.toEquipmentId !== id)
  modalConfig.value.show = false
}

onMounted(async () => {
  await topologyFeature.initialize()
  syncStatusFromTopology()
})
</script>
