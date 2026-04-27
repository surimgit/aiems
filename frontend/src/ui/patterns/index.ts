/**
 * UI 패턴 인덱스
 * 
 *複合UIパターン (로직 + 表示)
 * 이 패턴들은 로직을 포함하고, 여러 프리미티브를 조합합니다.
 */

export { default as PanelCard } from './PanelCard.vue'
export { default as StatusChip } from './StatusChip.vue'
export { default as MetricCard } from './MetricCard.vue'

// ============ Patterns ============

import type { ComputedRef } from 'vue'
import { computed } from 'vue'

/**
 * 데이터 표시 패턴
 */
export interface DataDisplayPattern<T> {
  data: T | null
  loading: boolean
  error: string | null
  emptyText?: string
  
  isLoading: ComputedRef<boolean>
  hasError: ComputedRef<boolean>
  hasData: ComputedRef<boolean>
  isEmpty: ComputedRef<boolean>
  
  displayData: ComputedRef<T | null>
}

export const useDataDisplayPattern = <T>(params: {
  data: () => T | null
  loading: () => boolean
  error: () => string | null
  emptyText?: string
}): DataDisplayPattern<T> => {
  const isLoading = computed(() => params.loading())
  const hasError = computed(() => !!params.error())
  const hasData = computed(() => !!params.data())
  const isEmpty = computed(() => !params.data() && !params.loading() && !params.error())
  const displayData = computed(() => params.data())
  
  return {
    get data() { return params.data() },
    get loading() { return params.loading() },
    get error() { return params.error() },
    isLoading,
    hasError,
    hasData,
    isEmpty,
    displayData
  }
}

/**
 * 카드 그리드 패턴
 */
export interface CardGridPattern {
  columns: number
  gap: number
}

export const useCardGridPattern = (columns: number = 3, gap: number = 16): CardGridPattern => ({
  columns,
  gap
})

/**
 * 필터 패턴
 */
export interface FilterOption {
  label: string
  value: string
}

export interface FilterPattern {
  selected: string | null
  options: FilterOption[]
  
  selectFilter: (value: string) => void
  clearFilter: () => void
}

export const useFilterPattern = (options: FilterOption[]): FilterPattern => {
  const selected = computed(() => null)
  
  const selectFilter = (value: string) => {
    // TODO: 구현
  }
  
  const clearFilter = () => {
    // TODO: 구현
  }
  
  return {
    get selected() { return selected.value },
    options,
    selectFilter,
    clearFilter
  }
}

/**
 *表格패턴
 */
export interface TableColumn {
  key: string
  label: string
  width?: string
  align?: 'left' | 'center' | 'right'
}

export interface TablePattern<T> {
  columns: TableColumn[]
  data: T[]
  
  getValue: (row: T, key: string) => unknown
}

export const useTablePattern = <T>(columns: TableColumn[], data: T[]): TablePattern<T> => ({
  columns,
  data,
  getValue: (row: T, key: string) => (row as Record<string, unknown>)[key]
})

export default {
  useDataDisplayPattern,
  useCardGridPattern,
  useFilterPattern,
  useTablePattern
}
