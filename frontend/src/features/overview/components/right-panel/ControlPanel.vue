<script setup lang="ts">
import { computed, ref } from 'vue'
import { storeToRefs } from 'pinia'
import { useDashboardStore } from '@/stores/dashboard/dashboard.store'
import { useControlStore } from '@/stores/control/control.store'
import type { CommandAction } from '@/types/common'
import { useI18n } from 'vue-i18n'

const dashboardStore = useDashboardStore()
const controlStore = useControlStore()

const { selectedResource } = storeToRefs(dashboardStore)
const { loading, error, pendingCommands, commandHistory } = storeToRefs(controlStore)
const { t } = useI18n()

const resultMessage = ref('')
const localActionStatus = ref<Record<string, { status: string; updatedAt: number }>>({})

interface ActionItem {
  action: CommandAction
  label: string
}

const actionMap: Record<string, ActionItem[]> = {
  ESS: [
    { action: 'START_CHARGE', label: '충전 시작' },
    { action: 'STOP_CHARGE', label: '충전 중지' },
    { action: 'START_DISCHARGE', label: '방전 시작' },
    { action: 'STOP_DISCHARGE', label: '방전 중지' },
    { action: 'STANDBY', label: '대기 전환' }
  ],
  DIESEL_GENERATOR: [
    { action: 'START_GENERATOR', label: '발전기 기동' },
    { action: 'STOP_GENERATOR', label: '발전기 정지' },
    { action: 'STANDBY', label: '대기 전환' }
  ],
  LOAD: [
    { action: 'SHED_LOAD', label: '부하 차단' },
    { action: 'RESTORE_LOAD', label: '부하 복구' }
  ],
  SWITCH: [
    { action: 'OPEN_SWITCH', label: '스위치 오픈' },
    { action: 'CLOSE_SWITCH', label: '스위치 클로즈' }
  ],
  SOLAR: [
    { action: 'SET_POWER_LIMIT', label: '출력 제한' },
    { action: 'STANDBY', label: '대기 전환' }
  ]
}

const selectedActions = computed(() => {
  if (!selectedResource.value) return []
  return actionMap[selectedResource.value.resource_type] ?? []
})

const isActionActive = (action: CommandAction): boolean => {
  const resource = selectedResource.value
  if (!resource) return false
  const mode = (resource.telemetry?.operating_mode ?? '').toLowerCase()
  const isChargeMode = mode === 'charge' || mode === 'charging'
  const isDischargeMode = mode === 'discharge' || mode === 'discharging'
  const isStandbyMode = mode === 'standby' || mode === 'idle'
  if (resource.resource_type === 'ESS') {
    if (action === 'START_CHARGE') return isChargeMode
    if (action === 'START_DISCHARGE') return isDischargeMode
    if (action === 'STANDBY') return isStandbyMode
  }
  if (resource.resource_type === 'DIESEL_GENERATOR') {
    if (action === 'START_GENERATOR') return mode.includes('run') || mode.includes('start')
    if (action === 'STANDBY') return mode.includes('standby') || mode.includes('off') || mode.includes('idle')
  }
  if (resource.resource_type === 'SWITCH') {
    const pos = (resource.position ?? '').toUpperCase()
    if (action === 'OPEN_SWITCH') return pos === 'OPEN'
    if (action === 'CLOSE_SWITCH') return pos === 'CLOSED'
  }
  return false
}

const commandStatusOrder: Record<string, number> = {
  CREATED: 1,
  ACCEPTED: 2,
  IN_PROGRESS: 3,
  RUNNING: 4,
  COMPLETED: 5,
  REJECTED: 6,
  FAILED: 7,
  TIMED_OUT: 8,
  BLOCKED: 9,
  EXPIRED: 10,
  IGNORED: 11
}

const COMMAND_STATUS_TTL_MS = 20_000
const isFreshCommand = (createdAt: string): boolean => {
  const ts = Date.parse(createdAt ?? '')
  if (!Number.isFinite(ts)) return false
  return Date.now() - ts <= COMMAND_STATUS_TTL_MS
}

const latestCommandByAction = computed(() => {
  if (!selectedResource.value) return new Map<CommandAction, { status: string; created_at: string }>()
  const resourceId = selectedResource.value.resource_id.toLowerCase()
  const all = [...pendingCommands.value, ...commandHistory.value]
    .filter((item) => (item.target_resource_id ?? '').toLowerCase() === resourceId)
    .filter((item) => isFreshCommand(item.created_at))
    .sort((a, b) => {
      const ts = (Date.parse(b.created_at ?? '') || 0) - (Date.parse(a.created_at ?? '') || 0)
      if (ts !== 0) return ts
      return (commandStatusOrder[b.status] ?? 0) - (commandStatusOrder[a.status] ?? 0)
    })

  const byAction = new Map<CommandAction, { status: string; created_at: string }>()
  for (const item of all) {
    if (byAction.has(item.action)) continue
    byAction.set(item.action, { status: item.status, created_at: item.created_at })
  }
  return byAction
})

const isInFlightStatus = (status: string) => status === 'CREATED' || status === 'ACCEPTED' || status === 'IN_PROGRESS' || status === 'RUNNING'

const actionStatusLabel = (action: CommandAction): string => {
  const local = localActionStatus.value[action]
  if (local && Date.now() - local.updatedAt <= COMMAND_STATUS_TTL_MS) {
    return local.status
  }

  const command = latestCommandByAction.value.get(action)
  if (!command) return 'IDLE'
  if (!isFreshCommand(command.created_at)) return 'IDLE'
  return command.status
}

const actionStatusClass = (action: CommandAction): string => {
  const status = actionStatusLabel(action)
  if (status === 'FAILED' || status === 'TIMED_OUT' || status === 'BLOCKED' || status === 'REJECTED') return 'error'
  if (status === 'PENDING' || status === 'RUNNING' || status === 'IN_PROGRESS' || status === 'ACCEPTED' || status === 'CREATED') return 'pending'
  if (status === 'COMPLETED') return 'ok'
  return 'idle'
}

const isControlBlocked = computed(() => {
  if (!selectedResource.value) return true
  const status = (selectedResource.value.status ?? '').toUpperCase()
  const comms = (selectedResource.value.comms_health ?? '').toLowerCase()
  const interlockBlocked = selectedResource.value.interlock_blocked === true
  return status === 'EMERGENCY' || status === 'OFFLINE' || comms === 'stale' || interlockBlocked
})

const blockReason = computed(() => {
  if (!selectedResource.value) return '장비를 선택해 주세요.'
  if (selectedResource.value.interlock_blocked) return '인터록으로 제어가 차단되었습니다.'
  if ((selectedResource.value.status ?? '').toUpperCase() === 'EMERGENCY') return 'EMERGENCY 상태에서는 제어할 수 없습니다.'
  if ((selectedResource.value.status ?? '').toUpperCase() === 'OFFLINE') return 'OFFLINE 상태에서는 제어할 수 없습니다.'
  if ((selectedResource.value.comms_health ?? '').toLowerCase() === 'stale') return '통신이 불안정하여 제어가 제한됩니다.'
  return ''
})

const toControlResourceType = (resourceType: string) => {
  if (resourceType === 'DIESEL_GENERATOR') return 'DIESEL'
  return resourceType
}

const submit = async (action: CommandAction) => {
  if (!selectedResource.value) {
    resultMessage.value = '장비를 먼저 선택해 주세요.'
    return
  }

  if (isControlBlocked.value) {
    resultMessage.value = blockReason.value
    return
  }

  try {
    localActionStatus.value[action] = { status: 'PENDING', updatedAt: Date.now() }
    const result = await controlStore.submitCommand({
      site_id: controlStore.siteId,
      device_id: selectedResource.value.resource_id,
      resource_type: toControlResourceType(selectedResource.value.resource_type) as any,
      action
    })
    localActionStatus.value[action] = { status: result.status, updatedAt: Date.now() }
    resultMessage.value = `명령 성공: ${result.status}`
  } catch {
    localActionStatus.value[action] = { status: 'FAILED', updatedAt: Date.now() }
    resultMessage.value = '명령 전달 실패'
  }
}
</script>

<template>
  <div class="panel-content space-y-3">
    <p class="text-xs text-slate-400">
      제어 대상: <span class="text-slate-100">{{ selectedResource?.name || selectedResource?.resource_id || '미선택' }}</span>
    </p>
    <p v-if="isControlBlocked && blockReason" class="text-xs text-amber-300">
      {{ blockReason }}
    </p>

    <p v-if="selectedActions.length === 0" class="text-xs text-slate-500">지원되는 제어 명령이 없습니다.</p>

    <div class="grid grid-cols-2 gap-2">
      <button
        v-for="item in selectedActions"
        :key="item.action"
        class="control-btn"
        :class="{ active: isActionActive(item.action) }"
        :disabled="!selectedResource || loading || isControlBlocked"
        @click="submit(item.action)"
      >
        <span>{{ item.label }}</span>
        <span class="status-chip" :class="actionStatusClass(item.action)">{{ actionStatusLabel(item.action) }}</span>
      </button>
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
  @apply flex items-center justify-between gap-2 rounded border border-slate-600 px-2 py-1 text-xs text-slate-100 disabled:opacity-50;
}

.control-btn.active {
  @apply border-cyan-400 bg-cyan-400/20 text-cyan-100;
}

.status-chip {
  @apply rounded px-1.5 py-0.5 text-[10px] font-semibold;
}

.status-chip.idle {
  @apply bg-slate-700 text-slate-200;
}

.status-chip.pending {
  @apply bg-amber-500/20 text-amber-200;
}

.status-chip.ok {
  @apply bg-cyan-500/20 text-cyan-200;
}

.status-chip.error {
  @apply bg-red-500/20 text-red-200;
}
</style>
