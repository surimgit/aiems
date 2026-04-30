/**
 * 권장 조치 (Recommendation) 피처
 * 
 * Responsibility:
 * - AI 권장 조치 데이터 제공
 * - 우선순위 정렬
 */

import { computed } from 'vue'
import { DEFAULT_SITE_ID } from '@/app/config'
import { useAiStore } from '@/stores/ai/ai.store'

export interface UseRecommendationFeature {
  recommendations: ReturnType<typeof useAiStore>['sortedRecommendations']
  highPriorityRecommendations: ReturnType<typeof useAiStore>['highPriorityRecommendations']
  isLoading: boolean
}

export const useRecommendationFeature = (): UseRecommendationFeature => {
  const aiStore = useAiStore()
  
  const recommendations = computed(() => aiStore.sortedRecommendations)
  const highPriorityRecommendations = computed(() => aiStore.highPriorityRecommendations)
  const isLoading = computed(() => aiStore.loading)
  
  const fetchRecommendations = async (siteId: string = DEFAULT_SITE_ID) => {
    aiStore.setSiteId(siteId)
    await aiStore.fetchRecommendations(siteId)
  }
  
  return {
    recommendations,
    highPriorityRecommendations,
    isLoading,
    fetchRecommendations
  }
}

export default useRecommendationFeature
