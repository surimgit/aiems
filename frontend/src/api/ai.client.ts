/**
 * AI API Client (조회/요청)
 * - 실제 AI 백엔드 존재 API만 사용:
 *   POST /api/ai/predict-live-satellite-capacity-factor
 *   POST /api/ai/forecast
 *
 * - 미구현/미존재 API 사용 금지:
 *   GET /api/plants/{siteId}/ai/latest (state-processor 503)
 *   POST /api/ai/inference-requests (AI 백엔드 없음)
 *   GET /api/ai/inference-results/{id} (AI 백엔드 없음)
 *   GET /api/ai/forecasts/{id} (AI 백엔드 없음)
 *   GET /api/ai/recommendations/{id} (AI 백엔드 없음)
 */

import axios from 'axios'
import type {
  ForecastData,
  InferenceAcceptedResponse,
  InferenceRequest,
  InferenceResult,
  Recommendation,
} from '@/types/common'

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
  site_id: string
  region: string
  latitude: number
  longitude: number
  timezone: string
  installed_capacity_kw: number
  base_load_kw: number
}

interface ForecastPointResponse {
  target_time: string
  predicted_load_kw?: number
  safe_predicted_load_kw?: number
}

interface ForecastResponse {
  forecasts?: ForecastPointResponse[]
}

const KST_TIMEZONE = 'Asia/Seoul'
const DEFAULT_REGION = '대전시'
const DEFAULT_SITE_ID = 'PLANT-ALPHA'
const DEFAULT_LATITUDE = 36.3504
const DEFAULT_LONGITUDE = 127.3845
const DEFAULT_INSTALLED_CAPACITY_KW = 100
const DEFAULT_FORECAST_SITE: ForecastSiteRequest = {
  site_id: DEFAULT_SITE_ID,
  region: DEFAULT_REGION,
  latitude: DEFAULT_LATITUDE,
  longitude: DEFAULT_LONGITUDE,
  timezone: KST_TIMEZONE,
  installed_capacity_kw: DEFAULT_INSTALLED_CAPACITY_KW,
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
    latitude: DEFAULT_LATITUDE,
    longitude: DEFAULT_LONGITUDE,
    horizon_hours: horizonHours,
    target_time: buildTargetTimeByHorizon(horizonHours),
    installed_capacity_kw: DEFAULT_INSTALLED_CAPACITY_KW
  })

  return response.data
}

const requestIntegratedForecast = async (): Promise<ForecastResponse> => {
  const response = await aiHttpClient.post<ForecastResponse>('/api/ai/forecast', {
    site_id: DEFAULT_SITE_ID,
    site: DEFAULT_FORECAST_SITE,
    start_time: buildForecastStartTime(),
    periods: 24,
    frequency_hours: 1
  })

  return response.data
}

// AI 서비스는 선택적 기능 — 어떤 에러도 fallback 으로 처리
const withAiFallback = async <T>(runner: () => Promise<T>, fallback: T): Promise<T> => {
  try {
    return await runner()
  } catch (error) {
    console.warn('[AI] 요청 실패 (fallback 반환):', error)
    return fallback
  }
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
      const predictedKw = parseFiniteNumber(point.safe_predicted_load_kw ?? point.predicted_load_kw)
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

// 미구현 API — 백엔드 구현 전까지 빈 배열 반환
export const getRecommendations = async (_siteId: string): Promise<Recommendation[]> => {
  return []
}

// 미구현 API — 백엔드 구현 전까지 null 반환
export const getAiModelStatus = async (_siteId: string): Promise<InferenceResult | null> => {
  return null
}

// 미구현 API — 백엔드 구현 전까지 stub
export const requestInference = async (
  _request: InferenceRequest
): Promise<InferenceAcceptedResponse> => {
  throw new Error('AI inference API is not yet implemented')
}

export default {
  getGenerationForecast,
  getDemandForecast,
  getRecommendations,
  getAiModelStatus,
  requestInference,
}
