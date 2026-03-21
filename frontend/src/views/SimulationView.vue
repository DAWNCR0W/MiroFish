<template>
  <div class="main-view">
    <!-- 헤더 -->
    <header class="app-header">
      <div class="header-left">
        <div class="brand" @click="router.push('/')">MIROFISH</div>
      </div>
      
      <div class="header-center">
        <div class="view-switcher">
          <button 
            v-for="mode in ['graph', 'split', 'workbench']" 
            :key="mode"
            class="switch-btn"
            :class="{ active: viewMode === mode }"
            @click="viewMode = mode"
          >
            {{ { graph: '그래프', split: '분할', workbench: '작업공간' }[mode] }}
          </button>
        </div>
      </div>

      <div class="header-right">
        <div class="workflow-step">
          <span class="step-num">2단계 / 5단계</span>
          <span class="step-name">환경 설정</span>
        </div>
        <div class="step-divider"></div>
        <span class="status-indicator" :class="statusClass">
          <span class="dot"></span>
          {{ statusText }}
        </span>
      </div>
    </header>

    <!-- 주요 콘텐츠 영역 -->
    <main class="content-area">
      <!-- 왼쪽 패널: 그래프 -->
      <div class="panel-wrapper left" :style="leftPanelStyle">
        <GraphPanel 
          :graphData="graphData"
          :loading="graphLoading"
          :currentPhase="2"
          @refresh="refreshGraph"
          @toggle-maximize="toggleMaximize('graph')"
        />
      </div>

      <!-- 오른쪽 패널: 2단계 환경 설정 -->
      <div class="panel-wrapper right" :style="rightPanelStyle">
        <Step2EnvSetup
          :simulationId="currentSimulationId"
          :projectData="projectData"
          :graphData="graphData"
          :systemLogs="systemLogs"
          @go-back="handleGoBack"
          @next-step="handleNextStep"
          @add-log="addLog"
          @update-status="updateStatus"
        />
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import GraphPanel from '../components/GraphPanel.vue'
import Step2EnvSetup from '../components/Step2EnvSetup.vue'
import { getProject, getGraphData } from '../api/graph'
import { getSimulation, stopSimulation, getEnvStatus, closeSimulationEnv } from '../api/simulation'
import { warnLog } from '../utils/logger'

const route = useRoute()
const router = useRouter()

// 속성
const props = defineProps({
  simulationId: String
})

// 레이아웃 상태
const viewMode = ref('split')

// 데이터 상태
const currentSimulationId = ref(route.params.simulationId)
const projectData = ref(null)
const graphData = ref(null)
const graphLoading = ref(false)
const systemLogs = ref([])
const currentStatus = ref('processing') // processing | completed | error

// --- 계산된 레이아웃 스타일 ---
const leftPanelStyle = computed(() => {
  if (viewMode.value === 'graph') return { width: '100%', opacity: 1, transform: 'translateX(0)' }
  if (viewMode.value === 'workbench') return { width: '0%', opacity: 0, transform: 'translateX(-20px)' }
  return { width: '50%', opacity: 1, transform: 'translateX(0)' }
})

const rightPanelStyle = computed(() => {
  if (viewMode.value === 'workbench') return { width: '100%', opacity: 1, transform: 'translateX(0)' }
  if (viewMode.value === 'graph') return { width: '0%', opacity: 0, transform: 'translateX(20px)' }
  return { width: '50%', opacity: 1, transform: 'translateX(0)' }
})

// --- 상태 계산 ---
const statusClass = computed(() => {
  return currentStatus.value
})

const statusText = computed(() => {
  if (currentStatus.value === 'error') return '오류'
  if (currentStatus.value === 'completed') return '준비 완료'
  return '준비 중'
})

// --- 보조 함수 ---
const addLog = (msg) => {
  const time = new Date().toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' }) + '.' + new Date().getMilliseconds().toString().padStart(3, '0')
  systemLogs.value.push({ time, msg })
  if (systemLogs.value.length > 100) {
    systemLogs.value.shift()
  }
}

const updateStatus = (status) => {
  currentStatus.value = status
}

// --- 레이아웃 메서드 ---
const toggleMaximize = (target) => {
  if (viewMode.value === target) {
    viewMode.value = 'split'
  } else {
    viewMode.value = target
  }
}

const handleGoBack = () => {
  // process 페이지로 돌아갑니다
  if (projectData.value?.project_id) {
    router.push({ name: 'Process', params: { projectId: projectData.value.project_id } })
  } else {
    router.push('/')
  }
}

const handleNextStep = (params = {}) => {
  addLog('3단계로 이동: 시뮬레이션 시작')
  
  // 시뮬레이션 회차 설정을 기록합니다
  if (params.maxRounds) {
    addLog(`사용자 지정 시뮬레이션 회차: ${params.maxRounds}회`)
  } else {
    addLog('자동 설정 회차를 사용합니다')
  }
  
  // 라우팅 파라미터를 구성합니다
  const routeParams = {
    name: 'SimulationRun',
    params: { simulationId: currentSimulationId.value }
  }
  
  // 사용자 지정 회차가 있으면 query로 전달합니다
  if (params.maxRounds) {
    routeParams.query = { maxRounds: params.maxRounds }
  }
  
  // 3단계 페이지로 이동합니다
  router.push(routeParams)
}

// --- Data Logic ---

/**
 * 실행 중인 시뮬레이션을 확인하고 종료합니다.
 * 사용자가 3단계에서 2단계로 돌아오면 기본적으로 시뮬레이션 종료를 의미합니다.
 */
const checkAndStopRunningSimulation = async () => {
  if (!currentSimulationId.value) return
  
  try {
    // 먼저 시뮬레이션 환경이 살아 있는지 확인합니다
    const envStatusRes = await getEnvStatus({ simulation_id: currentSimulationId.value })
    
    if (envStatusRes.success && envStatusRes.data?.env_alive) {
      addLog('실행 중인 시뮬레이션 환경을 감지했습니다. 종료하는 중...')
      
      // 우아하게 시뮬레이션 환경을 종료합니다
      try {
        const closeRes = await closeSimulationEnv({ 
          simulation_id: currentSimulationId.value,
          timeout: 10  // 10초 타임아웃
        })
        
        if (closeRes.success) {
          addLog('✓ 시뮬레이션 환경이 종료되었습니다')
        } else {
          addLog(`시뮬레이션 환경 종료 실패: ${closeRes.error || '알 수 없는 오류'}`)
          // 우아한 종료가 실패하면 강제 중지를 시도합니다
          await forceStopSimulation()
        }
      } catch (closeErr) {
        addLog(`시뮬레이션 환경 종료 중 예외가 발생했습니다: ${closeErr.message}`)
        // 우아한 종료 중 예외가 발생하면 강제 중지를 시도합니다
        await forceStopSimulation()
      }
    } else {
      // 환경은 꺼져 있지만 프로세스가 남아 있을 수 있어 시뮬레이션 상태를 확인합니다
      const simRes = await getSimulation(currentSimulationId.value)
      if (simRes.success && simRes.data?.status === 'running') {
        addLog('시뮬레이션이 실행 중입니다. 중지하는 중...')
        await forceStopSimulation()
      }
    }
  } catch (err) {
    currentStatus.value = 'error'
    addLog(`시뮬레이션 상태 확인 실패: ${err.message}`)
    warnLog('시뮬레이션 상태 확인 실패:', err)
  }
}

/**
 * 시뮬레이션을 강제로 종료합니다.
 */
const forceStopSimulation = async () => {
  try {
    const stopRes = await stopSimulation({ simulation_id: currentSimulationId.value })
    if (stopRes.success) {
      addLog('✓ 시뮬레이션을 강제 중지했습니다')
    } else {
      currentStatus.value = 'error'
      addLog(`강제 시뮬레이션 중지 실패: ${stopRes.error || '알 수 없는 오류'}`)
    }
  } catch (err) {
    currentStatus.value = 'error'
    addLog(`강제 중지 중 예외 발생: ${err.message}`)
  }
}

const loadSimulationData = async () => {
  try {
    addLog(`시뮬레이션 데이터 로드: ${currentSimulationId.value}`)
    
    // 시뮬레이션 정보를 가져옵니다
    const simRes = await getSimulation(currentSimulationId.value)
    if (simRes.success && simRes.data) {
      const simData = simRes.data
      
      // 프로젝트 정보를 가져옵니다
      if (simData.project_id) {
        const projRes = await getProject(simData.project_id)
        if (projRes.success && projRes.data) {
          projectData.value = projRes.data
          currentStatus.value = 'processing'
          addLog(`프로젝트 로드 성공: ${projRes.data.project_id}`)
          
          // 그래프 데이터를 가져옵니다
          if (projRes.data.graph_id) {
            await loadGraph(projRes.data.graph_id)
          }
        } else {
          currentStatus.value = 'error'
          addLog(`프로젝트 로드 실패: ${projRes.error || '알 수 없는 오류'}`)
        }
      }
    } else {
      currentStatus.value = 'error'
      addLog(`시뮬레이션 데이터 로드 실패: ${simRes.error || '알 수 없는 오류'}`)
    }
  } catch (err) {
    currentStatus.value = 'error'
    addLog(`불러오는 중 예외가 발생했습니다: ${err.message}`)
  }
}

const loadGraph = async (graphId) => {
  graphLoading.value = true
  try {
    const res = await getGraphData(graphId)
    if (res.success) {
      graphData.value = res.data
      currentStatus.value = 'processing'
      addLog('그래프 데이터 로드 완료')
    } else {
      currentStatus.value = 'error'
      addLog(`그래프 로드 실패: ${res.error || '알 수 없는 오류'}`)
    }
  } catch (err) {
    currentStatus.value = 'error'
    addLog(`그래프 로드 실패: ${err.message}`)
  } finally {
    graphLoading.value = false
  }
}

const refreshGraph = () => {
  if (projectData.value?.graph_id) {
    loadGraph(projectData.value.graph_id)
  }
}

onMounted(async () => {
  addLog('시뮬레이션 화면을 초기화했습니다')
  
  // 실행 중인 시뮬레이션을 확인하고 종료합니다(3단계에서 돌아올 때)
  await checkAndStopRunningSimulation()
  
  // 시뮬레이션 데이터를 불러옵니다
  loadSimulationData()
})
</script>

<style scoped>
.main-view {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: #FFF;
  overflow: hidden;
  font-family: 'Space Grotesk', 'Noto Sans KR', system-ui, sans-serif;
}

/* Header */
.app-header {
  height: 60px;
  border-bottom: 1px solid #EAEAEA;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  background: #FFF;
  z-index: 100;
  position: relative;
}

.brand {
  font-family: 'JetBrains Mono', monospace;
  font-weight: 800;
  font-size: 18px;
  letter-spacing: 1px;
  cursor: pointer;
}

.header-center {
  position: absolute;
  left: 50%;
  transform: translateX(-50%);
}

.view-switcher {
  display: flex;
  background: #F5F5F5;
  padding: 4px;
  border-radius: 6px;
  gap: 4px;
}

.switch-btn {
  border: none;
  background: transparent;
  padding: 6px 16px;
  font-size: 12px;
  font-weight: 600;
  color: #666;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s;
}

.switch-btn.active {
  background: #FFF;
  color: #000;
  box-shadow: 0 2px 4px rgba(0,0,0,0.05);
}

.header-right {
  display: flex;
  align-items: center;
  gap: 16px;
}

.workflow-step {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
}

.step-num {
  font-family: 'JetBrains Mono', monospace;
  font-weight: 700;
  color: #999;
}

.step-name {
  font-weight: 700;
  color: #000;
}

.step-divider {
  width: 1px;
  height: 14px;
  background-color: #E0E0E0;
}

.status-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #666;
  font-weight: 500;
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #CCC;
}

.status-indicator.processing .dot { background: #FF5722; animation: pulse 1s infinite; }
.status-indicator.completed .dot { background: #4CAF50; }
.status-indicator.error .dot { background: #F44336; }

@keyframes pulse { 50% { opacity: 0.5; } }

/* Content */
.content-area {
  flex: 1;
  display: flex;
  position: relative;
  overflow: hidden;
}

.panel-wrapper {
  height: 100%;
  overflow: hidden;
  transition: width 0.4s cubic-bezier(0.25, 0.8, 0.25, 1), opacity 0.3s ease, transform 0.3s ease;
  will-change: width, opacity, transform;
}

.panel-wrapper.left {
  border-right: 1px solid #EAEAEA;
}
</style>
