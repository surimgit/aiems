/**
 * AI API Client (조회/요청)
 * - ProjectDocs/11-api/ai-api.md 기준
 */

import { http } from './http'
import type {
  ForecastContract,
  ForecastData,
  InferenceAcceptedResponse,
  InferenceRequest,
  InferenceResult,
  Recommendation,
  SiteLatestAi
} from '@/types/common'

const pickForecastSeries = (
  forecasts: ForecastContract[] | undefined,
  target: 'generation_kw' | 'load_kw'
): ForecastData[] => {
  if (!forecasts || forecasts.length === 0) {
    return []
  }

  const collected: ForecastData[] = []
  for (const forecast of forecasts) {
    for (const point of forecast.series) {
      const value = point[target]
      if (typeof value === 'number') {
        collected.push({
          timestamp: point.timestamp,
          type: target === 'generation_kw' ? 'generation' : 'demand',
          predicted_kw: value,
          confidence: forecast.confidence
        })
      }
    }
  }

  return collected
}

export const createInferenceRequest = async (
  request: InferenceRequest
): Promise<InferenceAcceptedResponse> => {
  return http.post<InferenceAcceptedResponse>('/api/ai/inference-requests', request)
}

export const getInferenceResult = async (inferenceId: string): Promise<InferenceResult> => {
  return http.get<InferenceResult>(`/api/ai/inference-results/${inferenceId}`)
}

export const getForecastById = async (forecastId: string): Promise<ForecastContract> => {
  return http.get<ForecastContract>(`/api/ai/forecasts/${forecastId}`)
}

export const getRecommendationById = async (recommendationId: string): Promise<Recommendation> => {
  return http.get<Recommendation>(`/api/ai/recommendations/${recommendationId}`)
}

export const getLatestAiBySite = async (siteId: string): Promise<SiteLatestAi> => {
  return http.get<SiteLatestAi>(`/api/plants/${siteId}/ai/latest`)
}

export const getGenerationForecast = async (siteId: string): Promise<ForecastData[]> => {
  const latest = await getLatestAiBySite(siteId)
  return pickForecastSeries(latest.forecasts, 'generation_kw')
}

export const getDemandForecast = async (siteId: string): Promise<ForecastData[]> => {
  const latest = await getLatestAiBySite(siteId)
  return pickForecastSeries(latest.forecasts, 'load_kw')
}

export const getRecommendations = async (siteId: string): Promise<Recommendation[]> => {
  const latest = await getLatestAiBySite(siteId)
  return latest.recommendations ?? []
}

export const requestInference = async (
  request: InferenceRequest
): Promise<InferenceAcceptedResponse> => {
  return createInferenceRequest(request)
}

export const getAiModelStatus = async (siteId: string): Promise<InferenceResult | null> => {
  const latest = await getLatestAiBySite(siteId)
  return latest.inference ?? null
}

export default {
  createInferenceRequest,
  getInferenceResult,
  getForecastById,
  getRecommendationById,
  getLatestAiBySite,
  getGenerationForecast,
  getDemandForecast,
  getRecommendations,
  requestInference,
  getAiModelStatus
}
