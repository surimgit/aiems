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
import type { ComputedRef } from 'vue'
import type { Recommendation } from '@/types/common'

export interface UseRecommendationFeature {
  recommendations: ComputedRef<Recommendation[]>
  highPriorityRecommendations: ComputedRef<Recommendation[]>
  isLoading: ComputedRef<boolean>
  fetchRecommendations: (siteId?: string) => Promise<void>
}

export const useRecommendationFeature = (): UseRecommendationFeature => {
  const aiStore = useAiStore()
  
  const recommendations = computed(() => [...aiStore.recommendations].sort((a, b) => {
    const priorityOrder = { high: 0, medium: 1, low: 2 }
    return priorityOrder[a.priority] - priorityOrder[b.priority]
  }))
  const highPriorityRecommendations = computed(() => aiStore.recommendations.filter((r) => r.priority === 'high'))
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
