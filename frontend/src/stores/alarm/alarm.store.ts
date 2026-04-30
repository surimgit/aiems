/**
 * 알람 스토어
 * 
 * Responsibility:
 * - 알람 상태 관리
 * - 비상 우선 상태 노출
 * - 전역 알람 스트립 데이터 제공
 */

import { defineStore } from 'pinia'
import { DEFAULT_SITE_ID } from '@/app/config'
import type { AlarmData } from '@/types/common'
import { getAlarmList } from '@/api/dashboard.client'

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

export const useAlarmStore = defineStore<'alarm', AlarmState, AlarmGetters, AlarmActions>(
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
        if (!Array.isArray(this.alarms)) {
          return []
        }
        return this.alarms.filter((alarm) => !alarm.acknowledged)
      },
      
      criticalAlarms(): AlarmData[] {
        if (!Array.isArray(this.alarms)) {
          return []
        }
        return this.alarms.filter((alarm) => alarm.level === 'critical' && !alarm.acknowledged)
      },
      
      unacknowledgedCount(): number {
        if (!Array.isArray(this.alarms)) {
          return 0
        }
        return this.alarms.filter((alarm) => !alarm.acknowledged).length
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
        const alarm = this.alarms.find((a) => a.alarm_id === alarmId)
        if (alarm) {
          alarm.acknowledged = true
        }
        // TODO: API 호출하여 서버에 확인 처리
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
