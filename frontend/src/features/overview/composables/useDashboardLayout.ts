import { computed } from 'vue'
import { resolveDashboardLayoutMode } from '../layoutPresets'

export const useDashboardLayout = (viewportWidth: () => number, panelOpen: () => boolean) => {
  const mode = computed(() => resolveDashboardLayoutMode(viewportWidth()))

  const panelPresentation = computed(() => {
    if (!panelOpen()) return 'closed'
    if (mode.value === 'tablet') return 'overlay'
    return 'side'
  })

  const layoutClass = computed(() => {
    if (panelOpen()) {
      return 'dashboard-layout--panel-open'
    }
    return 'dashboard-layout--panel-closed'
  })

  return {
    mode,
    layoutClass,
    panelPresentation
  }
}

export default useDashboardLayout
