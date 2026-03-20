import service from './index'

/**
 * 온톨로지를 생성합니다(문서 업로드 및 시뮬레이션 요구사항 포함).
 * @param {Object} data - files, simulation_requirement, project_name 등을 포함합니다.
 * @returns {Promise}
 */
export function generateOntology(formData) {
  return service({
    url: '/api/graph/ontology/generate',
    method: 'post',
    data: formData,
    headers: {
      'Content-Type': 'multipart/form-data'
    }
  })
}

/**
 * 그래프를 구축합니다.
 * @param {Object} data - project_id, graph_name 등을 포함합니다.
 * @returns {Promise}
 */
export function buildGraph(data) {
  return service({
    url: '/api/graph/build',
    method: 'post',
    data
  })
}

/**
 * 작업 상태를 조회합니다.
 * @param {String} taskId - 작업 ID
 * @returns {Promise}
 */
export function getTaskStatus(taskId) {
  return service({
    url: `/api/graph/task/${taskId}`,
    method: 'get'
  })
}

/**
 * 그래프 데이터를 가져옵니다.
 * @param {String} graphId - 그래프 ID
 * @returns {Promise}
 */
export function getGraphData(graphId) {
  return service({
    url: `/api/graph/data/${graphId}`,
    method: 'get'
  })
}

/**
 * 기존 그래프의 중복 엔티티를 병합합니다.
 * @param {String} graphId - 그래프 ID
 * @param {Object} data - { dry_run?: boolean, include_graph_data?: boolean }
 * @returns {Promise}
 */
export function dedupeGraph(graphId, data = {}) {
  return service({
    url: `/api/graph/dedupe/${graphId}`,
    method: 'post',
    data
  })
}

/**
 * 프로젝트 정보를 가져옵니다.
 * @param {String} projectId - 프로젝트 ID
 * @returns {Promise}
 */
export function getProject(projectId) {
  return service({
    url: `/api/graph/project/${projectId}`,
    method: 'get'
  })
}
