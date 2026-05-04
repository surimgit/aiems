/**
 * 제어 스토어
 * - ProjectDocs Control API 계약 기반
 */

import { defineStore } from 'pinia'
import { DEFAULT_EDGE_ID, DEFAULT_OPERATOR_ID, DEFAULT_SITE_ID } from '@/app/config'
import type {
  CommandAction,
  ControlResult,
  OperatorCommandRequest
} from '@/types/common'
import {
  approveRecommendation,
  getCommandStatus,
  listCommands,
  rejectRecommendation,
  submitOperatorCommand
} from '@/api/control.client'

interface PendingCommand {
  command_id: string
  status: ControlResult['status']
  target_resource_id: string
  action: CommandAction
  created_at: string
}

interface ControlState {
  siteId: string
  edgeId: string
  operatorId: string
  pendingCommands: PendingCommand[]
  loading: boolean
  error: string | null
}

interface ControlGetters {
  pendingCount: number
  hasPendingCommand: boolean
}

interface ControlActions {
  setContext(payload: { siteId?: string; edgeId?: string; operatorId?: string }): void
  submitCommand(payload: Omit<OperatorCommandRequest, 'requested_by'> & { requested_by?: string }): Promise<ControlResult>
  approveAiRecommendation(recommendationId: string, reason?: string): Promise<ControlResult>
  rejectAiRecommendation(recommendationId: string, reason?: string): Promise<ControlResult>
  fetchCommandStatus(commandId: string): Promise<ControlResult>
  fetchCommandHistory(): Promise<ControlResult[]>
}

export const useControlStore = defineStore('control', {
  state: (): ControlState => ({
    siteId: DEFAULT_SITE_ID,
    edgeId: DEFAULT_EDGE_ID,
    operatorId: DEFAULT_OPERATOR_ID,
    pendingCommands: [],
    loading: false,
    error: null
  }),

  getters: {
    pendingCount(): number {
      return this.pendingCommands.filter((cmd) => cmd.status === 'ACCEPTED' || cmd.status === 'RUNNING').length
    },

    hasPendingCommand(): boolean {
      return this.pendingCount > 0
    }
  },

  actions: {
    setContext(payload: { siteId?: string; edgeId?: string; operatorId?: string }): void {
      if (payload.siteId) this.siteId = payload.siteId
      if (payload.edgeId) this.edgeId = payload.edgeId
      if (payload.operatorId) this.operatorId = payload.operatorId
    },

    async submitCommand(
      payload: Omit<OperatorCommandRequest, 'requested_by'> & { requested_by?: string }
    ): Promise<ControlResult> {
      this.loading = true
      this.error = null

      try {
        const result = await submitOperatorCommand({
          ...payload,
          requested_by: payload.requested_by ?? this.operatorId
        })

        this.pendingCommands.unshift({
          command_id: result.command_id,
          status: result.status,
          target_resource_id: result.target_resource_id,
          action: result.action,
          created_at: result.created_at
        })

        return result
      } catch (error) {
        this.error = (error as Error).message
        throw error
      } finally {
        this.loading = false
      }
    },

    async approveAiRecommendation(recommendationId: string, reason?: string): Promise<ControlResult> {
      this.loading = true
      this.error = null

      try {
        return await approveRecommendation(recommendationId, {
          requested_by: this.operatorId,
          reason
        })
      } catch (error) {
        this.error = (error as Error).message
        throw error
      } finally {
        this.loading = false
      }
    },

    async rejectAiRecommendation(recommendationId: string, reason?: string): Promise<ControlResult> {
      this.loading = true
      this.error = null

      try {
        return await rejectRecommendation(recommendationId, {
          requested_by: this.operatorId,
          reason
        })
      } catch (error) {
        this.error = (error as Error).message
        throw error
      } finally {
        this.loading = false
      }
    },

    async fetchCommandStatus(commandId: string): Promise<ControlResult> {
      this.loading = true
      this.error = null

      try {
        const result = await getCommandStatus(commandId)
        const index = this.pendingCommands.findIndex((item) => item.command_id === result.command_id)
        if (index >= 0) {
          this.pendingCommands[index] = {
            command_id: result.command_id,
            status: result.status,
            target_resource_id: result.target_resource_id,
            action: result.action,
            created_at: result.created_at
          }
        }
        return result
      } catch (error) {
        this.error = (error as Error).message
        throw error
      } finally {
        this.loading = false
      }
    },

    async fetchCommandHistory(): Promise<ControlResult[]> {
      this.loading = true
      this.error = null

      try {
        return await listCommands({ site_id: this.siteId })
      } catch (error) {
        this.error = (error as Error).message
        throw error
      } finally {
        this.loading = false
      }
    }
  }
})

export default useControlStore
