/**
 * Polling 데이터 소스
 * 
 * 주기적 API 호출을 통한 실시간 데이터 수신 구현
 */

import { getPowerSummary, getEssStatusList } from '@/api/dashboard.client'
import { DEFAULT_SITE_ID } from '@/app/config'
import type { RealtimePowerData, RealtimeEssStatus, ConnectionState } from './types'

export type PollingCallback<T> = (data: T) => void

/**
 * PollingSource 클래스
 */
export class PollingSource {
  private intervalId: ReturnType<typeof setInterval> | null = null
  private state: ConnectionState = 'disconnected'
  
  /**
   * 전력 데이터 폴링 시작
   */
  startPowerPolling(
    intervalMs: number,
    onData: PollingCallback<RealtimePowerData>,
    onError?: (error: Error) => void,
    siteId: string = DEFAULT_SITE_ID
  ): void {
    if (this.state === 'connected') {
      console.warn('[PollingSource] Already polling')
      return
    }
    
    this.state = 'connecting'
    
    const poll = async () => {
      try {
        const data = await getPowerSummary(siteId)
        onData(data as RealtimePowerData)
        this.state = 'connected'
      } catch (error) {
        onError?.(error as Error)
      }
    }
    
    // 초기 실행
    poll()
    
    // 주기적 실행
    this.intervalId = setInterval(poll, intervalMs)
  }
  
  /**
   * ESS 상태 리스트 폴링 시작
   */
  startEssStatusPolling(
    intervalMs: number,
    onData: PollingCallback<RealtimeEssStatus[]>,
    onError?: (error: Error) => void,
    siteId: string = DEFAULT_SITE_ID
  ): void {
    if (this.state === 'connected') {
      console.warn('[PollingSource] Already polling')
      return
    }
    
    this.state = 'connecting'
    
    const poll = async () => {
      try {
        const data = await getEssStatusList(siteId)
        onData(data as unknown as RealtimeEssStatus[])
        this.state = 'connected'
      } catch (error) {
        onError?.(error as Error)
      }
    }
    
    poll()
    this.intervalId = setInterval(poll, intervalMs)
  }
  
  /**
   * 폴링 중지
   */
  stop(): void {
    if (this.intervalId) {
      clearInterval(this.intervalId)
      this.intervalId = null
    }
    this.state = 'disconnected'
  }
  
  /**
   * 현재 상태 반환
   */
  getState(): ConnectionState {
    return this.state
  }
}

export const pollingSource = new PollingSource()

export default pollingSource
