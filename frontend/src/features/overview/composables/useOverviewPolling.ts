import { ref, type Ref } from 'vue'
import { DEFAULT_SITE_ID } from '@/app/config'
import { socketioSource } from '@/realtime/socketioSource'
import { useAlarmStore } from '@/stores/alarm/alarm.store'
import { useDashboardStore } from '@/stores/dashboard/dashboard.store'

const METADATA_REFRESH_INTERVAL_MS = 1000
const TOPOLOGY_REFRESH_TICKS = 5
const ALARM_REFRESH_TICKS = 2

export interface UseOverviewPolling {
  isRunning: Ref<boolean>
  start: () => void
  stop: () => void
}

export const useOverviewPolling = (siteId: string = DEFAULT_SITE_ID): UseOverviewPolling => {
  const alarmStore = useAlarmStore()
  const dashboardStore = useDashboardStore()

  const isRunning = ref(false)
  const isTickInFlight = ref(false)
  const tickCount = ref(0)
  let timerId: ReturnType<typeof setTimeout> | null = null
  let unsubscribeState: (() => void) | null = null
  let unsubscribeError: (() => void) | null = null

  const scheduleNextTick = () => {
    timerId = setTimeout(() => {
      void runTick()
    }, METADATA_REFRESH_INTERVAL_MS)
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

      await Promise.allSettled([
        ...(shouldRefreshTopology ? [dashboardStore.fetchTopology(siteId)] : []),
        ...(shouldRefreshAlarms ? [alarmStore.fetchAlarms(siteId)] : [])
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
    dashboardStore.setSiteId(siteId)

    isRunning.value = true
    tickCount.value = 0
    unsubscribeState = socketioSource.subscribeState((event) => {
      dashboardStore.applyRealtimeStateUpdate(event)
    })
    unsubscribeError = socketioSource.subscribeError((error) => {
      console.error('[OverviewRealtime] Socket.IO error:', error)
    })
    socketioSource.connect(siteId)
    scheduleNextTick()
  }

  const stop = () => {
    isRunning.value = false
    unsubscribeState?.()
    unsubscribeState = null
    unsubscribeError?.()
    unsubscribeError = null
    socketioSource.disconnect()
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
