/**
 * 단위 변환 유틸리티
 * 
 * EMS에서 사용하는 단위 변환 함수를 정의합니다.
 */

/**
 * kW를 MW로 변환
 */
export const kwToMw = (kw: number): number => kw / 1000

/**
 * MW를 kW로 변환
 */
export const mwToKw = (mw: number): number => mw * 1000

/**
 * kWh를 MWh로 변환
 */
export const kwhToMwh = (kwh: number): number => kwh / 1000

/**
 * MWh를 kWh로 변환
 */
export const mwhToKwh = (mwh: number): number => mwh * 1000

/**
 * 퍼센트를 소수로 변환 (0-100 -> 0-1)
 */
export const percentToDecimal = (percent: number): number => percent / 100

/**
 * 소수를 퍼센트로 변환 (0-1 -> 0-100)
 */
export const decimalToPercent = (decimal: number): number => decimal * 100

/**
 * 전력格式化 (kW)
 */
export const formatPower = (kw: number, decimals: number = 1): string => {
  if (Math.abs(kw) >= 1000) {
    return `${kwToMw(kw).toFixed(decimals)} MW`
  }
  return `${kw.toFixed(decimals)} kW`
}

/**
 * 용량格式化 (kWh)
 */
export const formatCapacity = (kwh: number, decimals: number = 1): string => {
  if (Math.abs(kwh) >= 1000) {
    return `${kwhToMwh(kwh).toFixed(decimals)} MWh`
  }
  return `${kwh.toFixed(decimals)} kWh`
}

/**
 * SOC格式化 (%)
 */
export const formatSoc = (soc: number, decimals: number = 0): string => {
  return `${soc.toFixed(decimals)}%`
}

/**
 * 시간格式化
 */
export const formatTimestamp = (timestamp: string): string => {
  const date = new Date(timestamp)
  return date.toLocaleString('ko-KR', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  })
}

export default {
  kwToMw,
  mwToKw,
  kwhToMwh,
  mwhToKwh,
  percentToDecimal,
  decimalToPercent,
  formatPower,
  formatCapacity,
  formatSoc,
  formatTimestamp
}