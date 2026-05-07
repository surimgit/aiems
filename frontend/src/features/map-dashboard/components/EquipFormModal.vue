<template>
  <div class="absolute inset-0 z-50 flex items-center justify-center bg-black/60 p-3 backdrop-blur-sm">
    <div class="max-h-[78vh] w-64 overflow-y-auto rounded-lg border border-slate-600 bg-slate-800 p-3 text-white shadow-2xl">
      <h3 class="mb-2 border-b border-slate-600 pb-1.5 text-sm font-bold">
        {{ mode === 'add' ? '새 장비 추가' : '장비 정보 수정' }}
      </h3>

      <div class="flex flex-col gap-1.5">
        <label class="text-xs text-slate-300">장비 이름</label>
        <input v-model="localForm.name" type="text" class="rounded border border-slate-700 bg-slate-900 px-2 py-1.5 text-xs" />

        <label class="text-xs text-slate-300">장비 타입</label>
        <select v-model="localForm.type" class="rounded border border-slate-700 bg-slate-900 px-2 py-1.5 text-xs">
          <option value="GENERATOR">발전기</option>
          <option value="ESS">ESS</option>
          <option value="LOAD">LOAD</option>
        </select>

        <label class="text-xs text-slate-300">전력량</label>
        <input v-model="localForm.power" type="text" class="rounded border border-slate-700 bg-slate-900 px-2 py-1.5 text-xs" />

        <label class="text-xs text-slate-300">상태</label>
        <select v-model="localForm.status" class="rounded border border-slate-700 bg-slate-900 px-2 py-1.5 text-xs">
          <option value="normal">정상</option>
          <option value="stopped">중지</option>
          <option value="error">이상</option>
        </select>

        <div class="mt-1.5 flex justify-between">
          <button v-if="mode === 'edit'" class="rounded bg-rose-600 px-2.5 py-1 text-xs font-bold hover:bg-rose-500" @click="emit('delete')">삭제</button>
          <div v-else />
          <div class="flex gap-2">
            <button class="rounded bg-slate-700 px-2.5 py-1 text-xs hover:bg-slate-600" @click="emit('close')">취소</button>
            <button class="rounded bg-emerald-600 px-2.5 py-1 text-xs font-bold hover:bg-emerald-500" @click="emit('save', localForm)">
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
