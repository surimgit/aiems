<script setup lang="ts">
import { computed, ref } from 'vue'
import { storeToRefs } from 'pinia'
import { useDashboardStore } from '@/stores/dashboard/dashboard.store'
import { useI18n } from 'vue-i18n'
import { useResourceAlias } from '@/features/overview/composables/useResourceAlias'
import type { LocaleType } from '@/app/i18n'

const dashboardStore = useDashboardStore()
const { selectedResource, selectedEss } = storeToRefs(dashboardStore)
const { t, locale } = useI18n()
const { getAlias, getDisplayName, stageAlias } = useResourceAlias()

const editing = ref(false)
const draftName = ref('')

const statusLabelMap: Record<string, string> = {
  NORMAL: 'status.normal',
  WARNING: 'status.warning',
  EMERGENCY: 'status.critical',
  OFFLINE: 'status.offline',
  idle: 'status.idle',
  charging: 'status.charging',
  discharging: 'status.discharging',
  fault: 'status.fault'
}

const toStatusLabel = (value: string | undefined) => {
  if (!value) return t('common.noData')
  const key = statusLabelMap[value]
  return key ? t(key) : value
}

const selectedResourceDisplayName = computed(() => {
  if (!selectedResource.value) return ''
  const fallback = selectedResource.value.name || selectedResource.value.resource_id
  return getDisplayName(selectedResource.value.resource_id, fallback, locale.value as LocaleType)
})

const beginEdit = () => {
  if (!selectedResource.value) return
  const resourceId = selectedResource.value.resource_id
  const fallback = selectedResource.value.name || selectedResource.value.resource_id
  draftName.value = getAlias(resourceId, locale.value as LocaleType) ?? fallback
  editing.value = true
}

const cancelEdit = () => {
  editing.value = false
  draftName.value = ''
}

const saveEdit = () => {
  if (!selectedResource.value) return
  const resourceId = selectedResource.value.resource_id
  const fallback = selectedResource.value.name || selectedResource.value.resource_id
  stageAlias(resourceId, locale.value as LocaleType, draftName.value, fallback)

  editing.value = false
}
</script>

<template>
  <div class="panel-content">
    <template v-if="selectedResource">
      <div class="title-row">
        <p class="title">{{ selectedResourceDisplayName }}</p>
        <button v-if="!editing" type="button" class="edit-btn" @click="beginEdit">{{ t('selectedResource.info.editName') }}</button>
      </div>

      <div v-if="editing" class="edit-wrap">
        <input v-model="draftName" class="edit-input" type="text" :placeholder="t('selectedResource.info.editNamePlaceholder')" />
        <div class="edit-actions">
          <button type="button" class="edit-action-btn" @click="saveEdit">{{ t('common.apply') }}</button>
          <button type="button" class="edit-action-btn" @click="cancelEdit">{{ t('common.cancel') }}</button>
        </div>
      </div>

      <dl class="grid grid-cols-2 gap-2 text-xs text-slate-300">
        <dt>{{ t('selectedResource.info.equipmentId') }}</dt><dd>{{ selectedResource.resource_id }}</dd>
        <dt>{{ t('selectedResource.info.equipmentType') }}</dt><dd>{{ selectedResource.resource_type }}</dd>
        <dt>{{ t('selectedResource.info.status') }}</dt><dd>{{ toStatusLabel(selectedResource.status) }}</dd>
        <dt>{{ t('selectedResource.info.commsStatus') }}</dt><dd>{{ selectedResource.comms_health ?? t('common.noData') }}</dd>
        <dt>{{ t('selectedResource.info.currentPower') }}</dt><dd>{{ selectedResource.telemetry?.p_kw ?? '-' }} kW</dd>
        <dt>{{ t('selectedResource.info.voltage') }}</dt><dd>{{ selectedResource.telemetry?.v_volt ?? '-' }} V</dd>
        <dt v-if="selectedEss">SOC</dt><dd v-if="selectedEss">{{ selectedEss.soc }}%</dd>
        <dt v-if="selectedEss">{{ t('selectedResource.info.capacity') }}</dt><dd v-if="selectedEss">{{ selectedEss.capacity_kwh }} kWh</dd>
      </dl>
    </template>
    <p v-else class="text-sm text-slate-400">{{ t('selectedResource.info.empty') }}</p>
  </div>
</template>

<style scoped>
.panel-content {
  @apply rounded border border-slate-700 bg-slate-950/60 p-3 text-sm text-slate-300;
}

.title {
  @apply mb-3 text-sm font-semibold text-slate-100;
}

.title-row {
  @apply mb-2 flex items-center justify-between gap-2;
}

.edit-btn {
  @apply rounded border border-slate-600 px-2 py-0.5 text-[11px] text-slate-300;
}

.edit-wrap {
  @apply mb-3 rounded border border-slate-700 bg-slate-900/50 p-2;
}

.edit-input {
  @apply w-full rounded border border-slate-700 bg-slate-950 px-2 py-1 text-xs text-slate-100 outline-none;
}

.edit-actions {
  @apply mt-2 flex justify-end gap-2;
}

.edit-action-btn {
  @apply rounded border border-slate-600 px-2 py-1 text-[11px] text-slate-300;
}
</style>
