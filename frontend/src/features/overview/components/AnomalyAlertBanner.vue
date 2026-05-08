<script setup lang="ts">
import { computed, ref, watch } from 'vue'
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
const { resources } = storeToRefs(dashboardStore)

watch(
  () => props.activeAlarms,
  () => {
    dismissed.value = false
  },
  { deep: true }
)

const criticalCount = computed(() => props.activeAlarms.filter((alarm) => alarm.level === 'critical').length)
const warningCount = computed(() => props.activeAlarms.filter((alarm) => alarm.level === 'warning').length)
const activeCount = computed(() => props.activeAlarms.length)

const visible = computed(() => activeCount.value > 0 && !dismissed.value)

const severity = computed<'critical' | 'warning' | 'info'>(() => {
  if (criticalCount.value > 0) return 'critical'
  if (warningCount.value > 0) return 'warning'
  return 'info'
})

const newestAlarmMessage = computed(() => {
  if (!visible.value) return ''

  const sorted = [...props.activeAlarms].sort((a, b) => {
    const timeA = new Date(a.timestamp).getTime()
    const timeB = new Date(b.timestamp).getTime()
    return (Number.isFinite(timeB) ? timeB : 0) - (Number.isFinite(timeA) ? timeA : 0)
  })

  const latest = sorted[0]
  const message = latest?.message?.trim()
  if (message) return message
  return latest?.code || t('common.noData')
})

const newestTargetResourceId = computed(() => {
  if (!visible.value) return null

  const sorted = [...props.activeAlarms].sort((a, b) => {
    const timeA = new Date(a.timestamp).getTime()
    const timeB = new Date(b.timestamp).getTime()
    return (Number.isFinite(timeB) ? timeB : 0) - (Number.isFinite(timeA) ? timeA : 0)
  })

  const latest = sorted[0]
  return latest?.ess_id || null
})

const bannerText = computed(() => {
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
  @apply bg-red-600 text-white;
}

.severity-warning {
  @apply bg-amber-500 text-slate-950;
}

.severity-info {
  @apply bg-sky-600 text-white;
}
</style>
