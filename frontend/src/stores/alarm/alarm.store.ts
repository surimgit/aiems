/**
 * 알람 스토어
 * 
 * Responsibility:
 * - 알람 상태 관리
 * - 비상 우선 상태 노출
 * - 전역 알람 스트립 데이터 제공
 */

import { defineStore } from 'pinia'
import { DEFAULT_OPERATOR_ID, DEFAULT_SITE_ID } from '@/app/config'
import type { AlarmData } from '@/types/common'
import { acknowledgeAlarmById, getAlarmList } from '@/api/dashboard.client'

const normalizeAlarmList = (payload: unknown): AlarmData[] => {
  if (Array.isArray(payload)) {
    return payload as AlarmData[]
  }

  if (payload && typeof payload === 'object') {
    const maybeItems = (payload as { items?: unknown }).items
    if (Array.isArray(maybeItems)) {
      return maybeItems as AlarmData[]
    }

    const maybeData = (payload as { data?: unknown }).data
    if (Array.isArray(maybeData)) {
      return maybeData as AlarmData[]
    }
  }

  return []
}

interface AlarmState {
  siteId: string
  alarms: AlarmData[]
  loading: boolean
  error: string | null
  filter: {
    level?: 'info' | 'warning' | 'critical'
    acknowledged?: boolean
  }
}

interface AlarmGetters {
  activeAlarms: AlarmData[]
  criticalAlarms: AlarmData[]
  unacknowledgedCount: number
  hasActiveAlarm: boolean
  criticalAlarmCount: number
}

interface AlarmActions {
  setSiteId(siteId: string): void
  fetchAlarms(siteId?: string): Promise<void>
  acknowledgeAlarm(alarmId: string): Promise<void>
  setFilter(filter: AlarmState['filter']): void
  clearAll(): void
}

export const useAlarmStore = defineStore(
  'alarm',
  {
    state: (): AlarmState => ({
      siteId: DEFAULT_SITE_ID,
      alarms: [],
      loading: false,
      error: null,
      filter: {}
    }),
    
    getters: {
      activeAlarms(): AlarmData[] {
        if (!Array.isArray(this.alarms)) return []
        const unacked = this.alarms.filter((alarm) => !alarm.acknowledged)
        const sorted = [...unacked].sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())
        const bySignature = new Map<string, AlarmData>()
        for (const alarm of sorted) {
          const key = `${alarm.level}|${alarm.code}|${alarm.message}`
          if (!bySignature.has(key)) bySignature.set(key, alarm)
        }
        return Array.from(bySignature.values())
      },

      criticalAlarms(): AlarmData[] {
        return this.activeAlarms.filter((alarm) => alarm.level === 'critical')
      },

      unacknowledgedCount(): number {
        return this.activeAlarms.length
      },
      
      hasActiveAlarm(): boolean {
        return this.activeAlarms.length > 0
      },
      
      criticalAlarmCount(): number {
        return this.criticalAlarms.length
      }
    },
    
    actions: {
      setSiteId(siteId: string): void {
        this.siteId = siteId
      },

      async fetchAlarms(siteId?: string): Promise<void> {
        this.loading = true
        this.error = null
        
        try {
          const alarms = await getAlarmList(siteId ?? this.siteId)
          this.alarms = normalizeAlarmList(alarms)
        } catch (error) {
          this.error = (error as Error).message
          console.error('[AlarmStore] Fetch error:', error)
        } finally {
          this.loading = false
        }
      },
      
      async acknowledgeAlarm(alarmId: string): Promise<void> {
        this.error = null
        const alarm = this.alarms.find((a) => a.alarm_id === alarmId)
        const previous = alarm?.acknowledged

        if (alarm) {
          alarm.acknowledged = true
        }

        try {
          await acknowledgeAlarmById(this.siteId, alarmId, DEFAULT_OPERATOR_ID)
        } catch (error) {
          if (alarm) {
            alarm.acknowledged = previous
          }
          this.error = (error as Error).message
          throw error
        }
      },
      
      setFilter(filter: AlarmState['filter']): void {
        this.filter = { ...this.filter, ...filter }
      },
      
      clearAll(): void {
        this.alarms = []
        this.error = null
      }
    }
  }
)

export default useAlarmStore
