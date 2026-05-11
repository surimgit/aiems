<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useDashboardStore } from '@/stores/dashboard/dashboard.store'
import { useI18n } from 'vue-i18n'
import { useResourceAlias } from '@/features/overview/composables/useResourceAlias'
import type { LocaleType } from '@/app/i18n'
import { useAlarmStore } from '@/stores/alarm/alarm.store'

const dashboardStore = useDashboardStore()
const alarmStore = useAlarmStore()
const { selectedResource, selectedEss } = storeToRefs(dashboardStore)
const { activeAlarms } = storeToRefs(alarmStore)
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

const hasActiveAlarmForSelectedResource = computed(() => {
  const resourceId = selectedResource.value?.resource_id
  if (!resourceId) return false
  const lower = resourceId.toLowerCase()
  return activeAlarms.value.some((alarm) => {
    const target = (alarm.ess_id ?? '').toLowerCase()
    const message = (alarm.message ?? '').toLowerCase()
    return target === lower || message.includes(lower)
  })
})

const displayedStatusLabel = computed(() => {
  const rawStatus = selectedResource.value?.status
  if (!rawStatus) return t('common.noData')
  if (hasActiveAlarmForSelectedResource.value && String(rawStatus).toUpperCase() === 'NORMAL') {
    return `${toStatusLabel(rawStatus)} (ALARM_ACTIVE)`
  }
  return toStatusLabel(rawStatus)
})

const selectedResourceDisplayName = computed(() => {
  if (!selectedResource.value) return ''
  const fallback = selectedResource.value.name || selectedResource.value.resource_id
  return getDisplayName(selectedResource.value.resource_id, fallback, locale.value as LocaleType)
})

const modeLabel = computed(() => selectedResource.value?.telemetry?.operating_mode ?? '-')
const currentLabel = computed(() => selectedResource.value?.telemetry?.i_amp ?? '-')
const frequencyLabel = computed(() => selectedResource.value?.telemetry?.f_hz ?? '-')
const pfLabel = computed(() => selectedResource.value?.telemetry?.pf ?? '-')
const socLabel = computed(() => selectedResource.value?.telemetry?.soc ?? selectedEss.value?.soc ?? '-')

const imageFallback = ref(false)

const equipmentImageSrc = computed(() => {
  const type = (selectedResource.value?.resource_type ?? 'unknown').toLowerCase()
  return `/images/equipment/${type}.png`
})

const equipmentImageAlt = computed(() => {
  if (!selectedResource.value) return 'equipment'
  return `${selectedResource.value.resource_type} image`
})

watch(
  () => selectedResource.value?.resource_id,
  () => {
    imageFallback.value = false
  }
)

const beginEdit = () => {
  if (!selectedResource.value) return
  const resourceId = selectedResource.value.resource_id
  const fallback = selectedResource.value.name || selectedResource.value.resource_id
  draftName.value = getAlias(resourceId, locale.value as LocaleType) ?? fallback
  editing.value = true
  imageFallback.value = false
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

      <div class="equipment-visual">
        <img
          v-if="!imageFallback"
          class="equipment-image"
          :src="equipmentImageSrc"
          :alt="equipmentImageAlt"
          @error="imageFallback = true"
        />
        <div v-else class="equipment-image-fallback">{{ selectedResource.resource_type }}</div>
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
        <dt>{{ t('selectedResource.info.status') }}</dt><dd>{{ displayedStatusLabel }}</dd>
        <dt>{{ t('selectedResource.info.commsStatus') }}</dt><dd>{{ selectedResource.comms_health ?? t('common.noData') }}</dd>
        <dt>{{ t('selectedResource.info.currentPower') }}</dt><dd>{{ selectedResource.telemetry?.p_kw ?? '-' }} kW</dd>
        <dt>{{ t('selectedResource.info.voltage') }}</dt><dd>{{ selectedResource.telemetry?.v_volt ?? '-' }} V</dd>
        <dt>전류</dt><dd>{{ currentLabel }} A</dd>
        <dt>주파수</dt><dd>{{ frequencyLabel }} Hz</dd>
        <dt>역률</dt><dd>{{ pfLabel }}</dd>
        <dt>운전 모드</dt><dd>{{ modeLabel }}</dd>
        <dt>SOC</dt><dd>{{ socLabel }}<span v-if="socLabel !== '-'">%</span></dd>
        <dt v-if="selectedEss">{{ t('selectedResource.info.capacity') }}</dt><dd v-if="selectedEss">{{ selectedEss.capacity_kwh }} kWh</dd>
        <dt v-if="selectedResource.resource_type === 'SWITCH'">스위치 위치</dt><dd v-if="selectedResource.resource_type === 'SWITCH'">{{ selectedResource.position ?? '-' }}</dd>
        <dt v-if="selectedResource.resource_type === 'SWITCH'">인터록</dt><dd v-if="selectedResource.resource_type === 'SWITCH'">{{ selectedResource.interlock_blocked ? '차단' : '정상' }}</dd>
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

.equipment-visual {
  @apply mb-3 rounded border border-slate-700 bg-slate-900/40 p-2;
}

.equipment-image {
  @apply h-20 w-full rounded object-contain bg-slate-950/60;
}

.equipment-image-fallback {
  @apply flex h-20 w-full items-center justify-center rounded bg-slate-950/60 text-xs text-slate-400;
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
