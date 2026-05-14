export type RightPanelMode =
  | 'alarm'
  | 'recent-command'
  | 'country-language'
  | 'selected-resource'
  | 'load-usage'

export type RightPanelState = 'closed' | 'opening' | 'open' | 'switching' | 'closing'

export type DashboardVariant = 'V0' | 'V1' | 'V2' | 'V3' | 'V4' | 'V5' | 'V6'

export interface RightPanelUiState {
  state: RightPanelState
  mode: RightPanelMode | null
}

export interface DashboardLayoutContext {
  viewportWidth: number
  panelOpen: boolean
}
