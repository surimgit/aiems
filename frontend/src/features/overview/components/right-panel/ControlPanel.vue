<script setup lang="ts">
import { ref } from 'vue'
import { storeToRefs } from 'pinia'
import { useDashboardStore } from '@/stores/dashboard/dashboard.store'
import { useControlStore } from '@/stores/control/control.store'
import type { CommandAction } from '@/types/common'
import { useI18n } from 'vue-i18n'

const dashboardStore = useDashboardStore()
const controlStore = useControlStore()

const { selectedEss, selectedResource } = storeToRefs(dashboardStore)
const { loading, error } = storeToRefs(controlStore)
const { t } = useI18n()

const resultMessage = ref('')

const submit = async (action: CommandAction) => {
  if (!selectedEss.value) {
    resultMessage.value = t('selectedResource.control.noEssSelected')
    return
  }

  try {
    const result = await controlStore.submitCommand({
      site_id: controlStore.siteId,
      edge_id: controlStore.edgeId,
      target_resource_id: selectedEss.value.ess_id,
      action
    })
    resultMessage.value = `${t('selectedResource.control.commandSuccess')}: ${result.status}`
  } catch {
    resultMessage.value = t('selectedResource.control.commandFailed')
  }
}
</script>

<template>
  <div class="panel-content space-y-3">
    <p class="text-xs text-slate-400">
      {{ t('selectedResource.control.target') }}: <span class="text-slate-100">{{ selectedResource?.name || selectedResource?.resource_id || t('selectedResource.control.noneSelected') }}</span>
    </p>
    <p v-if="selectedResource && selectedResource.resource_type !== 'ESS'" class="text-xs text-amber-300">
      {{ t('selectedResource.control.onlyEssSupported') }}
    </p>
    <div class="grid grid-cols-2 gap-2">
      <button class="control-btn" :disabled="!selectedEss || loading" @click="submit('START_CHARGE')">{{ t('selectedResource.control.actions.startCharge') }}</button>
      <button class="control-btn" :disabled="!selectedEss || loading" @click="submit('STOP_CHARGE')">{{ t('selectedResource.control.actions.stopCharge') }}</button>
      <button class="control-btn" :disabled="!selectedEss || loading" @click="submit('START_DISCHARGE')">{{ t('selectedResource.control.actions.startDischarge') }}</button>
      <button class="control-btn" :disabled="!selectedEss || loading" @click="submit('STOP_DISCHARGE')">{{ t('selectedResource.control.actions.stopDischarge') }}</button>
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
