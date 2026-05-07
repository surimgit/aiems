<template>
  <div class="absolute inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
    <div class="w-80 rounded-lg border border-slate-600 bg-slate-800 p-6 text-white shadow-2xl">
      <h3 class="mb-4 border-b border-slate-600 pb-2 text-lg font-bold">
        {{ mode === 'add' ? '새 장비 추가' : '장비 정보 수정' }}
      </h3>

      <div class="flex flex-col gap-3">
        <label class="text-sm text-slate-300">장비 이름</label>
        <input v-model="localForm.name" type="text" class="rounded border border-slate-700 bg-slate-900 p-2 text-sm" />

        <label class="text-sm text-slate-300">장비 타입</label>
        <select v-model="localForm.type" class="rounded border border-slate-700 bg-slate-900 p-2 text-sm">
          <option value="GENERATOR">발전기</option>
          <option value="ESS">ESS</option>
          <option value="LOAD">LOAD</option>
        </select>

        <label class="text-sm text-slate-300">전력량</label>
        <input v-model="localForm.power" type="text" class="rounded border border-slate-700 bg-slate-900 p-2 text-sm" />

        <label class="text-sm text-slate-300">상태</label>
        <select v-model="localForm.status" class="rounded border border-slate-700 bg-slate-900 p-2 text-sm">
          <option value="normal">정상</option>
          <option value="stopped">중지</option>
          <option value="error">이상</option>
        </select>

        <div class="mt-4 flex justify-between">
          <button v-if="mode === 'edit'" class="rounded bg-rose-600 px-3 py-1.5 text-sm font-bold hover:bg-rose-500" @click="emit('delete')">삭제</button>
          <div v-else />
          <div class="flex gap-2">
            <button class="rounded bg-slate-700 px-3 py-1.5 text-sm hover:bg-slate-600" @click="emit('close')">취소</button>
            <button class="rounded bg-emerald-600 px-3 py-1.5 text-sm font-bold hover:bg-emerald-500" @click="emit('save', localForm)">
              {{ mode === 'add' ? '배치하기' : '저장' }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, watch } from 'vue'
import type { EquipmentFormData } from '../types'

const props = defineProps<{
  mode: 'add' | 'edit'
  initialData: EquipmentFormData
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'save', payload: EquipmentFormData): void
  (e: 'delete'): void
}>()

const localForm = reactive<EquipmentFormData>({ ...props.initialData })

watch(
  () => props.initialData,
  (next) => {
    Object.assign(localForm, next)
  },
  { deep: true }
)
</script>
