/**
 * 이력 (History) 피처
 * 
 * Responsibility:
 * - 과거 데이터 조회
 * - 기간별 필터링
 */

// TODO:History API 구현 후 연결

export interface HistoryRecord {
  timestamp: string
  type: 'power' | 'alarm' | 'control'
  data: Record<string, unknown>
}

export interface UseHistoryFeature {
  records: HistoryRecord[]
  isLoading: boolean
}

export const useHistoryFeature = (): UseHistoryFeature => {
  const records: HistoryRecord[] = []
  const isLoading = false
  
  const fetchHistory = async (startDate: string, endDate: string) => {
    // TODO: API 호출
    console.log('Fetch history:', startDate, endDate)
  }
  
  return {
    records,
    isLoading,
    fetchHistory
  }
}

export default useHistoryFeature