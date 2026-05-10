import { ref, type Ref } from 'vue'
import { DEFAULT_SITE_ID } from '@/app/config'
import { useForecastFeature } from '@/features/forecast'
import { useAlarmStore } from '@/stores/alarm/alarm.store'
import { useControlStore } from '@/stores/control/control.store'

const POLLING_INTERVAL_MS = 30_000

export interface UseOverviewPolling {
  isRunning: Ref<boolean>
  start: () => void
  stop: () => void
}

export const useOverviewPolling = (siteId: string = DEFAULT_SITE_ID): UseOverviewPolling => {
  const forecastFeature = useForecastFeature()
  const alarmStore = useAlarmStore()
  const controlStore = useControlStore()

  const isRunning = ref(false)
  const isTickInFlight = ref(false)
  let timerId: ReturnType<typeof setTimeout> | null = null

  const scheduleNextTick = () => {
    timerId = setTimeout(() => {
      void runTick()
    }, POLLING_INTERVAL_MS)
  }

  const runTick = async () => {
    if (!isRunning.value) return
    if (isTickInFlight.value) {
      scheduleNextTick()
      return
    }

    isTickInFlight.value = true
    try {
      await Promise.allSettled([
        forecastFeature.fetchForecasts(siteId),
        alarmStore.fetchAlarms(siteId),
        controlStore.fetchCommandHistory()
      ])
    } catch (error) {
      console.error('[OverviewPolling] Unexpected tick error:', error)
    } finally {
      isTickInFlight.value = false
      if (isRunning.value) {
        scheduleNextTick()
      }
    }
  }

  const start = () => {
    if (isRunning.value) return

    alarmStore.setSiteId(siteId)
    controlStore.setContext({ siteId })
    isRunning.value = true
    scheduleNextTick()
  }

  const stop = () => {
    isRunning.value = false
    if (timerId) {
      clearTimeout(timerId)
      timerId = null
    }
  }

  return {
    isRunning,
    start,
    stop
  }
}

export default useOverviewPolling
