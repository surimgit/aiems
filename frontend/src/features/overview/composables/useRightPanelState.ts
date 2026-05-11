import { computed, ref } from 'vue'
import type { RightPanelMode, RightPanelState } from '../types'

export const useRightPanelState = () => {
  const state = ref<RightPanelState>('closed')
  const mode = ref<RightPanelMode | null>(null)

  const isOpen = computed(() => state.value === 'open' || state.value === 'switching')

  const open = (nextMode: RightPanelMode) => {
    if (!isOpen.value) {
      state.value = 'opening'
      mode.value = nextMode
      state.value = 'open'
      return
    }

    state.value = 'switching'
    mode.value = nextMode
    state.value = 'open'
  }

  const close = () => {
    state.value = 'closing'
    mode.value = null
    state.value = 'closed'
  }

  const toggle = (nextMode: RightPanelMode) => {
    if (mode.value === nextMode && isOpen.value) {
      close()
      return
    }
    open(nextMode)
  }

  return {
    state,
    mode,
    isOpen,
    open,
    close,
    toggle
  }
}

export default useRightPanelState
