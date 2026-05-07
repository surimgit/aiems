/**
 * API type contracts aligned to ProjectDocs
 */

/**
 * Error Response 표준
 * - ProjectDocs/07-appendix/error-response-standard.md
 */
export interface ApiError {
  error_code: string
  message: string
  trace_id?: string
  details?: Record<string, unknown>
}

/**
 * Legacy + envelope compatibility while backend evolves.
 */
export interface LegacyApiEnvelope<T = unknown> {
  success: boolean
  data?: T
  error?: ApiError
  message?: string
}

/**
 * Unified API result type.
 * - success: direct payload T
 * - legacy: { success, data }
 */
export type ApiResponse<T> = T | LegacyApiEnvelope<T>

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  page_size: number
  has_next: boolean
  has_prev: boolean
}

export const isLegacyEnvelope = <T>(payload: ApiResponse<T>): payload is LegacyApiEnvelope<T> => {
  return typeof payload === 'object' && payload !== null && 'success' in payload
}

export const unwrapPayload = <T>(payload: ApiResponse<T>): T => {
  if (isLegacyEnvelope(payload)) {
    if (!payload.success) {
      throw new Error(payload.error?.message ?? payload.message ?? 'API request failed')
    }
    if (payload.data === undefined) {
      throw new Error('API envelope has no data payload')
    }
    return payload.data
  }
  return payload
}
