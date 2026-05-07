<template>
  <div class="pointer-events-none absolute inset-0 z-10 h-full w-full">
    <div
      v-for="equip in equipmentData"
      :key="equip.id"
      class="absolute w-[150px] rounded-lg border border-white/10 bg-slate-900/40 text-white shadow-xl backdrop-blur-md transition-transform duration-75 pointer-events-auto"
      :class="{ 'cursor-pointer hover:border-blue-500': isEditMode }"
      :style="getStyle(equip.id)"
      @click="handleEquipClick(equip.id)"
    >
      <div
        class="flex justify-between border-b border-white/10 px-3 py-2 text-[13px] font-bold"
        :class="{
          'text-white': equip.status === 'normal',
          'text-slate-400': equip.status === 'stopped',
          'text-rose-400': equip.status === 'error'
        }"
      >
        <span>{{ equip.name }}</span>
        <span v-if="isEditMode" class="text-[10px]">✏️</span>
      </div>
      <div class="px-3 py-2 text-[12px] opacity-80">
        <p>전력: {{ equip.power }}</p>
        <p>상태: {{ statusLabel[equip.status] }}</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { MapEquipment } from '../types'

const props = defineProps<{
  equipmentData: MapEquipment[]
  uiPositions: Record<string, { x: number; y: number }>
  mapZoom: number
  isEditMode: boolean
}>()

const emit = defineEmits<{
  (e: 'edit-equip', id: string): void
}>()

const statusLabel = {
  normal: '정상',
  stopped: '중지',
  error: '이상'
}

type Anchor = 'left' | 'right' | 'top' | 'bottom'

const anchorById = computed<Record<string, Anchor>>(() => {
  const width = typeof window !== 'undefined' ? window.innerWidth : 1920
  const leftCut = width * 0.35
  const rightCut = width * 0.65

  const result: Record<string, Anchor> = {}
  const centerItems: Array<{ id: string; y: number }> = []

  props.equipmentData.forEach((equip) => {
    const pos = props.uiPositions[equip.id]
    if (!pos) return

    if (pos.x <= leftCut) {
      result[equip.id] = 'left'
      return
    }
    if (pos.x >= rightCut) {
      result[equip.id] = 'right'
      return
    }
    centerItems.push({ id: equip.id, y: pos.y })
  })

  centerItems.sort((a, b) => a.y - b.y)
  centerItems.forEach((item, index) => {
    const half = Math.ceil(centerItems.length / 2)
    result[item.id] = index < half ? 'top' : 'bottom'
  })

  return result
})

const clamp = (value: number, min: number, max: number) => Math.max(min, Math.min(max, value))

const getStyle = (id: string) => {
  const pos = props.uiPositions[id]
  if (!pos) return { display: 'none' }

  const width = typeof window !== 'undefined' ? window.innerWidth : 1920
  const height = typeof window !== 'undefined' ? window.innerHeight : 1080
  const modalWidth = 150
  const modalHeight = 90
  const anchor = anchorById.value[id] ?? 'top'
  const zoomScale = clamp(0.8 + (props.mapZoom - 14) * 0.1, 0.8, 1)

  let left = pos.x - modalWidth / 2
  let top = pos.y - 140

  if (anchor === 'left') {
    left = pos.x - modalWidth - 14
    top = pos.y - modalHeight / 2
  } else if (anchor === 'right') {
    left = pos.x + 14
    top = pos.y - modalHeight / 2
  } else if (anchor === 'top') {
    left = pos.x - modalWidth / 2
    top = pos.y - modalHeight - 48
  } else {
    left = pos.x - modalWidth / 2
    top = pos.y + 16
  }

  left = clamp(left, 8, width - modalWidth - 8)
  top = clamp(top, 8, height - modalHeight - 8)

  return {
    left: `${left}px`,
    top: `${top}px`,
    transform: `scale(${zoomScale})`,
    transformOrigin: 'top left'
  }
}

const handleEquipClick = (id: string) => {
  if (props.isEditMode) emit('edit-equip', id)
}
</script>
