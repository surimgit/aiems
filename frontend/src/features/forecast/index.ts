/**
 * 예측 (Forecast) 피처
 * 
 * Responsibility:
 * - 발전량/수요 예측 데이터 제공
 * - AI 예측 결과 시각화용 데이터
 */

import { computed } from 'vue'
import { DEFAULT_SITE_ID } from '@/app/config'
import { useAiStore } from '@/stores/ai/ai.store'

export interface UseForecastFeature {
  generationForecast: ReturnType<typeof useAiStore>['generationForecast']
  demandForecast: ReturnType<typeof useAiStore>['demandForecast']
  isLoading: boolean
}

export const useForecastFeature = (): UseForecastFeature => {
  const aiStore = useAiStore()
  
  const generationForecast = computed(() => aiStore.generationForecast)
  const demandForecast = computed(() => aiStore.demandForecast)
  const isLoading = computed(() => aiStore.loading)
  
  const fetchForecasts = async (siteId: string = DEFAULT_SITE_ID) => {
    aiStore.setSiteId(siteId)
    await Promise.all([
      aiStore.fetchGenerationForecast(siteId),
      aiStore.fetchDemandForecast(siteId)
    ])
  }
  
  return {
    generationForecast,
    demandForecast,
    isLoading,
    fetchForecasts
  }
}

export default useForecastFeature
