import { watch, onUnmounted } from 'vue'
import { storeToRefs } from 'pinia'
import { useControlStore } from '@/stores/control/control.store'
import { getCommandStatus } from '@/api/control.client'

const POLL_INTERVAL_MS = 5_000

const TERMINAL_STATUSES = new Set([
  'COMPLETED',
  'FAILED',
  'REJECTED',
  'BLOCKED',
  'EXPIRED',
  'TIMED_OUT',
  'TIMEOUT'
])

const isTerminal = (status: string) => TERMINAL_STATUSES.has(status)

export const useCommandStatusPoller = () => {
  const controlStore = useControlStore()
  const { pendingCommands } = storeToRefs(controlStore)

  const activeTimers = new Map<string, ReturnType<typeof setTimeout>>()

  const pollOne = async (commandId: string) => {
    try {
      const result = await getCommandStatus(commandId)
      controlStore.updateCommandStatus(result)

      if (!isTerminal(result.status)) {
        scheduleOne(commandId)
      } else {
        activeTimers.delete(commandId)
      }
    } catch {
      scheduleOne(commandId)
    }
  }

  const scheduleOne = (commandId: string) => {
    const timer = setTimeout(() => {
      void pollOne(commandId)
    }, POLL_INTERVAL_MS)
    activeTimers.set(commandId, timer)
  }

  const startPollingCommand = (commandId: string, currentStatus: string) => {
    if (activeTimers.has(commandId)) return
    if (isTerminal(currentStatus)) return
    scheduleOne(commandId)
  }

  watch(
    pendingCommands,
    (cmds) => {
      for (const cmd of cmds) {
        startPollingCommand(cmd.command_id, cmd.status)
      }
    },
    { immediate: true, deep: false }
  )

  const stop = () => {
    for (const timer of activeTimers.values()) {
      clearTimeout(timer)
    }
    activeTimers.clear()
  }

  onUnmounted(stop)

  return { stop }
}

export default useCommandStatusPoller
