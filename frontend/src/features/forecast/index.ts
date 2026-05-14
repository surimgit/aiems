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
import type { ComputedRef } from 'vue'
import type { ForecastData } from '@/types/common'

export interface UseForecastFeature {
  generationForecast: ComputedRef<ForecastData[]>
  demandForecast: ComputedRef<ForecastData[]>
  isLoading: ComputedRef<boolean>
  fetchForecasts: (siteId?: string) => Promise<void>
}

export const useForecastFeature = (): UseForecastFeature => {
  const aiStore = useAiStore()
  
  const generationForecast = computed(() => aiStore.generationForecast)
  const demandForecast = computed(() => aiStore.demandForecast)
  const isLoading = computed(() => aiStore.loading)
  
  const fetchForecasts = async (siteId: string = DEFAULT_SITE_ID) => {
    aiStore.setSiteId(siteId)
    await aiStore.fetchForecasts(siteId)
  }
  
  return {
    generationForecast,
    demandForecast,
    isLoading,
    fetchForecasts
  }
}

export default useForecastFeature
