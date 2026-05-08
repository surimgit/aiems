/**
 * UI 프리미티브 인덱스
 * 
 * 기본 UI 컴포넌트 (프레젠테이션 컴포넌트)
 * 이 컴포넌트들은 로직을 포함하지 않고, presentation만 담당합니다.
 */

import type { ComputedRef, Ref } from 'vue'
import { computed } from 'vue'

// ============ Primitives ============

export interface PrimitiveProps {
  class?: string
}

export interface LoadingState {
  loading: boolean
  error?: string | null
}

export interface EmptyState {
  empty: boolean
  emptyText?: string
}

export const useLoadingState = <T>(
  data: Ref<T | null>,
  loading: Ref<boolean>,
  error: Ref<string | null>
): {
  isLoading: ComputedRef<boolean>
  hasError: ComputedRef<boolean>
  hasData: ComputedRef<boolean>
} => ({
  isLoading: computed(() => loading.value),
  hasError: computed(() => !!error.value),
  hasData: computed(() => !!data.value)
})

