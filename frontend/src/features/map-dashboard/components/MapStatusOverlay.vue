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
import type { MapEquipment } from '../types'

const props = defineProps<{
  equipmentData: MapEquipment[]
  uiPositions: Record<string, { x: number; y: number }>
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

const getStyle = (id: string) => {
  const pos = props.uiPositions[id]
  if (!pos) return { display: 'none' }
  return { transform: `translate(calc(${pos.x}px - 50%), calc(${pos.y}px - 140px))` }
}

const handleEquipClick = (id: string) => {
  if (props.isEditMode) emit('edit-equip', id)
}
</script>
