/**
 * 도메인 모델 인덱스
 * 
 * 이 파일은 도메인 모델의 타입을 정의합니다.
 */

// ESS 모델 타입
export interface EssModel {
  id: string
  name: string
  capacity: number // kWh
  maxPower: number // kW
  soc: number // State of Charge (0-100%)
  soh: number // State of Health (0-100%)
  status: 'idle' | 'charging' | 'discharging' | 'fault'
  createdAt: string
  updatedAt: string
}

// 전력 모델 타입
export interface PowerModel {
  timestamp: string
  netPower: number // kW (+: discharge, -: charge)
  pvPower: number // kW
  essPower: number // kW
  gridPower: number // kW
  loadPower: number // kW
}

// 알람 모델 타입
export interface AlarmModel {
  id: string
  level: 'info' | 'warning' | 'critical'
  code: string
  message: string
  essId?: string
  timestamp: string
  acknowledged: boolean
}

// 예측 모델 타입
export interface ForecastModel {
  timestamp: string
  type: 'generation' | 'demand'
  predicted: number // kW
  confidence: number // 0-100%
}