/**
 * AI 스토어
 * 
 * Responsibility:
 * - AI 예측 데이터 관리
 * - 권장 조치 조회
 * - AI 추론 요청 관리
 */

import { defineStore } from 'pinia'
import { DEFAULT_SITE_ID } from '@/app/config'
import type {
  ForecastData,
  InferenceAcceptedResponse,
  InferenceRequest,
  InferenceResult,
  Recommendation
} from '@/types/common'
import { 
  getGenerationForecast, 
  getDemandForecast, 
  getRecommendations, 
  requestInference,
  getAiModelStatus 
} from '@/api/ai.client'

interface AiState {
  siteId: string
  generationForecast: ForecastData[]
  demandForecast: ForecastData[]
  recommendations: Recommendation[]
  modelStatus: InferenceResult | null
  loading: boolean
  error: string | null
}

interface AiGetters {
  latestGenerationForecast: ForecastData | null
  latestDemandForecast: ForecastData | null
  sortedRecommendations: Recommendation[]
  highPriorityRecommendations: Recommendation[]
}

interface AiActions {
  setSiteId(siteId: string): void
  fetchGenerationForecast(siteId?: string): Promise<void>
  fetchDemandForecast(siteId?: string): Promise<void>
  fetchRecommendations(siteId?: string): Promise<void>
  fetchModelStatus(): Promise<void>
  requestAiInference(request: InferenceRequest): Promise<InferenceAcceptedResponse>
}

export const useAiStore = defineStore<'ai', AiState, AiGetters, AiActions>(
  'ai',
  {
    state: (): AiState => ({
      siteId: DEFAULT_SITE_ID,
      generationForecast: [],
      demandForecast: [],
      recommendations: [],
      modelStatus: null,
      loading: false,
      error: null
    }),
    
    getters: {
      latestGenerationForecast(): ForecastData | null {
        return this.generationForecast[0] ?? null
      },
      
      latestDemandForecast(): ForecastData | null {
        return this.demandForecast[0] ?? null
      },
      
      sortedRecommendations(): Recommendation[] {
        return [...this.recommendations].sort((a, b) => {
          const priorityOrder = { high: 0, medium: 1, low: 2 }
          return priorityOrder[a.priority] - priorityOrder[b.priority]
        })
      },
      
      highPriorityRecommendations(): Recommendation[] {
        return this.recommendations.filter((r) => r.priority === 'high')
      }
    },
    
    actions: {
      setSiteId(siteId: string): void {
        this.siteId = siteId
      },

      async fetchGenerationForecast(siteId?: string): Promise<void> {
        this.loading = true
        this.error = null
        
        try {
          this.generationForecast = await getGenerationForecast(siteId ?? this.siteId)
        } catch (error) {
          this.error = (error as Error).message
          console.error('[AiStore] Fetch generation forecast error:', error)
        } finally {
          this.loading = false
        }
      },
      
      async fetchDemandForecast(siteId?: string): Promise<void> {
        this.loading = true
        this.error = null
        
        try {
          this.demandForecast = await getDemandForecast(siteId ?? this.siteId)
        } catch (error) {
          this.error = (error as Error).message
          console.error('[AiStore] Fetch demand forecast error:', error)
        } finally {
          this.loading = false
        }
      },
      
      async fetchRecommendations(siteId?: string): Promise<void> {
        this.loading = true
        this.error = null
        
        try {
          this.recommendations = await getRecommendations(siteId ?? this.siteId)
        } catch (error) {
          this.error = (error as Error).message
          console.error('[AiStore] Fetch recommendations error:', error)
        } finally {
          this.loading = false
        }
      },
      
      async fetchModelStatus(): Promise<void> {
        this.loading = true
        this.error = null
        
        try {
          this.modelStatus = await getAiModelStatus(this.siteId)
        } catch (error) {
          this.error = (error as Error).message
          console.error('[AiStore] Fetch model status error:', error)
        } finally {
          this.loading = false
        }
      },
      
      async requestAiInference(request: InferenceRequest): Promise<InferenceAcceptedResponse> {
        this.loading = true
        this.error = null
        
        try {
          return await requestInference(request)
        } catch (error) {
          this.error = (error as Error).message
          throw error
        } finally {
          this.loading = false
        }
      }
    }
  }
)

export default useAiStore
