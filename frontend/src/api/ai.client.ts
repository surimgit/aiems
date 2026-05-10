/**
 * AI API Client (조회/요청)
 * - ProjectDocs/11-api/ai-api.md 기준
 */

import { http } from './http'
import axios from 'axios'
import type {
  ForecastContract,
  ForecastData,
  InferenceAcceptedResponse,
  InferenceRequest,
  InferenceResult,
  Recommendation,
  SiteLatestAi
} from '@/types/common'
import type { ApiError } from '@/types/api'

const LATEST_AI_CACHE_TTL_MS = 1500
const latestAiCache = new Map<string, { fetchedAt: number; data: SiteLatestAi }>()
const latestAiInFlight = new Map<string, Promise<SiteLatestAi>>()

const isFeatureUnavailableError = (error: unknown): boolean => {
  if (!axios.isAxiosError(error)) {
    return false
  }

  const status = error.response?.status
  const payload = error.response?.data as ApiError | undefined
  if (status === 404 || status === 503 || payload?.error_code === 'FEATURE_UNAVAILABLE') return true
  if (!error.response && (error.code === 'ECONNABORTED' || error.code === 'ECONNRESET' || error.code === 'ERR_NETWORK')) {
    return true
  }
  return false
}

const withAiFallback = async <T>(runner: () => Promise<T>, fallback: T): Promise<T> => {
  try {
    return await runner()
  } catch (error) {
    if (isFeatureUnavailableError(error)) {
      return fallback
    }
    throw error
  }
}

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
  const key = siteId.toUpperCase()
  const cached = latestAiCache.get(key)
  const now = Date.now()
  if (cached && now - cached.fetchedAt < LATEST_AI_CACHE_TTL_MS) {
    return cached.data
  }

  const inFlight = latestAiInFlight.get(key)
  if (inFlight) return inFlight

  const request = http
    .get<SiteLatestAi>(`/api/plants/${siteId}/ai/latest`)
    .then((data) => {
      latestAiCache.set(key, { fetchedAt: Date.now(), data })
      return data
    })
    .finally(() => {
      latestAiInFlight.delete(key)
    })

  latestAiInFlight.set(key, request)
  return request
}

export const getGenerationForecast = async (siteId: string): Promise<ForecastData[]> => {
  return withAiFallback(async () => {
    const latest = await getLatestAiBySite(siteId)
    return pickForecastSeries(latest.forecasts, 'generation_kw')
  }, [])
}

export const getDemandForecast = async (siteId: string): Promise<ForecastData[]> => {
  return withAiFallback(async () => {
    const latest = await getLatestAiBySite(siteId)
    return pickForecastSeries(latest.forecasts, 'load_kw')
  }, [])
}

export const getRecommendations = async (siteId: string): Promise<Recommendation[]> => {
  return withAiFallback(async () => {
    const latest = await getLatestAiBySite(siteId)
    return latest.recommendations ?? []
  }, [])
}

export const requestInference = async (
  request: InferenceRequest
): Promise<InferenceAcceptedResponse> => {
  return createInferenceRequest(request)
}

export const getAiModelStatus = async (siteId: string): Promise<InferenceResult | null> => {
  return withAiFallback(async () => {
    const latest = await getLatestAiBySite(siteId)
    return latest.inference ?? null
  }, null)
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
