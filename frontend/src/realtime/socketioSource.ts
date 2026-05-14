import { io, type Socket } from 'socket.io-client'
import type { ConnectionState, StateUpdateEvent } from './types'

export type StateUpdateHandler = (event: StateUpdateEvent) => void
export type SocketErrorHandler = (error: Error) => void

interface SubscribeAck {
  ok: boolean
  site_id?: string
  error?: string
}

const SOCKET_IO_PATH = '/socket.io'
const STATUS_NAMESPACE = '/status'

export class SocketIoSource {
  private socket: Socket | null = null
  private state: ConnectionState = 'disconnected'
  private siteId: string | null = null
  private stateHandlers = new Set<StateUpdateHandler>()
  private errorHandlers = new Set<SocketErrorHandler>()

  connect(siteId: string): void {
    if (this.socket && this.state === 'connected' && this.siteId === siteId) {
      return
    }

    this.disconnect()
    this.siteId = siteId
    this.state = 'connecting'

    const socket = io(STATUS_NAMESPACE, {
      path: SOCKET_IO_PATH,
      transports: ['websocket', 'polling'],
      reconnection: true,
      reconnectionAttempts: Infinity,
      reconnectionDelay: 1000,
      reconnectionDelayMax: 5000
    })

    socket.on('connect', () => {
      this.state = 'connected'
      socket.emit('subscribe_site', { site_id: siteId }, (ack?: SubscribeAck) => {
        if (ack && !ack.ok) {
          this.emitError(new Error(ack.error ?? 'Socket.IO site subscription failed'))
        }
      })
    })

    socket.on('site_state_update', (event: StateUpdateEvent) => {
      this.stateHandlers.forEach((handler) => handler(event))
    })

    socket.on('connect_error', (error: Error) => {
      this.state = 'error'
      this.emitError(error)
    })

    socket.on('disconnect', () => {
      this.state = 'disconnected'
    })

    this.socket = socket
  }

  subscribeState(handler: StateUpdateHandler): () => void {
    this.stateHandlers.add(handler)
    return () => {
      this.stateHandlers.delete(handler)
    }
  }

  subscribeError(handler: SocketErrorHandler): () => void {
    this.errorHandlers.add(handler)
    return () => {
      this.errorHandlers.delete(handler)
    }
  }

  disconnect(): void {
    if (!this.socket) {
      this.state = 'disconnected'
      this.siteId = null
      return
    }

    this.state = 'disconnecting'
    if (this.siteId) {
      this.socket.emit('unsubscribe_site', { site_id: this.siteId })
    }
    this.socket.removeAllListeners()
    this.socket.disconnect()
    this.socket = null
    this.siteId = null
    this.state = 'disconnected'
  }

  getState(): ConnectionState {
    return this.state
  }

  private emitError(error: Error): void {
    this.errorHandlers.forEach((handler) => handler(error))
  }
}

export const socketioSource = new SocketIoSource()

export default socketioSource
