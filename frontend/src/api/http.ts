import axios, { type AxiosInstance, type AxiosRequestConfig, type AxiosResponse } from 'axios'
import { unwrapPayload, type ApiResponse } from '@/types/api'

/**
 * HTTP 클라이언트 기본 설정
 * 
 * 설계 원칙:
 * - Base URL은 환경변수에서 관리
 * - 인터셉터를 통해 인증 토큰, 에러 처리
 */

const createHttpClient = (): AxiosInstance => {
  const client = axios.create({
    baseURL: import.meta.env.VITE_API_BASE_URL || '',
    timeout: Number(import.meta.env.VITE_API_TIMEOUT) || 30000,
    headers: {
      'Content-Type': 'application/json'
    }
  })

  // 요청 인터셉터
  client.interceptors.request.use(
    (config) => {
      // TODO: 인증 토큰 추가
      // const token = getAuthToken()
      // if (token) {
      //   config.headers.Authorization = `Bearer ${token}`
      // }
      return config
    },
    (error) => {
      return Promise.reject(error)
    }
  )

  // 응답 인터셉터
  client.interceptors.response.use(
    (response: AxiosResponse) => {
      return response
    },
    (error) => {
      const requestUrl = String(error.config?.url ?? '')
      const isAiLatest = requestUrl.includes('/api/plants/') && requestUrl.includes('/ai/latest')
      const status = error.response?.status
      if (isAiLatest && (status === 404 || status === 503 || !status)) {
        return Promise.reject(error)
      }
      // TODO:グローバルエラー処理
      // 401: unauthorized -> ログイン画面にリダイレクト
      // 403: forbidden -> 権限エラー表示
      // 500: server error -> エラー表示
      console.error('[API Error]', error.response?.status, error.message)
      return Promise.reject(error)
    }
  )

  return client
}

export const httpClient = createHttpClient()

// 제네릭 HTTP 메소드 (legacy envelope + direct payload 모두 지원)
export const http = {
  get: async <T = unknown>(url: string, config?: AxiosRequestConfig): Promise<T> => {
    const response = await httpClient.get<ApiResponse<T>>(url, config)
    return unwrapPayload(response.data)
  },
  post: async <T = unknown>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T> => {
    const response = await httpClient.post<ApiResponse<T>>(url, data, config)
    return unwrapPayload(response.data)
  },
  put: async <T = unknown>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T> => {
    const response = await httpClient.put<ApiResponse<T>>(url, data, config)
    return unwrapPayload(response.data)
  },
  patch: async <T = unknown>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T> => {
    const response = await httpClient.patch<ApiResponse<T>>(url, data, config)
    return unwrapPayload(response.data)
  },
  delete: async <T = unknown>(url: string, config?: AxiosRequestConfig): Promise<T> => {
    const response = await httpClient.delete<ApiResponse<T>>(url, config)
    return unwrapPayload(response.data)
  }
}

export default httpClient
