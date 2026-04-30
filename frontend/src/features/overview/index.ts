/**
 * 개요 (Overview) 피처
 * 
 * Responsibility:
 * - 대시보드 메인view의 데이터 제공
 * - 전력 요약, ESS 상태 등 조합
 * 
 * 사용 패턴:
 * ```vue
 * <script setup>
 * import { useOverviewFeature } from '@/features/overview'
 * const { powerSummary, essList, isLoading } = useOverviewFeature()
 * </script>
 * ```
 */

import { computed } from 'vue'
import { DEFAULT_SITE_ID } from '@/app/config'
import { useDashboardStore } from '@/stores/dashboard/dashboard.store'
import { useAlarmStore } from '@/stores/alarm/alarm.store'
import { interpretNetPower } from '@/domain/sign'
import { formatPower } from '@/domain/units'

export interface UseOverviewFeature {
  powerSummary: ReturnType<typeof useDashboardStore>['powerSummary']
  essList: ReturnType<typeof useDashboardStore>['essList']
  activeAlarms: ReturnType<typeof useAlarmStore>['activeAlarms']
  isLoading: boolean
  netPowerDisplay: string
  powerStatus: ReturnType<typeof interpretNetPower>
}

export const useOverviewFeature = (): UseOverviewFeature => {
  const dashboardStore = useDashboardStore()
  const alarmStore = useAlarmStore()

  const isLoading = computed(() => dashboardStore.loading)
  const powerSummary = computed(() => dashboardStore.powerSummary)
  const essList = computed(() => dashboardStore.essList)
  const activeAlarms = computed(() => alarmStore.activeAlarms)

  const netPowerDisplay = computed(() => {
    if (!powerSummary.value) return '--'
    return formatPower(powerSummary.value.net_power_kw)
  })

  const powerStatus = computed(() => {
    if (!powerSummary.value) return interpretNetPower(0)
    return interpretNetPower(powerSummary.value.net_power_kw)
  })

  const initialize = async () => {
    dashboardStore.setSiteId(DEFAULT_SITE_ID)
    alarmStore.setSiteId(DEFAULT_SITE_ID)

    await Promise.all([
      dashboardStore.fetchPowerSummary(DEFAULT_SITE_ID),
      dashboardStore.fetchEssList(DEFAULT_SITE_ID),
      alarmStore.fetchAlarms(DEFAULT_SITE_ID)
    ])
  }

  return {
    powerSummary,
    essList,
    activeAlarms,
    isLoading,
    netPowerDisplay,
    powerStatus,
    initialize
  }
}

export default useOverviewFeature
