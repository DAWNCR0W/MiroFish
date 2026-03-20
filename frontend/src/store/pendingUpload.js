/**
 * 업로드 대기 파일과 요구사항을 임시로 저장합니다.
 * 홈에서 엔진 시작을 눌러 즉시 이동한 뒤 Process 페이지에서 API를 호출하기 위해 사용합니다.
 */
import { reactive } from 'vue'

const state = reactive({
  files: [],
  simulationRequirement: '',
  isPending: false
})

export function setPendingUpload(files, requirement) {
  state.files = files
  state.simulationRequirement = requirement
  state.isPending = true
}

export function getPendingUpload() {
  return {
    files: state.files,
    simulationRequirement: state.simulationRequirement,
    isPending: state.isPending
  }
}

export function clearPendingUpload() {
  state.files = []
  state.simulationRequirement = ''
  state.isPending = false
}

export default state
