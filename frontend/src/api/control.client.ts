/**
 * Control API Client (제어/추적)
 * - ProjectDocs/11-api/control-api.md 기준
 */

import { http } from './http'
import type { ControlResult, OperatorCommandRequest } from '@/types/common'

export interface RecommendationDecisionRequest {
  requested_by: string
  reason?: string
}

export interface ListCommandsQuery {
  site_id?: string
  device_id?: string
  issued_by?: string
  page?: number
  page_size?: number
}

const queryString = (query: ListCommandsQuery): string => {
  const params = new URLSearchParams()
  if (query.site_id) params.set('site_id', query.site_id)
  if (query.device_id) params.set('device_id', query.device_id)
  if (query.issued_by) params.set('issued_by', query.issued_by)
  if (query.page !== undefined) params.set('page', String(query.page))
  if (query.page_size !== undefined) params.set('page_size', String(query.page_size))
  const encoded = params.toString()
  return encoded.length > 0 ? `?${encoded}` : ''
}

export const submitOperatorCommand = async (
  payload: OperatorCommandRequest
): Promise<ControlResult> => {
  return http.post<ControlResult>('/api/control/operator-commands', payload)
}

export const approveRecommendation = async (
  recommendationId: string,
  payload: RecommendationDecisionRequest
): Promise<ControlResult> => {
  return http.post<ControlResult>(
    `/api/control/recommendations/${recommendationId}/approve`,
    payload
  )
}

export const rejectRecommendation = async (
  recommendationId: string,
  payload: RecommendationDecisionRequest
): Promise<ControlResult> => {
  return http.post<ControlResult>(
    `/api/control/recommendations/${recommendationId}/reject`,
    payload
  )
}

export const getCommandStatus = async (commandId: string): Promise<ControlResult> => {
  return http.get<ControlResult>(`/api/control/commands/${commandId}`)
}

export const listCommands = async (query: ListCommandsQuery = {}): Promise<ControlResult[]> => {
  return http.get<ControlResult[]>(`/api/control/commands${queryString(query)}`)
}

export default {
  submitOperatorCommand,
  approveRecommendation,
  rejectRecommendation,
  getCommandStatus,
  listCommands
}
