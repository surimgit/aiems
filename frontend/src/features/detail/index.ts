/**
 * 상세 (Detail) 피처
 * 
 * Responsibility:
 * - ESS 상세 데이터 제공
 * - 개별 ESS 상태, 성능 등
 */

import { computed } from 'vue'
import { useDashboardStore } from '@/stores/dashboard/dashboard.store'
import type { ComputedRef } from 'vue'
import type { ESSStatus } from '@/types/common'

export interface UseDetailFeature {
  essList: ComputedRef<ESSStatus[]>
  selectedEssId: ComputedRef<string | null>
  selectedEss: ComputedRef<ESSStatus | null>
  isLoading: ComputedRef<boolean>
  selectEss: (essId: string) => void
}

export const useDetailFeature = (): UseDetailFeature => {
  const dashboardStore = useDashboardStore()
  
  const essList = computed(() => dashboardStore.essList)
  const isLoading = computed(() => dashboardStore.loading)
  
  const selectedEssId = computed(() => dashboardStore.selectedEssId)
  const selectedEss = computed(() => dashboardStore.selectedEss)
  
  const selectEss = (essId: string) => {
    dashboardStore.selectEss(essId)
  }
  
  return {
    essList,
    selectedEssId,
    selectedEss,
    isLoading,
    selectEss
  }
}

export default useDetailFeature
