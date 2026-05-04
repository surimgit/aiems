/**
 * 알람 (Alarm) 피처
 * 
 * Responsibility:
 * - 알람 목록 데이터 제공
 * - 필터링, 정렬
 */

import { computed } from 'vue'
import { DEFAULT_SITE_ID } from '@/app/config'
import { useAlarmStore } from '@/stores/alarm/alarm.store'
import type { AlarmData } from '@/types/common'
import type { ComputedRef } from 'vue'

export interface UseAlarmFeature {
  alarms: ComputedRef<AlarmData[]>
  activeAlarms: ComputedRef<AlarmData[]>
  criticalAlarms: ComputedRef<AlarmData[]>
  hasActiveAlarm: ComputedRef<boolean>
  criticalAlarmCount: ComputedRef<number>
  isLoading: ComputedRef<boolean>
  fetchAlarms: () => Promise<void>
  acknowledgeAlarm: (alarmId: string) => Promise<void>
}

export const useAlarmFeature = (): UseAlarmFeature => {
  const alarmStore = useAlarmStore()
  
  const alarms = computed(() => alarmStore.alarms)
  const activeAlarms = computed(() => alarmStore.activeAlarms)
  const criticalAlarms = computed(() => alarmStore.criticalAlarms)
  const hasActiveAlarm = computed(() => alarmStore.hasActiveAlarm)
  const criticalAlarmCount = computed(() => alarmStore.criticalAlarmCount)
  const isLoading = computed(() => alarmStore.loading)
  
  const fetchAlarms = async () => {
    alarmStore.setSiteId(DEFAULT_SITE_ID)
    await alarmStore.fetchAlarms(DEFAULT_SITE_ID)
  }
  
  const acknowledgeAlarm = async (alarmId: string) => {
    await alarmStore.acknowledgeAlarm(alarmId)
  }
  
  return {
    alarms,
    activeAlarms,
    criticalAlarms,
    hasActiveAlarm,
    criticalAlarmCount,
    isLoading,
    fetchAlarms,
    acknowledgeAlarm
  }
}

export default useAlarmFeature
