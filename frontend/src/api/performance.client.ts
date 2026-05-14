/**
 * Performance API Client
 *
 * Frontend contract for DB-backed solar savings performance.
 * Backend owner: state-processor read API backed by TimescaleDB aggregates.
 */

import axios from 'axios'
import { DEFAULT_SITE_ID } from '@/app/config'
import { unwrapPayload, type ApiResponse } from '@/types/api'

export type SolarSavingsPeriod = 'today' | 'month'

export interface SolarSavingsPerformance {
  site_id: string
  period: SolarSavingsPeriod
  from: string
  to: string
  solar_generation_kwh: number
  avoided_grid_kwh: number
  savings_won: number
  avg_tariff_won_per_kwh: number
  self_use_ratio_pct: number
  tariff_basis?: string
  updated_at?: string
}

const PERFORMANCE_REQUEST_TIMEOUT_MS = 10000

const performanceHttpClient = axios.create({
  baseURL: '',
  timeout: PERFORMANCE_REQUEST_TIMEOUT_MS,
  headers: {
    'Content-Type': 'application/json'
  }
})

const withPerformanceFallback = async <T>(runner: () => Promise<T>, fallback: T): Promise<T> => {
  try {
    return await runner()
  } catch (error) {
    const status = axios.isAxiosError(error) ? error.response?.status : undefined
    if (status !== 404 && status !== 503 && status !== undefined) {
      console.warn('[Performance] 요청 실패 (fallback 반환):', error)
    }
    return fallback
  }
}

export const getSolarSavingsPerformance = async (
  siteId: string = DEFAULT_SITE_ID,
  period: SolarSavingsPeriod = 'month'
): Promise<SolarSavingsPerformance | null> => {
  return withPerformanceFallback(async () => {
    const response = await performanceHttpClient.get<ApiResponse<SolarSavingsPerformance>>(
      `/api/plants/${encodeURIComponent(siteId)}/performance/solar-savings`,
      { params: { period } }
    )
    return unwrapPayload(response.data)
  }, null)
}

export default {
  getSolarSavingsPerformance
}
