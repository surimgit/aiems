import { ref, type Ref } from 'vue'
import { DEFAULT_SITE_ID } from '@/app/config'
import { useForecastFeature } from '@/features/forecast'
import { useAlarmStore } from '@/stores/alarm/alarm.store'
import { useControlStore } from '@/stores/control/control.store'
import { useDashboardStore } from '@/stores/dashboard/dashboard.store'

const POLLING_INTERVAL_MS = 1_000
const TOPOLOGY_REFRESH_TICKS = 10
const ALARM_REFRESH_TICKS = 5
const FORECAST_REFRESH_TICKS = 30
const COMMAND_REFRESH_TICKS = 5

export interface UseOverviewPolling {
  isRunning: Ref<boolean>
  start: () => void
  stop: () => void
}

export const useOverviewPolling = (siteId: string = DEFAULT_SITE_ID): UseOverviewPolling => {
  const forecastFeature = useForecastFeature()
  const alarmStore = useAlarmStore()
  const controlStore = useControlStore()
  const dashboardStore = useDashboardStore()

  const isRunning = ref(false)
  const isTickInFlight = ref(false)
  const tickCount = ref(0)
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
      tickCount.value += 1
      const shouldRefreshTopology = tickCount.value % TOPOLOGY_REFRESH_TICKS === 0
      const shouldRefreshAlarms = tickCount.value % ALARM_REFRESH_TICKS === 0
      const shouldRefreshForecasts = tickCount.value % FORECAST_REFRESH_TICKS === 0
      const shouldRefreshCommands = tickCount.value % COMMAND_REFRESH_TICKS === 0

      await Promise.allSettled([
        dashboardStore.fetchPowerSummary(siteId),
        dashboardStore.fetchResources(siteId),
        ...(shouldRefreshTopology ? [dashboardStore.fetchTopology(siteId)] : []),
        ...(shouldRefreshForecasts ? [forecastFeature.fetchForecasts(siteId)] : []),
        ...(shouldRefreshAlarms ? [alarmStore.fetchAlarms(siteId)] : []),
        ...(shouldRefreshCommands ? [controlStore.fetchCommandHistory()] : [])
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
    dashboardStore.setSiteId(siteId)

    isRunning.value = true
    tickCount.value = 0
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
