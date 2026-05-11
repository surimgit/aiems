/**
 * ESS 부호 규칙 및 전력 해석 도메인
 * 
 * 이 파일은 EMS에서 사용하는 부호 규칙을 единство에서 관리합니다.
 *다른 파일에서 중복 구현 금지.
 * 
 * [ESS 부호 규칙]
 * - 양수(+): 방전 (Discharge) - ESS에서 외부로 전력送出
 * - 음수(-): 충전 (Charge) - 외부에서 ESS로 전력입력
 * 
 * [net_power 해석]
 * - net_power > 0: ESS 방전 중 (外部供电)
 * - net_power < 0: ESS 충전 중 (受電)
 * - net_power = 0: 유휴 (Idle)
 */

import type { PowerData } from '@/types/common'

/**
 * ESS 부호 규칙 타입
 */
export type EssSign = 'charge' | 'discharge' | 'idle'

/**
 * 전원 값의 부호 해석
 * 
 * @param power 전원 값 (kW)
 * @returns 'charge' | 'discharge' | 'idle'
 */
export const interpretPowerSign = (power: number): EssSign => {
  if (power > 0) return 'discharge'
  if (power < 0) return 'charge'
  return 'idle'
}

/**
 * 방전 여부 확인
 * 
 * @param power 전원 값 (kW)
 */
export const isDischarging = (power: number): boolean => power > 0

/**
 * 충전 여부 확인
 * 
 * @param power 전원 값 (kW)
 */
export const isCharging = (power: number): boolean => power < 0

/**
 * 유휴 상태 확인
 * 
 * @param power 전원 값 (kW)
 */
export const isIdle = (power: number): boolean => power === 0

/**
 * net_power를 해석하여 상태 객체 반환
 * 
 * @param netPower 순/net 전력값
 * @returns { sign, isDischarging, isCharging }
 */
export const interpretNetPower = (
  netPower: number
): {
  sign: EssSign
  isDischarging: boolean
  isCharging: boolean
  isIdle: boolean
} => {
  return {
    sign: interpretPowerSign(netPower),
    isDischarging: isDischarging(netPower),
    isCharging: isCharging(netPower),
    isIdle: isIdle(netPower)
  }
}

/**
 * 부호에 따른 표시 문자 반환
 * 
 * @param power 전원 값 (kW)
 */
export const getPowerSignDisplay = (power: number): string => {
  if (power > 0) return `↓${Math.abs(power).toFixed(1)}kW`
  if (power < 0) return `↑${Math.abs(power).toFixed(1)}kW`
  return '−0.0kW'
}

/**
 * 전력 데이터에서 부호 정보 추출
 * 
 * @param data 전력 데이터
 */
export const extractSignFromPower = (data: PowerData): {
  sign: EssSign
  display: string
} => ({
  sign: interpretPowerSign(data.net_power_kw),
  display: getPowerSignDisplay(data.net_power_kw)
})

export default {
  interpretPowerSign,
  isDischarging,
  isCharging,
  isIdle,
  interpretNetPower,
  getPowerSignDisplay,
  extractSignFromPower
}
