import service from './index'

/**
 * 보고서 생성을 시작합니다.
 * @param {Object} data - { simulation_id, force_regenerate? }
 */
export const generateReport = (data) => {
  return service.post('/api/report/generate', data)
}

/**
 * 보고서 생성 상태를 가져옵니다.
 * @param {string} reportId
 */
export const getReportStatus = (reportId) => {
  return service.get(`/api/report/generate/status`, { params: { report_id: reportId } })
}

/**
 * 에이전트 로그를 가져옵니다(증분).
 * @param {string} reportId
 * @param {number} fromLine - 몇 번째 줄부터 가져올지
 */
export const getAgentLog = (reportId, fromLine = 0) => {
  return service.get(`/api/report/${reportId}/agent-log`, { params: { from_line: fromLine } })
}

/**
 * 콘솔 로그를 가져옵니다(증분).
 * @param {string} reportId
 * @param {number} fromLine - 몇 번째 줄부터 가져올지
 */
export const getConsoleLog = (reportId, fromLine = 0) => {
  return service.get(`/api/report/${reportId}/console-log`, { params: { from_line: fromLine } })
}

/**
 * 보고서 상세를 가져옵니다.
 * @param {string} reportId
 */
export const getReport = (reportId) => {
  return service.get(`/api/report/${reportId}`)
}

/**
 * 생성된 보고서 섹션 목록을 가져옵니다.
 * @param {string} reportId
 */
export const getReportSections = (reportId) => {
  return service.get(`/api/report/${reportId}/sections`)
}

/**
 * 보고서 에이전트와 대화합니다.
 * @param {Object} data - { simulation_id, message, chat_history? }
 */
export const chatWithReport = (data) => {
  return service.post('/api/report/chat', data)
}
