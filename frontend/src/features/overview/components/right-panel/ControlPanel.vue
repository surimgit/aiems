<script setup lang="ts">
import { ref } from 'vue'
import { storeToRefs } from 'pinia'
import { useDashboardStore } from '@/stores/dashboard/dashboard.store'
import { useControlStore } from '@/stores/control/control.store'
import type { CommandAction } from '@/types/common'

const dashboardStore = useDashboardStore()
const controlStore = useControlStore()

const { selectedEss } = storeToRefs(dashboardStore)
const { loading, error } = storeToRefs(controlStore)

const resultMessage = ref('')

const submit = async (action: CommandAction) => {
  if (!selectedEss.value) {
    resultMessage.value = '선택된 ESS가 없습니다.'
    return
  }

  try {
    const result = await controlStore.submitCommand({
      site_id: controlStore.siteId,
      edge_id: controlStore.edgeId,
      target_resource_id: selectedEss.value.ess_id,
      action
    })
    resultMessage.value = `명령 전송 완료: ${result.status}`
  } catch {
    resultMessage.value = '명령 전송 실패'
  }
}
</script>

<template>
  <div class="panel-content space-y-3">
    <p class="text-xs text-slate-400">
      대상: <span class="text-slate-100">{{ selectedEss?.name || selectedEss?.ess_id || '선택 없음' }}</span>
    </p>
    <div class="grid grid-cols-2 gap-2">
      <button class="control-btn" :disabled="!selectedEss || loading" @click="submit('START_CHARGE')">충전 시작</button>
      <button class="control-btn" :disabled="!selectedEss || loading" @click="submit('STOP_CHARGE')">충전 중지</button>
      <button class="control-btn" :disabled="!selectedEss || loading" @click="submit('START_DISCHARGE')">방전 시작</button>
      <button class="control-btn" :disabled="!selectedEss || loading" @click="submit('STOP_DISCHARGE')">방전 중지</button>
    </div>
    <p v-if="resultMessage" class="text-xs text-cyan-300">{{ resultMessage }}</p>
    <p v-if="error" class="text-xs text-red-400">{{ error }}</p>
  </div>
</template>

<style scoped>
.panel-content {
  @apply rounded border border-slate-700 bg-slate-950/60 p-3 text-sm text-slate-300;
}

.control-btn {
  @apply rounded border border-slate-600 px-2 py-1 text-xs text-slate-100 disabled:opacity-50;
}
</style>
