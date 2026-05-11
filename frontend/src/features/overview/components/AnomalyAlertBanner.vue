<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useI18n } from 'vue-i18n'
import type { AlarmData } from '@/types/common'
import { useDashboardStore } from '@/stores/dashboard/dashboard.store'

const props = defineProps<{
  activeAlarms: AlarmData[]
}>()

const emit = defineEmits<{
  (e: 'open-alarm-panel'): void
  (e: 'open-resource', resourceId: string): void
}>()

const { t } = useI18n()
const dismissed = ref(false)
const dashboardStore = useDashboardStore()
const {
  resources,
  resourcesLastFetchedAt,
  topologyLastFetchedAt,
  resourcesFetchFailStreak,
  topologyFetchFailStreak
} = storeToRefs(dashboardStore)

const COMM_FAILURE_THRESHOLD = 3
const COMM_STALE_TTL_MS = 8_000
const nowTs = ref(Date.now())
const nowTicker = setInterval(() => {
  nowTs.value = Date.now()
}, 1_000)
onUnmounted(() => {
  clearInterval(nowTicker)
})

type SystemAnomaly = {
  level: 'critical' | 'warning'
  causeCode: string
  causeMessage: string
  resourceId: string | null
  timestamp: number
}

const systemAnomalies = computed<SystemAnomaly[]>(() => {
  const list: SystemAnomaly[] = []

  const resourceFail = resourcesFetchFailStreak.value
  const topologyFail = topologyFetchFailStreak.value
  const latestFetchedAt = Math.max(resourcesLastFetchedAt.value ?? 0, topologyLastFetchedAt.value ?? 0)
  const staleMs = latestFetchedAt > 0 ? nowTs.value - latestFetchedAt : 0

  if (resourceFail >= COMM_FAILURE_THRESHOLD || topologyFail >= COMM_FAILURE_THRESHOLD) {
    const blockedPart = resourceFail >= topologyFail ? 'resources' : 'topology'
    const failCount = Math.max(resourceFail, topologyFail)
    list.push({
      level: 'critical',
      causeCode: 'COMMUNICATION_LOSS',
      causeMessage: `통신 실패 연속 ${failCount}회 (${blockedPart} fetch 실패)`,
      resourceId: null,
      timestamp: nowTs.value
    })
  } else if (latestFetchedAt > 0 && staleMs > COMM_STALE_TTL_MS) {
    list.push({
      level: 'critical',
      causeCode: 'HEARTBEAT_TIMEOUT',
      causeMessage: `데이터 갱신 지연 ${(staleMs / 1000).toFixed(0)}초 (stale)`,
      resourceId: null,
      timestamp: nowTs.value
    })
  }

  for (const resource of resources.value) {
    const status = (resource.status ?? '').toUpperCase()
    const comms = (resource.comms_health ?? '').toUpperCase()

    if (status.includes('EMERGENCY') || status.includes('FAULT') || status.includes('ERROR') || status.includes('OFFLINE')) {
      list.push({
        level: 'critical',
        causeCode: 'RESOURCE_FAULT',
        causeMessage: `${resource.name ?? resource.resource_id} 상태 이상 (${status || 'UNKNOWN'})`,
        resourceId: resource.resource_id,
        timestamp: nowTs.value
      })
      continue
    }

    if (comms.includes('DISCONNECT') || comms.includes('OFFLINE') || comms.includes('TIMEOUT') || comms.includes('ERROR') || comms.includes('STALE')) {
      list.push({
        level: 'critical',
        causeCode: 'BROKER_DISCONNECTED',
        causeMessage: `${resource.name ?? resource.resource_id} 통신 이상 (${comms || 'UNKNOWN'})`,
        resourceId: resource.resource_id,
        timestamp: nowTs.value
      })
    }
  }

  return list
})

const newestSystemAnomaly = computed(() => {
  if (systemAnomalies.value.length === 0) return null
  return [...systemAnomalies.value].sort((a, b) => b.timestamp - a.timestamp)[0]
})

const systemAnomalySignature = computed(() =>
  newestSystemAnomaly.value
    ? `${newestSystemAnomaly.value.causeCode}:${newestSystemAnomaly.value.causeMessage}`
    : ''
)

const alarmSignature = computed(() => {
  return props.activeAlarms
    .map((alarm) => `${alarm.alarm_id ?? ''}|${alarm.code}|${alarm.message}|${alarm.timestamp}|${alarm.acknowledged ? '1' : '0'}`)
    .join('||')
})

const controlRetryPattern = /명령 전달\s*\d+회\s*재시도\s*후\s*최종\s*실패/i

const parseControlRetryFailure = (message: string): { resourceId: string | null; causeMessage: string } | null => {
  if (!controlRetryPattern.test(message)) return null
  const idMatch = message.match(/실패\s*:\s*([\w-]+)/i)
  const resourceId = idMatch?.[1] ?? null
  const causeMessage = resourceId
    ? `${resourceId} 제어 채널 전달 실패 (edge 또는 MQTT 연결 상태 확인 필요)`
    : '제어 채널 전달 실패 (edge 또는 MQTT 연결 상태 확인 필요)'
  return { resourceId, causeMessage }
}

watch(
  () => `${alarmSignature.value}::${systemAnomalySignature.value}`,
  () => {
    dismissed.value = false
  },
  { immediate: true }
)

const criticalCount = computed(() => props.activeAlarms.filter((alarm) => alarm.level === 'critical').length)
const warningCount = computed(() => props.activeAlarms.filter((alarm) => alarm.level === 'warning').length)
const activeCount = computed(() => props.activeAlarms.length + systemAnomalies.value.length)

const visible = computed(() => activeCount.value > 0 && !dismissed.value)

const severity = computed<'critical' | 'warning' | 'info'>(() => {
  if (newestSystemAnomaly.value?.level === 'critical') return 'critical'
  if (criticalCount.value > 0) return 'critical'
  if (warningCount.value > 0) return 'warning'
  return 'info'
})

const newestAlarmMessage = computed(() => {
  if (newestSystemAnomaly.value) {
    return `[${newestSystemAnomaly.value.causeCode}] ${newestSystemAnomaly.value.causeMessage}`
  }
  if (!visible.value) return ''

  const sorted = [...props.activeAlarms].sort((a, b) => {
    const timeA = new Date(a.timestamp).getTime()
    const timeB = new Date(b.timestamp).getTime()
    return (Number.isFinite(timeB) ? timeB : 0) - (Number.isFinite(timeA) ? timeA : 0)
  })

  const latest = sorted[0]
  const message = latest?.message?.trim()
  if (message) {
    const parsed = parseControlRetryFailure(message)
    if (parsed) {
      return `[COMMUNICATION_LOSS] ${parsed.causeMessage}`
    }
    return message
  }
  return latest?.code || t('common.noData')
})

const newestTargetResourceId = computed(() => {
  if (newestSystemAnomaly.value?.resourceId) return newestSystemAnomaly.value.resourceId
  if (!visible.value) return null

  const sorted = [...props.activeAlarms].sort((a, b) => {
    const timeA = new Date(a.timestamp).getTime()
    const timeB = new Date(b.timestamp).getTime()
    return (Number.isFinite(timeB) ? timeB : 0) - (Number.isFinite(timeA) ? timeA : 0)
  })

  const latest = sorted[0]
  const parsed = parseControlRetryFailure(latest?.message ?? '')
  if (parsed?.resourceId) return parsed.resourceId
  return latest?.ess_id || null
})

const bannerText = computed(() => {
  if (newestAlarmMessage.value) return newestAlarmMessage.value
  const resourceId = newestTargetResourceId.value
  if (!resourceId) return t('anomalyBanner.simple')

  const resourceName = resources.value.find((item) => item.resource_id === resourceId)?.name || resourceId
  return t('anomalyBanner.detectedWithTarget', { name: resourceName })
})

const openAlarmPanel = () => {
  const resourceId = newestTargetResourceId.value
  if (resourceId) {
    emit('open-resource', resourceId)
    return
  }

  emit('open-alarm-panel')
}

const closeBanner = () => {
  dismissed.value = true
}
</script>

<template>
  <section
    v-if="visible"
    class="anomaly-banner"
    :class="`severity-${severity}`"
    role="button"
    aria-live="polite"
    tabindex="0"
    @click="openAlarmPanel"
    @keydown.enter="openAlarmPanel"
    @keydown.space.prevent="openAlarmPanel"
  >
    <div class="content-wrap">
      <div class="left-wrap">
        <span class="icon-wrap" aria-hidden="true">
          <svg viewBox="0 0 24 24" class="icon">
            <path d="M12 3 1.8 20.5h20.4L12 3Zm0 5.5c.5 0 .9.4.9.9v5.3a.9.9 0 1 1-1.8 0V9.4c0-.5.4-.9.9-.9Zm0 9.7a1.1 1.1 0 1 1 0-2.2 1.1 1.1 0 0 1 0 2.2Z" fill="currentColor"/>
          </svg>
        </span>

        <div class="text-wrap">
          <p class="title">{{ bannerText }}</p>
        </div>
      </div>

      <div class="right-wrap">
        <button type="button" class="close-btn" :aria-label="t('common.close')" @click.stop="closeBanner">×</button>
      </div>
    </div>
  </section>
</template>

<style scoped>
.anomaly-banner {
  @apply rounded px-3 py-2;
}

.content-wrap {
  @apply flex items-center justify-between gap-3;
}

.left-wrap {
  @apply flex min-w-0 items-center gap-2;
}

.icon-wrap {
  @apply inline-flex h-6 w-6 flex-shrink-0 items-center justify-center text-white;
}

.icon {
  @apply h-5 w-5;
}

.text-wrap {
  @apply min-w-0;
}

.title {
  @apply text-base font-semibold;
}

.right-wrap {
  @apply flex items-center gap-2;
}

.close-btn {
  @apply h-7 w-7 rounded text-xl leading-none text-white/90 hover:bg-white/15;
}

.severity-critical {
  @apply bg-red-600/70 text-white backdrop-blur;
}

.severity-warning {
  @apply bg-amber-500/70 text-slate-950 backdrop-blur;
}

.severity-info {
  @apply bg-sky-600/70 text-white backdrop-blur;
}
</style>
