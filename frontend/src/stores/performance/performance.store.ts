/**
 * Performance store
 *
 * Responsibility:
 * - DB-backed performance metrics for the overview dashboard
 */

import { defineStore } from 'pinia'
import { DEFAULT_SITE_ID } from '@/app/config'
import {
  getSolarSavingsPerformance,
  type SolarSavingsPerformance,
  type SolarSavingsPeriod
} from '@/api/performance.client'

interface PerformanceState {
  siteId: string
  solarSavings: SolarSavingsPerformance | null
  loading: boolean
  error: string | null
}

interface PerformanceActions {
  setSiteId(siteId: string): void
  fetchSolarSavings(siteId?: string, period?: SolarSavingsPeriod): Promise<void>
}

export const usePerformanceStore = defineStore<'performance', PerformanceState, Record<string, never>, PerformanceActions>(
  'performance',
  {
    state: (): PerformanceState => ({
      siteId: DEFAULT_SITE_ID,
      solarSavings: null,
      loading: false,
      error: null
    }),

    actions: {
      setSiteId(siteId: string): void {
        this.siteId = siteId
      },

      async fetchSolarSavings(siteId?: string, period: SolarSavingsPeriod = 'month'): Promise<void> {
        this.loading = true
        this.error = null

        const targetSiteId = siteId ?? this.siteId
        this.siteId = targetSiteId

        try {
          this.solarSavings = await getSolarSavingsPerformance(targetSiteId, period)
        } catch (error) {
          this.error = (error as Error).message
          this.solarSavings = null
          console.error('[PerformanceStore] Fetch solar savings error:', error)
        } finally {
          this.loading = false
        }
      }
    }
  }
)

export default usePerformanceStore
