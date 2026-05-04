/**
 * WebSocket 데이터 소스
 * 
 * WebSocket 연결을 통한 실시간 데이터 수신 구현
 */

import type { RealtimeEvent, RealtimeEventType, ConnectionState } from './types'

export type WebSocketMessageHandler<T = unknown> = (event: RealtimeEvent<T>) => void

/**
 * WebSocketSource 클래스
 */
export class WebSocketSource {
  private ws: WebSocket | null = null
  private state: ConnectionState = 'disconnected'
  private handlers: Map<RealtimeEventType, Set<WebSocketMessageHandler>> = new Map()
  private reconnectAttempts = 0
  private maxReconnectAttempts = 5
  private reconnectDelay = 1000
  
  /**
   * WebSocket 연결
   */
  connect(url: string): void {
    if (this.state === 'connected') {
      console.warn('[WebSocketSource] Already connected')
      return
    }
    
    this.state = 'connecting'
    
    try {
      this.ws = new WebSocket(url)
      
      this.ws.onopen = () => {
        console.log('[WebSocketSource] Connected')
        this.state = 'connected'
        this.reconnectAttempts = 0
      }
      
      this.ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data) as RealtimeEvent
          this.handleMessage(data)
        } catch (error) {
          console.error('[WebSocketSource] Parse error', error)
        }
      }
      
      this.ws.onclose = () => {
        console.log('[WebSocketSource] Disconnected')
        this.state = 'disconnected'
        this.attemptReconnect(url)
      }
      
      this.ws.onerror = (error) => {
        console.error('[WebSocketSource] Error', error)
        this.state = 'error'
      }
    } catch (error) {
      console.error('[WebSocketSource] Connection failed', error)
      this.state = 'error'
    }
  }
  
  /**
   * 메시지 핸들러 등록
   */
  subscribe<T>(
    type: RealtimeEventType,
    handler: WebSocketMessageHandler<T>
  ): () => void {
    if (!this.handlers.has(type)) {
      this.handlers.set(type, new Set())
    }
    
    const handlers = this.handlers.get(type)!
    handlers.add(handler as WebSocketMessageHandler)
    
    // unsubscribe 함수 반환
    return () => {
      handlers.delete(handler as WebSocketMessageHandler)
    }
  }
  
  /**
   * 메시지 처리
   */
  private handleMessage<T>(event: RealtimeEvent<T>): void {
    const handlers = this.handlers.get(event.type)
    if (handlers) {
      handlers.forEach((handler) => {
        try {
          handler(event)
        } catch (error) {
          console.error('[WebSocketSource] Handler error', error)
        }
      })
    }
  }
  
  /**
   * 재연결 시도
   */
  private attemptReconnect(url: string): void {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error('[WebSocketSource] Max reconnect attempts reached')
      return
    }
    
    this.reconnectAttempts++
    const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1)
    
    console.log(`[WebSocketSource] Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts})`)
    
    setTimeout(() => {
      this.connect(url)
    }, delay)
  }
  
  /**
   * WebSocket 연결 종료
   */
  disconnect(): void {
    if (this.ws) {
      this.state = 'disconnecting'
      this.ws.close()
      this.ws = null
      this.state = 'disconnected'
    }
  }
  
  /**
   * 데이터 전송
   */
  send<T>(data: T): void {
    if (this.ws && this.state === 'connected') {
      this.ws.send(JSON.stringify(data))
    }
  }
  
  /**
   * 현재 상태 반환
   */
  getState(): ConnectionState {
    return this.state
  }
}

export const websocketSource = new WebSocketSource()

export default websocketSource