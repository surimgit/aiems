/**
 * 상세 (Detail) 피처
 * 
 * Responsibility:
 * - ESS 상세 데이터 제공
 * - 개별 ESS 상태, 성능 등
 */

import { computed } from 'vue'
import { useDashboardStore } from '@/stores/dashboard/dashboard.store'

export interface UseDetailFeature {
  essList: ReturnType<typeof useDashboardStore>['essList']
  selectedEssId: string | null
  selectedEss: ReturnType<typeof useDashboardStore>['essList'][number] | null
  isLoading: boolean
}

export const useDetailFeature = (): UseDetailFeature => {
  const dashboardStore = useDashboardStore()
  
  const essList = computed(() => dashboardStore.essList)
  const isLoading = computed(() => dashboardStore.loading)
  
  const selectedEssId = computed(() => null)
  const selectedEss = computed(() => null)
  
  const selectEss = (essId: string) => {
    // TODO: ESS 선택 로직
    console.log('Select ESS:', essId)
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