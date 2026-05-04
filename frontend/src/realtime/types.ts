/**
 * 실시간 데이터 타입 정의
 * 
 * Polling과 WebSocket에서 사용하는 공통 타입을 정의합니다.
 */

/**
 * 실시간 전력 데이터
 */
export interface RealtimePowerData {
  timestamp: string
  net_power_kw: number
  pv_power_kw: number
  ess_power_kw: number
  grid_power_kw: number
  load_power_kw: number
}

/**
 * 실시간 ESS 상태
 */
export interface RealtimeEssStatus {
  ess_id: string
  name: string
  soc: number
  soh: number
  status: 'idle' | 'charging' | 'discharging' | 'fault'
  power_kw: number
}

/**
 * 실시간 알람
 */
export interface RealtimeAlarm {
  alarm_id: string
  level: 'info' | 'warning' | 'critical'
  code: string
  message: string
  ess_id?: string
  timestamp: string
}

/**
 * 실시간 이벤트 타입
 */
export type RealtimeEventType = 
  | 'power_update'
  | 'ess_status'
  | 'alarm'
  | 'command_result'
  | 'forecast_update'

/**
 * 실시간 이벤트 페이로드
 */
export interface RealtimeEvent<T = unknown> {
  type: RealtimeEventType
  timestamp: string
  data: T
}

/**
 * 연결 상태
 */
export type ConnectionState = 'connecting' | 'connected' | 'disconnecting' | 'disconnected' | 'error'

/**
 * 데이터 소스 유형
 */
export type DataSourceType = 'polling' | 'websocket'

// Types are already exported above.
