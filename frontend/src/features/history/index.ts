/**
 * 이력 (History) 피처
 * 
 * Responsibility:
 * - 과거 데이터 조회
 * - 기간별 필터링
 */

import { computed } from 'vue'
import { useControlStore } from '@/stores/control/control.store'
import type { ComputedRef } from 'vue'

export interface HistoryRecord {
  timestamp: string
  type: 'power' | 'alarm' | 'control'
  data: Record<string, unknown>
}

export interface UseHistoryFeature {
  records: ComputedRef<HistoryRecord[]>
  isLoading: ComputedRef<boolean>
  fetchHistory: (startDate: string, endDate: string) => Promise<void>
}

export const useHistoryFeature = (): UseHistoryFeature => {
  const controlStore = useControlStore()
  const records = computed<HistoryRecord[]>(() =>
    controlStore.pendingCommands.map((command) => ({
      timestamp: command.created_at,
      type: 'control',
      data: {
        command_id: command.command_id,
        action: command.action,
        status: command.status,
        target_resource_id: command.target_resource_id
      }
    }))
  )

  const isLoading = computed(() => controlStore.loading)
  
  const fetchHistory = async (startDate: string, endDate: string) => {
    void startDate
    void endDate
    await controlStore.fetchCommandHistory()
  }
  
  return {
    records,
    isLoading,
    fetchHistory
  }
}

export default useHistoryFeature
