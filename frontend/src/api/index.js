import axios from 'axios'
import { warnLog } from '../utils/logger'

const createApiError = (message, sourceError = null, extras = {}) => {
  const normalized = new Error(message || sourceError?.message || '알 수 없는 오류')

  if (sourceError) {
    normalized.cause = sourceError
    normalized.code = sourceError.code
    normalized.config = sourceError.config
    normalized.request = sourceError.request
    normalized.response = sourceError.response
    normalized.status = sourceError.response?.status
  }

  Object.assign(normalized, extras)
  return normalized
}

// Axios 인스턴스를 생성합니다.
const service = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:5001',
  timeout: 300000, // 5분 타임아웃(온톨로지 생성에 시간이 오래 걸릴 수 있음)
  headers: {
    'Content-Type': 'application/json'
  }
})

// 요청 인터셉터
service.interceptors.request.use(
  config => {
    return config
  },
  error => {
    return Promise.reject(createApiError('요청을 준비하지 못했습니다', error))
  }
)

// 응답 인터셉터(오류 복구 재시도 메커니즘)
service.interceptors.response.use(
  response => {
    const res = response.data

    // 반환된 상태가 success가 아니면 오류를 발생시킵니다.
    if (!res.success && res.success !== undefined) {
      const apiError = createApiError(
        res.error || res.message || '오류',
        null,
        {
          config: response.config,
          response,
          status: response.status,
          data: res
        }
      )
      return Promise.reject(apiError)
    }

    return res
  },
  error => {
    const backendMessage = error.response?.data?.error || error.response?.data?.message
    if (backendMessage) {
      return Promise.reject(createApiError(backendMessage, error))
    }

    // 타임아웃 처리
    if (error.code === 'ECONNABORTED' && error.message.includes('timeout')) {
      return Promise.reject(createApiError('요청 시간이 초과되었습니다', error))
    }

    // 네트워크 오류 처리
    if (error.message === 'Network Error') {
      return Promise.reject(createApiError('네트워크 오류 - 연결 상태를 확인하세요', error))
    }

    return Promise.reject(createApiError(error.message || '응답 처리 중 오류가 발생했습니다', error))
  }
)

// 재시도 기능이 포함된 요청 함수
export const requestWithRetry = async (requestFn, maxRetries = 3, delay = 1000) => {
  for (let i = 0; i < maxRetries; i++) {
    try {
      return await requestFn()
    } catch (error) {
      const method = error?.config?.method?.toLowerCase?.()
      const isRetryableMethod = ['get', 'head', 'options'].includes(method)
      if (!isRetryableMethod) throw error

      if (i === maxRetries - 1) throw error

      warnLog(`요청 실패, 재시도 중 (${i + 1}/${maxRetries})...`, error)
      await new Promise(resolve => setTimeout(resolve, delay * Math.pow(2, i)))
    }
  }
}

export default service
