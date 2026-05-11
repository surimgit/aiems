/**
 * AI API Client (조회/요청)
 * - ProjectDocs/11-api/ai-api.md 기준.
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

const AI_API_BASE_URL =
  import.meta.env.VITE_AI_API_BASE_URL ||
  import.meta.env.VITE_API_BASE_URL ||
  'http://localhost:5004'

// AI 전용 timeout: 빠른 fallback 유도 (로컬 503 즉시 반환, RunPod warm ~5s)
const AI_REQUEST_TIMEOUT_MS = Number(import.meta.env.VITE_AI_TIMEOUT) || 10000

const aiHttpClient = axios.create({
  baseURL: AI_API_BASE_URL,
  timeout: AI_REQUEST_TIMEOUT_MS,
  headers: {
    'Content-Type': 'application/json'
  }
})

interface LiveSatellitePrediction {
  predicted_generation_kw?: number
  model_version?: string
}

interface LiveSatelliteTarget {
  target_time?: string
}

interface LiveSatelliteResponse {
  prediction?: LiveSatellitePrediction
  target?: LiveSatelliteTarget
}

interface ForecastSiteRequest {
  latitude: number
  longitude: number
  timezone: string
  installed_capacity_kw: number
  base_load_kw: number
}

interface ForecastPointResponse {
  target_time: string
  predicted_load_kw?: number
}

interface ForecastResponse {
  forecasts?: ForecastPointResponse[]
}

const KST_TIMEZONE = 'Asia/Seoul'
const DEFAULT_REGION = '대전시'
const DEFAULT_INSTALLED_CAPACITY_KW = 100
const DEFAULT_FORECAST_SITE: ForecastSiteRequest = {
  latitude: 36.3504,
  longitude: 127.3845,
  timezone: KST_TIMEZONE,
  installed_capacity_kw: 100,
  base_load_kw: 650
}

const getBaseKstTime = (): Date => {
  const now = new Date()
  const asKst = new Date(now.toLocaleString('en-US', { timeZone: KST_TIMEZONE }))
  asKst.setMinutes(0, 0, 0)
  return asKst
}

const toKstIsoString = (date: Date): string => {
  const iso = date.toISOString()
  return `${iso.substring(0, 19)}+09:00`
}

const buildTargetTimeByHorizon = (horizonHours: number): string => {
  const target = getBaseKstTime()
  target.setHours(target.getHours() + horizonHours)
  return toKstIsoString(target)
}

const buildForecastStartTime = (): string => {
  return toKstIsoString(getBaseKstTime())
}

const parseFiniteNumber = (value: unknown): number | null => {
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    return null
  }
  return value
}

const toGenerationForecastData = (response: LiveSatelliteResponse): ForecastData | null => {
  const timestamp = response.target?.target_time
  const predictedKw = parseFiniteNumber(response.prediction?.predicted_generation_kw)

  if (!timestamp || predictedKw === null) {
    return null
  }

  return {
    timestamp,
    type: 'generation',
    predicted_kw: predictedKw
  }
}

const predictLiveSatelliteCapacityFactor = async (horizonHours: number): Promise<LiveSatelliteResponse> => {
  const response = await aiHttpClient.post<LiveSatelliteResponse>('/api/ai/predict-live-satellite-capacity-factor', {
    site_id: null,
    region: DEFAULT_REGION,
    horizon_hours: horizonHours,
    target_time: buildTargetTimeByHorizon(horizonHours),
    installed_capacity_kw: DEFAULT_INSTALLED_CAPACITY_KW
  })

  return response.data
}

const requestIntegratedForecast = async (): Promise<ForecastResponse> => {
  const response = await aiHttpClient.post<ForecastResponse>('/api/ai/forecast', {
    site: DEFAULT_FORECAST_SITE,
    start_time: buildForecastStartTime(),
    periods: 24,
    frequency_hours: 1
  })

  return response.data
}

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

// AI 서비스는 선택적 기능 — 어떤 에러도 fallback 으로 처리
// (RunPod 장애, 로컬 모델 미존재, timeout, 500 등 모두 포함)
const withAiFallback = async <T>(runner: () => Promise<T>, fallback: T): Promise<T> => {
  try {
    return await runner()
  } catch (error) {
    console.warn('[AI] 요청 실패 (fallback 반환):', error)
    return fallback
  }
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

// 동시 요청 수를 제한해서 AI 서비스/브라우저 연결 풀 과부하 방지
const MAX_CONCURRENT_HORIZON_REQUESTS = 4

export const getGenerationForecast = async (siteId: string): Promise<ForecastData[]> => {
  void siteId
  return withAiFallback(async () => {
    const horizonRequests = Array.from({ length: 24 }, (_, index) => index + 1)
    const results: ForecastData[] = []

    for (let i = 0; i < horizonRequests.length; i += MAX_CONCURRENT_HORIZON_REQUESTS) {
      const batch = horizonRequests.slice(i, i + MAX_CONCURRENT_HORIZON_REQUESTS)
      const responses = await Promise.all(batch.map((horizon) => predictLiveSatelliteCapacityFactor(horizon)))
      for (const response of responses) {
        const point = toGenerationForecastData(response)
        if (point !== null) {
          results.push(point)
        }
      }
    }

    return results.sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime())
  }, [])
}

export const getDemandForecast = async (siteId: string): Promise<ForecastData[]> => {
  void siteId
  return withAiFallback(async () => {
    const response = await requestIntegratedForecast()
    const points = response.forecasts ?? []

    const forecastData: ForecastData[] = []
    for (const point of points) {
      const predictedKw = parseFiniteNumber(point.predicted_load_kw)
      if (predictedKw === null) {
        continue
      }

      forecastData.push({
        timestamp: point.target_time,
        type: 'demand',
        predicted_kw: predictedKw
      })
    }

    return forecastData.sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime())
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
