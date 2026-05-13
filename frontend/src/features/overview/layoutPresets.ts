export type DashboardLayoutMode = 'tablet' | 'laptop' | 'wall'

export const dashboardLayoutTokens = {
  tabletMaxWidth: 1024,
  wallMinWidth: 2560,
  panelWidth: {
    laptop: 380,
    wall: 460,
    tabletMax: 420
  }
} as const

export type DashboardWidgetId =
  | 'topologyStage'
  | 'selectedResourcePanel'
  | 'aiApprovalPanel'
  | 'alarmSummaryWidget'
  | 'powerBalanceChart'
  | 'commandTimelineWidget'
  | 'kpiSummaryWidget'

export interface DashboardWidgetLayout {
  id: DashboardWidgetId
  colSpan: number
  rowSpan: number
  order: number
  visible: boolean
}

export type DashboardLayoutPreset = Record<DashboardWidgetId, DashboardWidgetLayout>

export const dashboardLayoutPresets: Record<DashboardLayoutMode, DashboardLayoutPreset> = {
  tablet: {
    topologyStage: { id: 'topologyStage', colSpan: 8, rowSpan: 4, order: 1, visible: true },
    selectedResourcePanel: { id: 'selectedResourcePanel', colSpan: 8, rowSpan: 2, order: 2, visible: true },
    aiApprovalPanel: { id: 'aiApprovalPanel', colSpan: 8, rowSpan: 2, order: 3, visible: true },
    alarmSummaryWidget: { id: 'alarmSummaryWidget', colSpan: 8, rowSpan: 2, order: 4, visible: true },
    powerBalanceChart: { id: 'powerBalanceChart', colSpan: 8, rowSpan: 2, order: 5, visible: true },
    commandTimelineWidget: { id: 'commandTimelineWidget', colSpan: 8, rowSpan: 2, order: 6, visible: true },
    kpiSummaryWidget: { id: 'kpiSummaryWidget', colSpan: 8, rowSpan: 2, order: 7, visible: true }
  },
  laptop: {
    topologyStage: { id: 'topologyStage', colSpan: 8, rowSpan: 5, order: 1, visible: true },
    selectedResourcePanel: { id: 'selectedResourcePanel', colSpan: 4, rowSpan: 2, order: 2, visible: true },
    aiApprovalPanel: { id: 'aiApprovalPanel', colSpan: 4, rowSpan: 2, order: 3, visible: true },
    alarmSummaryWidget: { id: 'alarmSummaryWidget', colSpan: 4, rowSpan: 2, order: 4, visible: true },
    powerBalanceChart: { id: 'powerBalanceChart', colSpan: 4, rowSpan: 2, order: 5, visible: true },
    commandTimelineWidget: { id: 'commandTimelineWidget', colSpan: 4, rowSpan: 2, order: 6, visible: true },
    kpiSummaryWidget: { id: 'kpiSummaryWidget', colSpan: 4, rowSpan: 2, order: 7, visible: true }
  },
  wall: {
    topologyStage: { id: 'topologyStage', colSpan: 16, rowSpan: 6, order: 1, visible: true },
    selectedResourcePanel: { id: 'selectedResourcePanel', colSpan: 8, rowSpan: 2, order: 2, visible: true },
    aiApprovalPanel: { id: 'aiApprovalPanel', colSpan: 8, rowSpan: 2, order: 3, visible: true },
    alarmSummaryWidget: { id: 'alarmSummaryWidget', colSpan: 8, rowSpan: 2, order: 4, visible: true },
    powerBalanceChart: { id: 'powerBalanceChart', colSpan: 8, rowSpan: 2, order: 5, visible: true },
    commandTimelineWidget: { id: 'commandTimelineWidget', colSpan: 8, rowSpan: 2, order: 6, visible: true },
    kpiSummaryWidget: { id: 'kpiSummaryWidget', colSpan: 8, rowSpan: 2, order: 7, visible: true }
  }
}

export const resolveDashboardLayoutMode = (viewportWidth: number): DashboardLayoutMode => {
  if (viewportWidth <= dashboardLayoutTokens.tabletMaxWidth) return 'tablet'
  if (viewportWidth >= dashboardLayoutTokens.wallMinWidth) return 'wall'
  return 'laptop'
}
