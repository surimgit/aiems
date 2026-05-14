/**
 * AI API Client (조회/요청)
 * - 프런트 예측 그래프는 저장된 최신 24시간 예측만 조회:
 *   GET /api/ai/forecast/latest?site_id={siteId}
 *
 * - 브라우저에서 DB row 생성/모델 실행 트리거 API 직접 호출 금지
 *
 * - 미구현/미존재 API:
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

// 상대경로 사용: 로컬(vite proxy) / 배포(nginx) 모두 /api/ai/... 로 라우팅됨
// localhost:5004 직접 호출 금지 — 브라우저에서 localhost는 사용자 PC를 의미함
const AI_REQUEST_TIMEOUT_MS = 10000

const aiHttpClient = axios.create({
  baseURL: '',
  timeout: AI_REQUEST_TIMEOUT_MS,
  headers: {
    'Content-Type': 'application/json'
  }
})

interface ForecastPointResponse {
  site_id?: string
  forecast_run_id?: string
  horizon_index?: number
  target_time: string
  confidence?: number
  solar_confidence?: number
  predicted_solar_kw?: number
  predicted_generation_kw?: number
  predicted_load_kw?: number
  safe_predicted_load_kw?: number
  predicted_net_load_kw?: number
  solar_model_version?: string
  load_model_version?: string
  solar_backend?: string
  trigger_source?: string
}

interface ForecastLatestResponse {
  ok?: boolean
  site_id?: string
  forecast_run_id?: string
  rows?: number
  issued_at?: string
  forecasts?: ForecastPointResponse[]
  warnings?: string[]
}

interface ForecastSeries {
  generationForecast: ForecastData[]
  demandForecast: ForecastData[]
}

const DEFAULT_SITE_ID = 'PLANT-ALPHA'

const parseFiniteNumber = (value: unknown): number | null => {
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    return null
  }
  return value
}

const requestLatestForecast = async (siteId: string): Promise<ForecastLatestResponse> => {
  const response = await aiHttpClient.get<ForecastLatestResponse>('/api/ai/forecast/latest', {
    params: { site_id: siteId }
  })
  return response.data
}

const toForecastData = (
  points: ForecastPointResponse[],
  type: ForecastData['type'],
  selectPredictedKw: (point: ForecastPointResponse) => unknown,
  selectConfidence: (point: ForecastPointResponse) => unknown = (point) => point.confidence
): ForecastData[] => {
  const forecastData: ForecastData[] = []

  for (const point of points) {
    const predictedKw = parseFiniteNumber(selectPredictedKw(point))
    if (predictedKw === null) {
      continue
    }

    const confidence = parseFiniteNumber(selectConfidence(point))
    forecastData.push({
      timestamp: point.target_time,
      type,
      predicted_kw: predictedKw,
      ...(confidence === null ? {} : { confidence })
    })
  }

  return forecastData.sort((a, b) => {
    return new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
  })
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

export const getForecastSeries = async (siteId: string = DEFAULT_SITE_ID): Promise<ForecastSeries> => {
  return withAiFallback(async () => {
    const response = await requestLatestForecast(siteId)
    const points = response.forecasts ?? []

    return {
      generationForecast: toForecastData(
        points,
        'generation',
        (point) => point.predicted_solar_kw ?? point.predicted_generation_kw,
        (point) => point.solar_confidence ?? point.confidence
      ),
      demandForecast: toForecastData(
        points,
        'demand',
        (point) => point.safe_predicted_load_kw ?? point.predicted_load_kw
      )
    }
  }, { generationForecast: [], demandForecast: [] })
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
  getForecastSeries,
  getRecommendations,
  getAiModelStatus,
  requestInference,
}
