<template>
  <div class="report-panel">
    <!-- 메인 분할 레이아웃 -->
    <div class="main-split-layout">
      <!-- 왼쪽 패널: 보고서 스타일 -->
      <div class="left-panel report-style" ref="leftPanel">
        <div v-if="reportOutline" class="report-content-wrapper">
          <!-- 보고서 헤더 -->
          <div class="report-header-block">
            <div class="report-meta">
              <span class="report-tag">예측 보고서</span>
              <span class="report-id">ID: {{ reportId || 'REF-2024-X92' }}</span>
            </div>
            <h1 class="main-title">{{ reportOutline.title }}</h1>
            <p class="sub-title">{{ reportOutline.summary }}</p>
            <div class="header-divider"></div>
          </div>

          <!-- 섹션 목록 -->
          <div v-if="reportOutline.sections?.length" class="sections-list">
            <div
              v-for="(section, idx) in reportOutline.sections"
              :key="idx"
              class="report-section-item"
              :class="{
                'is-active': currentSectionIndex === idx + 1,
                'is-completed': isSectionCompleted(idx + 1),
                'is-pending': !isSectionCompleted(idx + 1) && currentSectionIndex !== idx + 1
              }"
            >
              <div class="section-header-row" @click="toggleSectionCollapse(idx)" :class="{ 'clickable': isSectionCompleted(idx + 1) }">
                <span class="section-number">{{ String(idx + 1).padStart(2, '0') }}</span>
                <h3 class="section-title">{{ section.title }}</h3>
                <svg
                  v-if="isSectionCompleted(idx + 1)"
                  class="collapse-icon"
                  :class="{ 'is-collapsed': collapsedSections.has(idx) }"
                  viewBox="0 0 24 24"
                  width="20"
                  height="20"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2"
                >
                  <polyline points="6 9 12 15 18 9"></polyline>
                </svg>
              </div>

              <div class="section-body" v-show="!collapsedSections.has(idx)">
                <!-- 완료 콘텐츠 -->
                <div v-if="generatedSections[idx + 1]" class="generated-content" v-html="renderMarkdown(generatedSections[idx + 1])"></div>

                <!-- 로딩 상태 -->
                <div v-else-if="currentSectionIndex === idx + 1" class="loading-state">
                  <div class="loading-icon">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                      <circle cx="12" cy="12" r="10" stroke-width="4" stroke="#E5E7EB"></circle>
                      <path d="M12 2a10 10 0 0 1 10 10" stroke-width="4" stroke="#4B5563" stroke-linecap="round"></path>
                    </svg>
                  </div>
                  <span class="loading-text">{{ section.title }} 생성 중...</span>
                </div>
              </div>
            </div>
          </div>

          <div v-else class="empty-report-state" :class="{ 'is-error': isComplete }">
            <span class="empty-report-title">
              {{ isComplete ? '보고서 본문이 생성되지 않았습니다' : '보고서 목차를 준비하는 중입니다' }}
            </span>
            <p class="empty-report-desc">
              {{ isComplete
                ? '이번 보고서는 비어 있는 목차로 완료 처리되었습니다. 다시 생성하면 정상 본문을 만들 수 있습니다.'
                : '에이전트가 목차와 섹션을 준비하면 여기에 보고서 본문이 나타납니다.' }}
            </p>
          </div>
        </div>

        <!-- 대기 상태 -->
        <div v-if="!reportOutline" class="waiting-placeholder">
          <div class="waiting-animation">
            <div class="waiting-ring"></div>
            <div class="waiting-ring"></div>
            <div class="waiting-ring"></div>
          </div>
          <span class="waiting-text">보고서 에이전트를 기다리는 중...</span>
        </div>
      </div>

      <!-- 오른쪽 패널: 워크플로 타임라인 -->
      <div class="right-panel" ref="rightPanel">
        <div class="panel-header" :class="`panel-header--${activeStep.status}`" v-if="!isComplete">
          <span class="header-dot" v-if="activeStep.status === 'active'"></span>
          <span class="header-index mono">{{ activeStep.noLabel }}</span>
          <span class="header-title">{{ activeStep.title }}</span>
          <span class="header-meta mono" v-if="activeStep.meta">{{ activeStep.meta }}</span>
        </div>

        <!-- 워크플로 개요(평평한 상태 기반 팔레트) -->
        <div class="workflow-overview" v-if="agentLogs.length > 0 || reportOutline">
          <div class="workflow-metrics">
            <div class="metric">
              <span class="metric-label">섹션</span>
              <span class="metric-value mono">{{ completedSections }}/{{ totalSections }}</span>
            </div>
            <div class="metric">
              <span class="metric-label">경과 시간</span>
              <span class="metric-value mono">{{ formatElapsedTime }}</span>
            </div>
            <div class="metric">
              <span class="metric-label">도구</span>
              <span class="metric-value mono">{{ totalToolCalls }}</span>
            </div>
            <div class="metric metric-right">
              <span class="metric-pill" :class="`pill--${statusClass}`">{{ statusText }}</span>
            </div>
          </div>

          <div class="workflow-steps" v-if="workflowSteps.length > 0">
            <div
              v-for="(step, sidx) in workflowSteps"
              :key="step.key"
              class="wf-step"
              :class="`wf-step--${step.status}`"
            >
              <div class="wf-step-connector">
                <div class="wf-step-dot"></div>
                <div class="wf-step-line" v-if="sidx < workflowSteps.length - 1"></div>
              </div>

              <div class="wf-step-content">
                <div class="wf-step-title-row">
                  <span class="wf-step-index mono">{{ step.noLabel }}</span>
                  <span class="wf-step-title">{{ step.title }}</span>
                  <span class="wf-step-meta mono" v-if="step.meta">{{ step.meta }}</span>
                </div>
              </div>
            </div>
          </div>

          <!-- 다음 단계 버튼 - 완료 후 표시 -->
          <button v-if="isComplete" class="next-step-btn" @click="goToInteraction">
            <span>심층 상호작용으로 이동</span>
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="5" y1="12" x2="19" y2="12"></line>
              <polyline points="12 5 19 12 12 19"></polyline>
            </svg>
          </button>

          <div class="workflow-divider"></div>
        </div>

        <div class="workflow-timeline">
          <TransitionGroup name="timeline-item">
            <div
              v-for="(log, idx) in displayLogs"
              :key="log.timestamp + '-' + idx"
              class="timeline-item"
              :class="getTimelineItemClass(log, idx, displayLogs.length)"
            >
              <!-- 타임라인 연결선 -->
              <div class="timeline-connector">
                <div class="connector-dot" :class="getConnectorClass(log, idx, displayLogs.length)"></div>
                <div class="connector-line" v-if="idx < displayLogs.length - 1"></div>
              </div>

              <!-- 타임라인 내용 -->
              <div class="timeline-content">
                <div class="timeline-header">
                  <span class="action-label">{{ getActionLabel(log.action) }}</span>
                  <span class="action-time">{{ formatTime(log.timestamp) }}</span>
                </div>

                <!-- 동작 본문 - 유형별로 다름 -->
                <div class="timeline-body" :class="{ 'collapsed': isLogCollapsed(log) }" @click="toggleLogExpand(log)">

                  <!-- 보고서 시작 -->
                  <template v-if="log.action === 'report_start'">
                    <div class="info-row">
                      <span class="info-key">시뮬레이션</span>
                      <span class="info-val mono">{{ log.details?.simulation_id }}</span>
                    </div>
                    <div class="info-row" v-if="log.details?.simulation_requirement">
                      <span class="info-key">요구사항</span>
                      <span class="info-val">{{ log.details.simulation_requirement }}</span>
                    </div>
                  </template>

                  <!-- 기획 -->
                  <template v-if="log.action === 'planning_start'">
                    <div class="status-message planning">{{ log.details?.message }}</div>
                  </template>
                  <template v-if="log.action === 'planning_complete'">
                    <div class="status-message success">{{ log.details?.message }}</div>
                    <div class="outline-badge" v-if="log.details?.outline">
                      {{ log.details.outline.sections?.length || 0 }} 섹션이 기획됨
                    </div>
                  </template>

                  <!-- 섹션 시작 -->
                  <template v-if="log.action === 'section_start'">
                    <div class="section-tag">
                      <span class="tag-num">#{{ log.section_index }}</span>
                      <span class="tag-title">{{ log.section_title }}</span>
                    </div>
                  </template>

                  <!-- 섹션 콘텐츠 생성 완료(내용은 생성됐지만 전체 장은 아직 완료되지 않았을 수 있음) -->
                  <template v-if="log.action === 'section_content'">
                    <div class="section-tag content-ready">
                      <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M12 20h9"></path>
                        <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"></path>
                      </svg>
                      <span class="tag-title">{{ log.section_title }}</span>
                    </div>
                  </template>

                  <!-- 섹션 완료 -->
                  <template v-if="log.action === 'section_complete'">
                    <div class="section-tag completed">
                      <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
                        <polyline points="20 6 9 17 4 12"></polyline>
                      </svg>
                      <span class="tag-title">{{ log.section_title }}</span>
                    </div>
                  </template>

                  <!-- 도구 호출 -->
                  <template v-if="log.action === 'tool_call'">
                    <div class="tool-badge" :class="'tool-' + getToolColor(log.details?.tool_name)">
                      <!-- 심층 분석 - 전구 -->
                      <svg v-if="getToolIcon(log.details?.tool_name) === 'lightbulb'" class="tool-icon" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M9 18h6M10 22h4M12 2a7 7 0 0 0-4 12.5V17a1 1 0 0 0 1 1h6a1 1 0 0 0 1-1v-2.5A7 7 0 0 0 12 2z"></path>
                      </svg>
                      <!-- 전방위 검색 - 지구본 -->
                      <svg v-else-if="getToolIcon(log.details?.tool_name) === 'globe'" class="tool-icon" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
                        <circle cx="12" cy="12" r="10"></circle>
                        <path d="M2 12h20M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"></path>
                      </svg>
                      <!-- 에이전트 인터뷰 - 사용자 -->
                      <svg v-else-if="getToolIcon(log.details?.tool_name) === 'users'" class="tool-icon" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path>
                        <circle cx="9" cy="7" r="4"></circle>
                        <path d="M23 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"></path>
                      </svg>
                      <!-- 빠른 검색 - 번개 -->
                      <svg v-else-if="getToolIcon(log.details?.tool_name) === 'zap'" class="tool-icon" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
                        <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon>
                      </svg>
                      <!-- 그래프 통계 - 차트 -->
                      <svg v-else-if="getToolIcon(log.details?.tool_name) === 'chart'" class="tool-icon" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
                        <line x1="18" y1="20" x2="18" y2="10"></line>
                        <line x1="12" y1="20" x2="12" y2="4"></line>
                        <line x1="6" y1="20" x2="6" y2="14"></line>
                      </svg>
                      <!-- 엔티티 조회 - 데이터베이스 -->
                      <svg v-else-if="getToolIcon(log.details?.tool_name) === 'database'" class="tool-icon" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
                        <ellipse cx="12" cy="5" rx="9" ry="3"></ellipse>
                        <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"></path>
                        <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"></path>
                      </svg>
                      <!-- 기본 도구 -->
                      <svg v-else class="tool-icon" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"></path>
                      </svg>
                      {{ getToolDisplayName(log.details?.tool_name) }}
                    </div>
                    <div v-if="log.details?.parameters && expandedLogs.has(log.timestamp)" class="tool-params">
                      <pre>{{ formatParams(log.details.parameters) }}</pre>
                    </div>
                  </template>

                  <!-- 도구 결과 -->
                  <template v-if="log.action === 'tool_result'">
                    <div class="result-wrapper" :class="'result-' + log.details?.tool_name">
                  <!-- 자체 헤더에 통계를 표시하는 도구는 result-meta를 숨깁니다 -->
                      <div v-if="!['interview_agents', 'insight_forge', 'panorama_search', 'quick_search'].includes(log.details?.tool_name)" class="result-meta">
                        <span class="result-tool">{{ getToolDisplayName(log.details?.tool_name) }}</span>
                        <span class="result-size">{{ formatResultSize(log.details?.result_length) }}</span>
                      </div>

                      <!-- 구조화된 결과 표시 -->
                      <div v-if="!showRawResult[log.timestamp]" class="result-structured">
                        <!-- 인터뷰 에이전트 - 특수 표시 -->
                        <template v-if="log.details?.tool_name === 'interview_agents'">
                          <InterviewDisplay :result="parseInterview(log.details.result)" :result-length="log.details?.result_length" />
                        </template>

                        <!-- 인사이트 포지 -->
                        <template v-else-if="log.details?.tool_name === 'insight_forge'">
                          <InsightDisplay :result="parseInsightForge(log.details.result)" :result-length="log.details?.result_length" />
                        </template>

                        <!-- 전방위 검색 -->
                        <template v-else-if="log.details?.tool_name === 'panorama_search'">
                          <PanoramaDisplay :result="parsePanorama(log.details.result)" :result-length="log.details?.result_length" />
                        </template>

                        <!-- 빠른 검색 -->
                        <template v-else-if="log.details?.tool_name === 'quick_search'">
                          <QuickSearchDisplay :result="parseQuickSearch(log.details.result)" :result-length="log.details?.result_length" />
                        </template>

                        <!-- 기본 -->
                        <template v-else>
                          <pre class="raw-preview">{{ truncateText(log.details?.result, 300) }}</pre>
                        </template>
                      </div>

                      <!-- 원시 결과 -->
                      <div v-else class="result-raw">
                        <pre>{{ log.details?.result }}</pre>
                      </div>
                    </div>
                  </template>

                  <!-- LLM 응답 -->
                  <template v-if="log.action === 'llm_response'">
                    <div class="llm-meta">
                      <span class="meta-tag">회차 {{ log.details?.iteration }}</span>
                      <span class="meta-tag" :class="{ active: log.details?.has_tool_calls }">
                        도구: {{ log.details?.has_tool_calls ? '있음' : '없음' }}
                      </span>
                      <span class="meta-tag" :class="{ active: log.details?.has_final_answer, 'final-answer': log.details?.has_final_answer }">
                        최종 답변: {{ log.details?.has_final_answer ? '있음' : '없음' }}
                      </span>
                    </div>
                    <!-- 최종 답변일 때 특수 안내를 표시합니다 -->
                    <div v-if="log.details?.has_final_answer" class="final-answer-hint">
                      <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
                        <polyline points="20 6 9 17 4 12"></polyline>
                      </svg>
                      <span>섹션 "{{ log.section_title }}" 내용이 생성되었습니다</span>
                    </div>
                    <div v-if="expandedLogs.has(log.timestamp) && log.details?.response" class="llm-content">
                      <pre>{{ log.details.response }}</pre>
                    </div>
                  </template>

                  <!-- 보고서 완료 -->
                  <template v-if="log.action === 'report_complete'">
                    <div class="complete-banner">
                      <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
                        <polyline points="22 4 12 14.01 9 11.01"></polyline>
                      </svg>
                      <span>보고서 생성 완료</span>
                    </div>
                  </template>
                </div>

                <!-- 푸터: 경과 시간 + 동작 버튼 -->
                <div class="timeline-footer" v-if="log.elapsed_seconds || (log.action === 'tool_call' && log.details?.parameters) || log.action === 'tool_result' || (log.action === 'llm_response' && log.details?.response)">
                  <span v-if="log.elapsed_seconds" class="elapsed-badge">+{{ log.elapsed_seconds.toFixed(1) }}s</span>
                  <span v-else class="elapsed-placeholder"></span>

                  <div class="footer-actions">
                    <!-- 도구 호출: 매개변수 표시/숨기기 -->
                    <button v-if="log.action === 'tool_call' && log.details?.parameters" class="action-btn" @click.stop="toggleLogExpand(log)">
                      {{ expandedLogs.has(log.timestamp) ? '매개변수 숨기기' : '매개변수 보기' }}
                    </button>

                    <!-- 도구 결과: 원시/구조화 보기 -->
                    <button v-if="log.action === 'tool_result'" class="action-btn" @click.stop="toggleRawResult(log.timestamp, $event)">
                      {{ showRawResult[log.timestamp] ? '구조화 보기' : '원시 출력' }}
                    </button>

                    <!-- LLM 응답: 응답 표시/숨기기 -->
                    <button v-if="log.action === 'llm_response' && log.details?.response" class="action-btn" @click.stop="toggleLogExpand(log)">
                      {{ expandedLogs.has(log.timestamp) ? '응답 숨기기' : '응답 보기' }}
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </TransitionGroup>

          <!-- 빈 상태 -->
          <div v-if="agentLogs.length === 0 && !isComplete" class="workflow-empty">
            <div class="empty-pulse"></div>
            <span>에이전트 활동을 기다리는 중...</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 하단 콘솔 로그 -->
    <div class="console-logs">
      <div class="log-header">
        <span class="log-title">콘솔 출력</span>
        <span class="log-id">{{ reportId || '보고서 없음' }}</span>
      </div>
      <div class="log-content" ref="logContent">
        <div class="log-line" v-for="(log, idx) in consoleLogs" :key="idx">
          <span class="log-msg" :class="getLogLevelClass(log)">{{ log }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onUnmounted, nextTick, h, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { getAgentLog, getConsoleLog, getReport, getReportSections } from '../api/report'
import { warnLog } from '../utils/logger'

const router = useRouter()

const props = defineProps({
  reportId: String,
  simulationId: String,
  systemLogs: Array
})

const emit = defineEmits(['add-log', 'update-status'])

// 이동
const goToInteraction = () => {
  if (props.reportId) {
    router.push({ name: 'Interaction', params: { reportId: props.reportId } })
  }
}

// 상태
const agentLogs = ref([])
const consoleLogs = ref([])
const agentLogLine = ref(0)
const consoleLogLine = ref(0)
const reportOutline = ref(null)
const currentSectionIndex = ref(null)
const generatedSections = ref({})
const expandedContent = ref(new Set())
const expandedLogs = ref(new Set())
const collapsedSections = ref(new Set())
const isComplete = ref(false)
const startTime = ref(null)
const leftPanel = ref(null)
const rightPanel = ref(null)
const logContent = ref(null)
const showRawResult = reactive({})

const resetReportState = () => {
  agentLogs.value = []
  consoleLogs.value = []
  agentLogLine.value = 0
  consoleLogLine.value = 0
  reportOutline.value = null
  currentSectionIndex.value = null
  generatedSections.value = {}
  expandedContent.value = new Set()
  expandedLogs.value = new Set()
  collapsedSections.value = new Set()
  isComplete.value = false
  startTime.value = null
}

const applyPersistedReportData = (reportData) => {
  if (!reportData) return

  if (reportData.outline) {
    reportOutline.value = reportData.outline
  }

  if (!startTime.value && reportData.created_at) {
    startTime.value = new Date(reportData.created_at)
  }

  if (reportData.status === 'completed') {
    isComplete.value = true
    currentSectionIndex.value = null
    emit('update-status', 'completed')
  }
}

const applyPersistedSections = (sections) => {
  if (!Array.isArray(sections) || sections.length === 0) return

  const nextSections = { ...generatedSections.value }
  sections.forEach(section => {
    if (section?.section_index && section.content) {
      nextSections[section.section_index] = section.content
    }
  })
  generatedSections.value = nextSections
}

const loadPersistedReportState = async () => {
  if (!props.reportId) return

  try {
    const [reportRes, sectionsRes] = await Promise.all([
      getReport(props.reportId),
      getReportSections(props.reportId)
    ])

    if (reportRes.success && reportRes.data) {
      applyPersistedReportData(reportRes.data)

      if (
        reportRes.data.status === 'completed'
        && !reportRes.data.outline?.sections?.length
      ) {
        addLog('완료된 보고서이지만 저장된 목차가 비어 있습니다. 다시 생성이 필요할 수 있습니다.')
      }
    }

    if (sectionsRes.success && sectionsRes.data) {
      applyPersistedSections(sectionsRes.data.sections || [])

      if (sectionsRes.data.is_complete) {
        isComplete.value = true
        currentSectionIndex.value = null
        emit('update-status', 'completed')
      }
    }
  } catch (err) {
    warnLog('저장된 보고서 데이터를 불러오지 못했습니다:', err)
  }
}

// 토글 함수
const toggleRawResult = (timestamp, event) => {
  // 버튼의 뷰포트 상대 위치를 저장합니다
  const button = event?.target
  const buttonRect = button?.getBoundingClientRect()
  const buttonTopBeforeToggle = buttonRect?.top

  // 상태를 전환합니다
  showRawResult[timestamp] = !showRawResult[timestamp]

  // DOM 업데이트를 기다린 뒤 버튼이 같은 위치에 보이도록 스크롤을 조정합니다
  if (button && buttonTopBeforeToggle !== undefined && rightPanel.value) {
    nextTick(() => {
      const newButtonRect = button.getBoundingClientRect()
      const buttonTopAfterToggle = newButtonRect.top
      const scrollDelta = buttonTopAfterToggle - buttonTopBeforeToggle

      // 스크롤 위치를 조정합니다
      rightPanel.value.scrollTop += scrollDelta
    })
  }
}

const toggleSectionContent = (idx) => {
  if (!generatedSections.value[idx + 1]) return
  const newSet = new Set(expandedContent.value)
  if (newSet.has(idx)) {
    newSet.delete(idx)
  } else {
    newSet.add(idx)
  }
  expandedContent.value = newSet
}

const toggleSectionCollapse = (idx) => {
  // 완료된 섹션만 접을 수 있습니다
  if (!generatedSections.value[idx + 1]) return
  const newSet = new Set(collapsedSections.value)
  if (newSet.has(idx)) {
    newSet.delete(idx)
  } else {
    newSet.add(idx)
  }
  collapsedSections.value = newSet
}

const toggleLogExpand = (log) => {
  const newSet = new Set(expandedLogs.value)
  if (newSet.has(log.timestamp)) {
    newSet.delete(log.timestamp)
  } else {
    newSet.add(log.timestamp)
  }
  expandedLogs.value = newSet
}

const isLogCollapsed = (log) => {
  if (['tool_call', 'tool_result', 'llm_response'].includes(log.action)) {
    return !expandedLogs.value.has(log.timestamp)
  }
  return false
}

// 표시 이름과 색상을 포함한 도구 설정
const toolConfig = {
  'insight_forge': {
    name: '심층 분석',
    color: 'purple',
    icon: 'lightbulb' // 전구 아이콘 - 인사이트를 나타냅니다
  },
  'panorama_search': {
    name: '전방위 검색',
    color: 'blue',
    icon: 'globe' // 지구본 아이콘 - 전방위 검색을 나타냅니다
  },
  'interview_agents': {
    name: '에이전트 인터뷰',
    color: 'green',
    icon: 'users' // 사용자 아이콘 - 대화를 나타냅니다
  },
  'quick_search': {
    name: '빠른 검색',
    color: 'orange',
    icon: 'zap' // 번개 아이콘 - 빠른 검색을 나타냅니다
  },
  'get_graph_statistics': {
    name: '그래프 통계',
    color: 'cyan',
    icon: 'chart' // 차트 아이콘 - 통계를 나타냅니다
  },
  'get_entities_by_type': {
    name: '엔티티 조회',
    color: 'pink',
    icon: 'database' // 데이터베이스 아이콘 - 엔티티를 나타냅니다
  }
}

const getToolDisplayName = (toolName) => {
  return toolConfig[toolName]?.name || toolName
}

const getToolColor = (toolName) => {
  return toolConfig[toolName]?.color || 'gray'
}

const getToolIcon = (toolName) => {
  return toolConfig[toolName]?.icon || 'tool'
}

const matchAny = (text, patterns) => {
  for (const pattern of patterns) {
    const match = text.match(pattern)
    if (match) return match
  }
  return null
}

// 파싱 함수
const parseInsightForge = (text) => {
  const result = {
    query: '',
    simulationRequirement: '',
    stats: { facts: 0, entities: 0, relationships: 0 },
    subQueries: [],
    facts: [],
    entities: [],
    relations: []
  }

  try {
    // 분석 질문을 추출합니다
    const queryMatch = matchAny(text, [
      /분석 질문:\s*(.+?)(?:\n|$)/,
      /\u5206\u6790\u95ee\u9898:\s*(.+?)(?:\n|$)/
    ])
    if (queryMatch) result.query = queryMatch[1].trim()

    // 예측 시나리오를 추출합니다
    const reqMatch = matchAny(text, [
      /예측 시나리오:\s*(.+?)(?:\n|$)/,
      /\u9884\u6d4b\u573a\u666f:\s*(.+?)(?:\n|$)/
    ])
    if (reqMatch) result.simulationRequirement = reqMatch[1].trim()

    // 통계 데이터를 추출합니다 - "관련 예측 사실: X개" 형식과 매칭합니다
    const factMatch = matchAny(text, [
      /관련 예측 사실:\s*(\d+)/,
      /\u76f8\u5173\u9884\u6d4b\u4e8b\u5b9e:\s*(\d+)/
    ])
    const entityMatch = matchAny(text, [
      /관련 엔티티:\s*(\d+)/,
      /\u76f8\u5173\u5b9e\u4f53:\s*(\d+)/
    ])
    const relMatch = matchAny(text, [
      /관계 사슬:\s*(\d+)/,
      /관계망:\s*(\d+)/,
      /\u5173\u7cfb\u94fe:\s*(\d+)/
    ])
    if (factMatch) result.stats.facts = parseInt(factMatch[1])
    if (entityMatch) result.stats.entities = parseInt(entityMatch[1])
    if (relMatch) result.stats.relationships = parseInt(relMatch[1])

      // 하위 질문을 추출합니다. 개수 제한은 두지 않습니다.
    const subQSection = matchAny(text, [
      /### 분석된 하위 질문\n([\s\S]*?)(?=\n###|$)/,
      /### \u5206\u6790\u7684하위 질문\n([\s\S]*?)(?=\n###|$)/,
      /### \u5206\u6790\u7684\u5b50\u95ee\u9898\n([\s\S]*?)(?=\n###|$)/
    ])
    if (subQSection) {
      const lines = subQSection[1].split('\n').filter(l => l.match(/^\d+\./))
      result.subQueries = lines.map(l => l.replace(/^\d+\.\s*/, '').trim()).filter(Boolean)
    }

    // 핵심 사실을 추출합니다 - 전체를 추출하며 개수 제한은 두지 않습니다
    const factsSection = matchAny(text, [
      /### 【핵심 사실】[\s\S]*?\n([\s\S]*?)(?=\n###|$)/,
      /### 【\u5173\u952e\u4e8b\u5b9e】[\s\S]*?\n([\s\S]*?)(?=\n###|$)/
    ])
    if (factsSection) {
      const lines = factsSection[1].split('\n').filter(l => l.match(/^\d+\./))
      result.facts = lines.map(l => {
        const match = l.match(/^\d+\.\s*"?(.+?)"?\s*$/)
        return match ? match[1].replace(/^"|"$/g, '').trim() : l.replace(/^\d+\.\s*/, '').trim()
      }).filter(Boolean)
    }

    // 핵심 엔티티를 추출합니다 - 요약과 관련 사실 수를 포함해 전체를 추출합니다
    const entitySection = matchAny(text, [
      /### 【핵심 엔티티】\n([\s\S]*?)(?=\n###|$)/,
      /### 【\u5173\u952e\u5b9e\u4f53】\n([\s\S]*?)(?=\n###|$)/
    ])
    if (entitySection) {
      const entityText = entitySection[1]
      // "- **" 기준으로 엔티티 블록을 나눕니다
      const entityBlocks = entityText.split(/\n(?=- \*\*)/).filter(b => b.trim().startsWith('- **'))
      result.entities = entityBlocks.map(block => {
        const nameMatch = block.match(/^-\s*\*\*(.+?)\*\*\s*\((.+?)\)/)
        const summaryMatch = matchAny(block, [
          /요약:\s*"?(.+?)"?(?:\n|$)/,
          /\u6458\u8981:\s*"?(.+?)"?(?:\n|$)/
        ])
        const relatedMatch = matchAny(block, [
          /관련 사실:\s*(\d+)/,
          /\u76f8\u5173\u4e8b\u5b9e:\s*(\d+)/
        ])
        return {
          name: nameMatch ? nameMatch[1].trim() : '',
          type: nameMatch ? nameMatch[2].trim() : '',
          summary: summaryMatch ? summaryMatch[1].trim() : '',
          relatedFactsCount: relatedMatch ? parseInt(relatedMatch[1]) : 0
        }
      }).filter(e => e.name)
    }

    // 관계망을 추출합니다 - 전체를 추출하며 개수 제한은 두지 않습니다
    const relSection = matchAny(text, [
      /### 【관계 사슬】\n([\s\S]*?)(?=\n###|$)/,
      /### 【관계망】\n([\s\S]*?)(?=\n###|$)/,
      /### 【\u5173\u7cfb\u94fe】\n([\s\S]*?)(?=\n###|$)/
    ])
    if (relSection) {
      const lines = relSection[1].split('\n').filter(l => l.trim().startsWith('-'))
      result.relations = lines.map(l => {
        const match = l.match(/^-\s*(.+?)\s*--\[(.+?)\]-->\s*(.+)$/)
        if (match) {
          return { source: match[1].trim(), relation: match[2].trim(), target: match[3].trim() }
        }
        return null
      }).filter(Boolean)
    }
  } catch (e) {
    warnLog('인사이트 포지 파싱에 실패했습니다:', e)
  }

  return result
}

const parsePanorama = (text) => {
  const result = {
    query: '',
    stats: { nodes: 0, edges: 0, activeFacts: 0, historicalFacts: 0 },
    activeFacts: [],
    historicalFacts: [],
    entities: []
  }

  try {
    // 쿼리를 추출합니다
    const queryMatch = matchAny(text, [
      /질문:\s*(.+?)(?:\n|$)/,
      /\u67e5\u8be2:\s*(.+?)(?:\n|$)/
    ])
    if (queryMatch) result.query = queryMatch[1].trim()

    // 통계 데이터를 추출합니다
    const nodesMatch = matchAny(text, [
      /총 노드 수:\s*(\d+)/,
      /\u603b\u8282\u70b9\u6570:\s*(\d+)/
    ])
    const edgesMatch = matchAny(text, [
      /총 엣지 수:\s*(\d+)/,
      /\u603b\u8fb9\u6570:\s*(\d+)/
    ])
    const activeMatch = matchAny(text, [
      /현재 유효 사실:\s*(\d+)/,
      /\u5f53\u524d\u6709\u6548\u4e8b\u5b9e:\s*(\d+)/
    ])
    const histMatch = matchAny(text, [
      /과거\/만료 사실:\s*(\d+)/,
      /\u5386\u53f2\/\u8fc7\u671f\u4e8b\u5b9e:\s*(\d+)/
    ])
    if (nodesMatch) result.stats.nodes = parseInt(nodesMatch[1])
    if (edgesMatch) result.stats.edges = parseInt(edgesMatch[1])
    if (activeMatch) result.stats.activeFacts = parseInt(activeMatch[1])
    if (histMatch) result.stats.historicalFacts = parseInt(histMatch[1])

    // 현재 유효한 사실을 추출합니다 - 전체를 추출하며 개수 제한은 두지 않습니다
    const activeSection = matchAny(text, [
      /### 【현재 유효 사실】[\s\S]*?\n([\s\S]*?)(?=\n###|$)/,
      /### 【\u5f53\u524d\u6709\u6548\u4e8b\u5b9e】[\s\S]*?\n([\s\S]*?)(?=\n###|$)/
    ])
    if (activeSection) {
      const lines = activeSection[1].split('\n').filter(l => l.match(/^\d+\./))
      result.activeFacts = lines.map(l => {
        // 번호와 따옴표를 제거합니다
        const factText = l.replace(/^\d+\.\s*/, '').replace(/^"|"$/g, '').trim()
        return factText
      }).filter(Boolean)
    }

    // 과거/만료 사실을 추출합니다 - 전체를 추출하며 개수 제한은 두지 않습니다
    const histSection = matchAny(text, [
      /### 【과거\/만료 사실】[\s\S]*?\n([\s\S]*?)(?=\n###|$)/,
      /### 【\u5386\u53f2\/\u8fc7\u671f\u4e8b\u5b9e】[\s\S]*?\n([\s\S]*?)(?=\n###|$)/
    ])
    if (histSection) {
      const lines = histSection[1].split('\n').filter(l => l.match(/^\d+\./))
      result.historicalFacts = lines.map(l => {
        const factText = l.replace(/^\d+\.\s*/, '').replace(/^"|"$/g, '').trim()
        return factText
      }).filter(Boolean)
    }

    // 관련 엔티티를 추출합니다 - 전체를 추출하며 개수 제한은 두지 않습니다
    const entitySection = text.match(/### 【관련 엔티티】\n([\s\S]*?)(?=\n###|$)/)
    if (entitySection) {
      const lines = entitySection[1].split('\n').filter(l => l.trim().startsWith('-'))
      result.entities = lines.map(l => {
        const match = l.match(/^-\s*\*\*(.+?)\*\*\s*\((.+?)\)/)
        if (match) return { name: match[1].trim(), type: match[2].trim() }
        return null
      }).filter(Boolean)
    }
  } catch (e) {
    warnLog('파노라마 파싱에 실패했습니다:', e)
  }

  return result
}

const parseInterview = (text) => {
  const result = {
    topic: '',
    agentCount: '',
    successCount: 0,
    totalCount: 0,
    selectionReason: '',
    interviews: [],
    summary: ''
  }

  try {
    // 인터뷰 주제를 추출합니다
    const topicMatch = matchAny(text, [
      /\*\*인터뷰 주제:\*\*\s*(.+?)(?:\n|$)/,
      /\*\*\u91c7\u8bbf\u4e3b\u9898:\*\*\s*(.+?)(?:\n|$)/
    ])
    if (topicMatch) result.topic = topicMatch[1].trim()

    // 인터뷰 인원을 추출합니다(예: "5 / 9 명의 시뮬레이션 에이전트")
    const countMatch = matchAny(text, [
      /\*\*인터뷰 인원:\*\*\s*(\d+)\s*\/\s*(\d+)/,
      /\*\*\u91c7\u8bbf\u4eba\u6570:\*\*\s*(\d+)\s*\/\s*(\d+)/
    ])
    if (countMatch) {
      result.successCount = parseInt(countMatch[1])
      result.totalCount = parseInt(countMatch[2])
      result.agentCount = `${countMatch[1]} / ${countMatch[2]}`
    }

    // 인터뷰 대상 선택 이유를 추출합니다
    const reasonMatch = matchAny(text, [
      /### 인터뷰 대상 선택 이유\n([\s\S]*?)(?=\n---\n|\n### 인터뷰 기록)/,
      /### \u91c7\u8bbf\u5bf9\u8c61선택 이유\n([\s\S]*?)(?=\n---\n|\n### \u91c7\u8bbf\u5b9e\u5f55)/,
      /### \u91c7\u8bbf\u5bf9\u8c61\u9009\u62e9\u7406\u7531\n([\s\S]*?)(?=\n---\n|\n### \u91c7\u8bbf\u5b9e\u5f55)/
    ])
    if (reasonMatch) {
      result.selectionReason = reasonMatch[1].trim()
    }

    // 각 사람의 선택 이유를 파싱합니다
    const parseIndividualReasons = (reasonText) => {
      const reasons = {}
      if (!reasonText) return reasons

      const lines = reasonText.split(/\n+/)
      let currentName = null
      let currentReason = []

      for (const line of lines) {
        let headerMatch = null
        let name = null
        let reasonStart = null

        // 형식 1: 숫자. **이름(index=X)**: 이유
        // 예: 1. **alumni_345(index=1)**: 우한대 동문으로서...
        headerMatch = line.match(/^\d+\.\s*\*\*([^*（(]+)(?:[（(]index\s*=?\s*\d+[)）])?\*\*[：:]\s*(.*)/)
        if (headerMatch) {
          name = headerMatch[1].trim()
          reasonStart = headerMatch[2]
        }

        // 형식 2: - 이름 선택(index X): 이유
        // 예: - selected_parent_601(index 0): 학부모 집단의 대표로서...
        if (!headerMatch) {
          headerMatch = line.match(/^-\s*(?:선택|\u9009\u62e9)([^（(]+)(?:[（(]index\s*=?\s*\d+[)）])?[：:]\s*(.*)/)
          if (headerMatch) {
            name = headerMatch[1].trim()
            reasonStart = headerMatch[2]
          }
        }

        // 형식 3: - **이름(index X)**: 이유
        // 예: - **parent_601(index 0)**: 학부모 집단의 대표로서...
        if (!headerMatch) {
          headerMatch = line.match(/^-\s*\*\*([^*（(]+)(?:[（(]index\s*=?\s*\d+[)）])?\*\*[：:]\s*(.*)/)
          if (headerMatch) {
            name = headerMatch[1].trim()
            reasonStart = headerMatch[2]
          }
        }

        if (name) {
          // 이전 사람의 이유를 저장합니다
          if (currentName && currentReason.length > 0) {
            reasons[currentName] = currentReason.join(' ').trim()
          }
          // 새 사람의 처리를 시작합니다
          currentName = name
          currentReason = reasonStart ? [reasonStart.trim()] : []
        } else if (currentName && line.trim() && !line.match(/^미선택|^\u672a\u9009|^종합하면|^\u7efc\u4e0a|^최종 선택|^\u6700\u7ec8\u9009\u62e9/)) {
          // 이유의 이어지는 줄입니다(끝부분 요약 단락은 제외)
          currentReason.push(line.trim())
        }
      }

      // 마지막 사람의 이유를 저장합니다
      if (currentName && currentReason.length > 0) {
        reasons[currentName] = currentReason.join(' ').trim()
      }

      return reasons
    }

    const individualReasons = parseIndividualReasons(result.selectionReason)

    // 각 인터뷰 기록을 추출합니다
    const interviewBlocks = text.split(/#### (?:인터뷰|\u91c7\u8bbf) #\d+:/).slice(1)

    interviewBlocks.forEach((block, index) => {
      const interview = {
        num: index + 1,
        title: '',
        name: '',
        role: '',
        bio: '',
        selectionReason: '',
        questions: [],
        twitterAnswer: '',
        redditAnswer: '',
        quotes: []
      }

      // 제목을 추출합니다(예: "학생", "교육 종사자" 등)
      const titleMatch = block.match(/^(.+?)\n/)
      if (titleMatch) interview.title = titleMatch[1].trim()

      // 이름과 역할을 추출합니다
      const nameRoleMatch = block.match(/\*\*(.+?)\*\*\s*\((.+?)\)/)
      if (nameRoleMatch) {
        interview.name = nameRoleMatch[1].trim()
        interview.role = nameRoleMatch[2].trim()
        // 해당 사람의 선택 이유를 설정합니다
        interview.selectionReason = individualReasons[interview.name] || ''
      }

      // 소개를 추출합니다
      const bioMatch = matchAny(block, [
        /_소개:\s*([\s\S]*?)_\n/,
        /_\u7b80\u4ecb:\s*([\s\S]*?)_\n/
      ])
      if (bioMatch) {
        interview.bio = bioMatch[1].trim().replace(/\.\.\.$/, '...')
      }

      // 질문 목록을 추출합니다
      const qMatch = matchAny(block, [
        /\*\*질문:\*\*\s*([\s\S]*?)(?=\n\n\*\*(?:답변|A):\*\*|\*\*(?:답변|A):\*\*)/,
        /\*\*Q:\*\*\s*([\s\S]*?)(?=\n\n\*\*(?:답변|A):\*\*|\*\*(?:답변|A):\*\*)/
      ])
      if (qMatch) {
        const qText = qMatch[1].trim()
        // 숫자 번호를 기준으로 질문을 분리합니다
        const questions = qText.split(/\n\d+\.\s+/).filter(q => q.trim())
        if (questions.length > 0) {
          // 첫 번째 질문 앞에 "1."이 있으면 별도 처리합니다
          const firstQ = qText.match(/^1\.\s+(.+)/)
          if (firstQ) {
            interview.questions = [firstQ[1].trim(), ...questions.slice(1).map(q => q.trim())]
          } else {
            interview.questions = questions.map(q => q.trim())
          }
        }
      }

      // 답변을 추출합니다 - Twitter와 Reddit으로 분리합니다
      const answerMatch = matchAny(block, [
        /\*\*답변:\*\*\s*([\s\S]*?)(?=\*\*(?:핵심 인용|\u5173\u952e\u5f15\u8a00)|$)/,
        /\*\*A:\*\*\s*([\s\S]*?)(?=\*\*(?:핵심 인용|\u5173\u952e\u5f15\u8a00)|$)/
      ])
      if (answerMatch) {
        const answerText = answerMatch[1].trim()

        // Twitter와 Reddit 답변을 분리합니다
        const twitterMatch = matchAny(answerText, [
          /【트위터 플랫폼 답변】\n?([\s\S]*?)(?=【레딧 플랫폼 답변】|【Reddit\u5e73\u53f0\u56de\u7b54】|$)/,
          /【Twitter\u5e73\u53f0\u56de\u7b54】\n?([\s\S]*?)(?=【Reddit\u5e73\u53f0\u56de\u7b54】|【레딧 플랫폼 답변】|$)/
        ])
        const redditMatch = matchAny(answerText, [
          /【레딧 플랫폼 답변】\n?([\s\S]*?)$/,
          /【Reddit\u5e73\u53f0\u56de\u7b54】\n?([\s\S]*?)$/
        ])

        if (twitterMatch) {
          interview.twitterAnswer = twitterMatch[1].trim()
        }
        if (redditMatch) {
          interview.redditAnswer = redditMatch[1].trim()
        }

        // 플랫폼 폴백 로직(구식 형식: 플랫폼 표시가 하나만 있는 경우와 호환)
        if (!twitterMatch && redditMatch) {
          // Reddit 답변만 있는 경우, 자리표시자가 아닐 때만 기본 표시용으로 복사합니다
          if (interview.redditAnswer && !isPlaceholderText(interview.redditAnswer)) {
            interview.twitterAnswer = interview.redditAnswer
          }
        } else if (twitterMatch && !redditMatch) {
          if (interview.twitterAnswer && !isPlaceholderText(interview.twitterAnswer)) {
            interview.redditAnswer = interview.twitterAnswer
          }
        } else if (!twitterMatch && !redditMatch) {
          // 플랫폼 구분 표시가 없는 경우(아주 오래된 형식), 전체를 답변으로 사용합니다
          interview.twitterAnswer = answerText
        }
      }

      // 핵심 인용문을 추출합니다(여러 인용 부호 형식과 호환)
      const quotesMatch = matchAny(block, [
        /\*\*핵심 인용:\*\*\n([\s\S]*?)(?=\n---|\n####|$)/,
        /\*\*\u5173\u952e\u5f15\u8a00:\*\*\n([\s\S]*?)(?=\n---|\n####|$)/
      ])
      if (quotesMatch) {
        const quotesText = quotesMatch[1]
        // 우선 > "text" 형식을 매칭합니다
        let quoteMatches = quotesText.match(/> "([^"]+)"/g)
        // 폴백: > "text" 또는 > \u201Ctext\u201D(중국어 인용 부호)를 매칭합니다
        if (!quoteMatches) {
          quoteMatches = quotesText.match(/> [\u201C""]([^\u201D""]+)[\u201D""]/g)
        }
        if (quoteMatches) {
          interview.quotes = quoteMatches
            .map(q => q.replace(/^> [\u201C""]|[\u201D""]$/g, '').trim())
            .filter(q => q)
        }
      }

      if (interview.name || interview.title) {
        result.interviews.push(interview)
      }
    })

    const summaryMatch = matchAny(text, [
      /### 인터뷰 요약 및 핵심 관점\n([\s\S]*?)$/,
      /### \u91c7\u8bbf\u6458\u8981\u4e0e\u6838\u5fc3\u89c2\u70b9\n([\s\S]*?)$/
    ])
    if (summaryMatch) {
      result.summary = summaryMatch[1].trim()
    }
  } catch (e) {
    warnLog('인터뷰 파싱에 실패했습니다:', e)
  }

  return result
}

const parseQuickSearch = (text) => {
  const result = {
    query: '',
    count: 0,
    facts: [],
    edges: [],
    nodes: []
  }

  try {
    // 검색 쿼리를 추출합니다
    const queryMatch = matchAny(text, [
      /검색어:\s*(.+?)(?:\n|$)/,
      /\u641c\u7d22\u67e5\u8be2:\s*(.+?)(?:\n|$)/
    ])
    if (queryMatch) result.query = queryMatch[1].trim()

    // 결과 수를 추출합니다
    const countMatch = matchAny(text, [
      /관련 정보\s*(\d+)건을 찾았습니다/,
      /\u627e\u5230\s*(\d+)\s*\u6761/
    ])
    if (countMatch) result.count = parseInt(countMatch[1])

    // 관련 사실을 추출합니다 - 전체를 추출하며 개수 제한은 두지 않습니다
    const factsSection = matchAny(text, [
      /### 관련 사실:\n([\s\S]*?)(?=\n###|$)/,
      /### \u76f8\u5173\u4e8b\u5b9e:\n([\s\S]*?)(?=\n###|$)/
    ])
    if (factsSection) {
      const lines = factsSection[1].split('\n').filter(l => l.match(/^\d+\./))
      result.facts = lines.map(l => l.replace(/^\d+\.\s*/, '').trim()).filter(Boolean)
    }

    // 간선 정보를 추출해 봅니다(있다면)
    const edgesSection = matchAny(text, [
      /### 관련 간선:\n([\s\S]*?)(?=\n###|$)/,
      /### \u76f8\u5173\u8fb9:\n([\s\S]*?)(?=\n###|$)/
    ])
    if (edgesSection) {
      const lines = edgesSection[1].split('\n').filter(l => l.trim().startsWith('-'))
      result.edges = lines.map(l => {
        const match = l.match(/^-\s*(.+?)\s*--\[(.+?)\]-->\s*(.+)$/)
        if (match) {
          return { source: match[1].trim(), relation: match[2].trim(), target: match[3].trim() }
        }
        return null
      }).filter(Boolean)
    }

    // 노드 정보를 추출해 봅니다(있다면)
    const nodesSection = matchAny(text, [
      /### 관련 노드:\n([\s\S]*?)(?=\n###|$)/,
      /### \u76f8\u5173\u8282\u70b9:\n([\s\S]*?)(?=\n###|$)/
    ])
    if (nodesSection) {
      const lines = nodesSection[1].split('\n').filter(l => l.trim().startsWith('-'))
      result.nodes = lines.map(l => {
        const match = l.match(/^-\s*\*\*(.+?)\*\*\s*\((.+?)\)/)
        if (match) return { name: match[1].trim(), type: match[2].trim() }
        const simpleMatch = l.match(/^-\s*(.+)$/)
        if (simpleMatch) return { name: simpleMatch[1].trim(), type: '' }
        return null
      }).filter(Boolean)
    }
  } catch (e) {
    warnLog('빠른 검색 파싱에 실패했습니다:', e)
  }

  return result
}

// ========== 하위 컴포넌트 ==========

// 인사이트 표시 컴포넌트 - 전체 데이터 렌더링을 강화한 인터뷰형 스타일
const InsightDisplay = {
  props: ['result', 'resultLength'],
  setup(props) {
    const activeTab = ref('facts') // 'facts', 'entities', 'relations', 'subqueries'
    const expandedFacts = ref(false)
    const expandedEntities = ref(false)
    const expandedRelations = ref(false)
    const INITIAL_SHOW_COUNT = 5

    // 표시용 결과 크기를 형식화합니다
    const formatSize = (length) => {
      if (!length) return ''
      if (length >= 1000) {
        return `${(length / 1000).toFixed(1)}천 자`
      }
      return `${length}자`
    }

    return () => h('div', { class: 'insight-display' }, [
      // 헤더 섹션 - 인터뷰 헤더처럼 구성합니다
      h('div', { class: 'insight-header' }, [
        h('div', { class: 'header-main' }, [
          h('div', { class: 'header-title' }, '심층 분석'),
          h('div', { class: 'header-stats' }, [
            h('span', { class: 'stat-item' }, [
              h('span', { class: 'stat-value' }, props.result.stats.facts || props.result.facts.length),
              h('span', { class: 'stat-label' }, '사실')
            ]),
            h('span', { class: 'stat-divider' }, '/'),
            h('span', { class: 'stat-item' }, [
              h('span', { class: 'stat-value' }, props.result.stats.entities || props.result.entities.length),
              h('span', { class: 'stat-label' }, '엔티티')
            ]),
            h('span', { class: 'stat-divider' }, '/'),
            h('span', { class: 'stat-item' }, [
              h('span', { class: 'stat-value' }, props.result.stats.relationships || props.result.relations.length),
              h('span', { class: 'stat-label' }, '관계')
            ]),
            props.resultLength && h('span', { class: 'stat-divider' }, '·'),
            props.resultLength && h('span', { class: 'stat-size' }, formatSize(props.resultLength))
          ])
        ]),
        props.result.query && h('div', { class: 'header-topic' }, props.result.query),
        props.result.simulationRequirement && h('div', { class: 'header-scenario' }, [
          h('span', { class: 'scenario-label' }, '예측 시나리오:  '),
          h('span', { class: 'scenario-text' }, props.result.simulationRequirement)
        ])
      ]),

      // 탭 내비게이션
      h('div', { class: 'insight-tabs' }, [
        h('button', {
          class: ['insight-tab', { active: activeTab.value === 'facts' }],
          onClick: () => { activeTab.value = 'facts' }
        }, [
          h('span', { class: 'tab-label' }, `현재 핵심 기억 (${props.result.facts.length})`)
        ]),
        h('button', {
          class: ['insight-tab', { active: activeTab.value === 'entities' }],
          onClick: () => { activeTab.value = 'entities' }
        }, [
          h('span', { class: 'tab-label' }, `핵심 엔티티 (${props.result.entities.length})`)
        ]),
        h('button', {
          class: ['insight-tab', { active: activeTab.value === 'relations' }],
          onClick: () => { activeTab.value = 'relations' }
        }, [
          h('span', { class: 'tab-label' }, `관계망 (${props.result.relations.length})`)
        ]),
        props.result.subQueries.length > 0 && h('button', {
          class: ['insight-tab', { active: activeTab.value === 'subqueries' }],
          onClick: () => { activeTab.value = 'subqueries' }
        }, [
          h('span', { class: 'tab-label' }, `하위 질문 (${props.result.subQueries.length})`)
        ])
      ]),

      // 탭 내용
      h('div', { class: 'insight-content' }, [
        // 사실 탭
        activeTab.value === 'facts' && props.result.facts.length > 0 && h('div', { class: 'facts-panel' }, [
          h('div', { class: 'panel-header' }, [
            h('span', { class: 'panel-title' }, '시계열 기억과 연결된 최신 핵심 사실'),
            h('span', { class: 'panel-count' }, `총 ${props.result.facts.length}개`)
          ]),
          h('div', { class: 'facts-list' },
            (expandedFacts.value ? props.result.facts : props.result.facts.slice(0, INITIAL_SHOW_COUNT)).map((fact, i) =>
              h('div', { class: 'fact-item', key: i }, [
                h('span', { class: 'fact-number' }, i + 1),
                h('div', { class: 'fact-content' }, fact)
              ])
            )
          ),
          props.result.facts.length > INITIAL_SHOW_COUNT && h('button', {
            class: 'expand-btn',
            onClick: () => { expandedFacts.value = !expandedFacts.value }
          }, expandedFacts.value ? `접기 ▲` : `전체 보기 ${props.result.facts.length}개 ▼`)
        ]),

        // 엔티티 탭
        activeTab.value === 'entities' && props.result.entities.length > 0 && h('div', { class: 'entities-panel' }, [
          h('div', { class: 'panel-header' }, [
            h('span', { class: 'panel-title' }, '핵심 엔티티'),
            h('span', { class: 'panel-count' }, `총 ${props.result.entities.length}개`)
          ]),
          h('div', { class: 'entities-grid' },
            (expandedEntities.value ? props.result.entities : props.result.entities.slice(0, 12)).map((entity, i) =>
              h('div', { class: 'entity-tag', key: i, title: entity.summary || '' }, [
                h('span', { class: 'entity-name' }, entity.name),
                h('span', { class: 'entity-type' }, entity.type),
                entity.relatedFactsCount > 0 && h('span', { class: 'entity-fact-count' }, `${entity.relatedFactsCount}개`)
              ])
            )
          ),
          props.result.entities.length > 12 && h('button', {
            class: 'expand-btn',
            onClick: () => { expandedEntities.value = !expandedEntities.value }
          }, expandedEntities.value ? `접기 ▲` : `전체 보기 ${props.result.entities.length}개 ▼`)
        ]),

        // 관계 탭
        activeTab.value === 'relations' && props.result.relations.length > 0 && h('div', { class: 'relations-panel' }, [
          h('div', { class: 'panel-header' }, [
            h('span', { class: 'panel-title' }, '관계망'),
            h('span', { class: 'panel-count' }, `총 ${props.result.relations.length}개`)
          ]),
          h('div', { class: 'relations-list' },
            (expandedRelations.value ? props.result.relations : props.result.relations.slice(0, INITIAL_SHOW_COUNT)).map((rel, i) =>
              h('div', { class: 'relation-item', key: i }, [
                h('span', { class: 'rel-source' }, rel.source),
                h('span', { class: 'rel-arrow' }, [
                  h('span', { class: 'rel-line' }),
                  h('span', { class: 'rel-label' }, rel.relation),
                  h('span', { class: 'rel-line' })
                ]),
                h('span', { class: 'rel-target' }, rel.target)
              ])
            )
          ),
          props.result.relations.length > INITIAL_SHOW_COUNT && h('button', {
            class: 'expand-btn',
            onClick: () => { expandedRelations.value = !expandedRelations.value }
          }, expandedRelations.value ? `접기 ▲` : `전체 보기 ${props.result.relations.length}개 ▼`)
        ]),

        // 하위 질문 탭
        activeTab.value === 'subqueries' && props.result.subQueries.length > 0 && h('div', { class: 'subqueries-panel' }, [
          h('div', { class: 'panel-header' }, [
            h('span', { class: 'panel-title' }, '드리프트 질의 생성 분석 하위 질문'),
            h('span', { class: 'panel-count' }, `총 ${props.result.subQueries.length}개`)
          ]),
          h('div', { class: 'subqueries-list' },
            props.result.subQueries.map((sq, i) =>
              h('div', { class: 'subquery-item', key: i }, [
                h('span', { class: 'subquery-number' }, `Q${i + 1}`),
                h('div', { class: 'subquery-text' }, sq)
              ])
            )
          )
        ]),

        // 빈 상태
        activeTab.value === 'facts' && props.result.facts.length === 0 && h('div', { class: 'empty-state' }, '현재 핵심 기억이 없습니다'),
        activeTab.value === 'entities' && props.result.entities.length === 0 && h('div', { class: 'empty-state' }, '핵심 엔티티가 없습니다'),
        activeTab.value === 'relations' && props.result.relations.length === 0 && h('div', { class: 'empty-state' }, '관계망이 없습니다')
      ])
    ])
  }
}

// 파노라마 표시 컴포넌트 - 현재/과거 탭을 강화했습니다
const PanoramaDisplay = {
  props: ['result', 'resultLength'],
  setup(props) {
    const activeTab = ref('active') // 'active', 'historical', 'entities'
    const expandedActive = ref(false)
    const expandedHistorical = ref(false)
    const expandedEntities = ref(false)
    const INITIAL_SHOW_COUNT = 5

    // 표시용 결과 크기를 형식화합니다
    const formatSize = (length) => {
      if (!length) return ''
      if (length >= 1000) {
        return `${(length / 1000).toFixed(1)}천 자`
      }
      return `${length}자`
    }

    return () => h('div', { class: 'panorama-display' }, [
      // 헤더 섹션
      h('div', { class: 'panorama-header' }, [
        h('div', { class: 'header-main' }, [
          h('div', { class: 'header-title' }, '전방위 검색'),
          h('div', { class: 'header-stats' }, [
            h('span', { class: 'stat-item' }, [
              h('span', { class: 'stat-value' }, props.result.stats.nodes),
              h('span', { class: 'stat-label' }, '노드')
            ]),
            h('span', { class: 'stat-divider' }, '/'),
            h('span', { class: 'stat-item' }, [
              h('span', { class: 'stat-value' }, props.result.stats.edges),
              h('span', { class: 'stat-label' }, '간선')
            ]),
            props.resultLength && h('span', { class: 'stat-divider' }, '·'),
            props.resultLength && h('span', { class: 'stat-size' }, formatSize(props.resultLength))
          ])
        ]),
        props.result.query && h('div', { class: 'header-topic' }, props.result.query)
      ]),

      // 탭 내비게이션
      h('div', { class: 'panorama-tabs' }, [
        h('button', {
          class: ['panorama-tab', { active: activeTab.value === 'active' }],
          onClick: () => { activeTab.value = 'active' }
        }, [
          h('span', { class: 'tab-label' }, `현재 유효한 기억 (${props.result.activeFacts.length})`)
        ]),
        h('button', {
          class: ['panorama-tab', { active: activeTab.value === 'historical' }],
          onClick: () => { activeTab.value = 'historical' }
        }, [
          h('span', { class: 'tab-label' }, `과거 기억 (${props.result.historicalFacts.length})`)
        ]),
        h('button', {
          class: ['panorama-tab', { active: activeTab.value === 'entities' }],
          onClick: () => { activeTab.value = 'entities' }
        }, [
          h('span', { class: 'tab-label' }, `관련 엔티티 (${props.result.entities.length})`)
        ])
      ]),

      // 탭 내용
      h('div', { class: 'panorama-content' }, [
        // 현재 사실 탭
        activeTab.value === 'active' && h('div', { class: 'facts-panel active-facts' }, [
          h('div', { class: 'panel-header' }, [
            h('span', { class: 'panel-title' }, '현재 유효한 기억'),
            h('span', { class: 'panel-count' }, `총 ${props.result.activeFacts.length}개`)
          ]),
          props.result.activeFacts.length > 0 ? h('div', { class: 'facts-list' },
            (expandedActive.value ? props.result.activeFacts : props.result.activeFacts.slice(0, INITIAL_SHOW_COUNT)).map((fact, i) =>
              h('div', { class: 'fact-item active', key: i }, [
                h('span', { class: 'fact-number' }, i + 1),
                h('div', { class: 'fact-content' }, fact)
              ])
            )
          ) : h('div', { class: 'empty-state' }, '현재 유효한 기억이 없습니다'),
          props.result.activeFacts.length > INITIAL_SHOW_COUNT && h('button', {
            class: 'expand-btn',
            onClick: () => { expandedActive.value = !expandedActive.value }
          }, expandedActive.value ? `접기 ▲` : `전체 보기 ${props.result.activeFacts.length}개 ▼`)
        ]),

        // 과거 사실 탭
        activeTab.value === 'historical' && h('div', { class: 'facts-panel historical-facts' }, [
          h('div', { class: 'panel-header' }, [
            h('span', { class: 'panel-title' }, '과거 기억'),
            h('span', { class: 'panel-count' }, `총 ${props.result.historicalFacts.length}개`)
          ]),
          props.result.historicalFacts.length > 0 ? h('div', { class: 'facts-list' },
            (expandedHistorical.value ? props.result.historicalFacts : props.result.historicalFacts.slice(0, INITIAL_SHOW_COUNT)).map((fact, i) =>
              h('div', { class: 'fact-item historical', key: i }, [
                h('span', { class: 'fact-number' }, i + 1),
                h('div', { class: 'fact-content' }, [
                  // 시간 정보를 추출해 봅니다 [time - time]
                  (() => {
                    const timeMatch = fact.match(/^\[(.+?)\]\s*(.*)$/)
                    if (timeMatch) {
                      return [
                        h('span', { class: 'fact-time' }, timeMatch[1]),
                        h('span', { class: 'fact-text' }, timeMatch[2])
                      ]
                    }
                    return h('span', { class: 'fact-text' }, fact)
                  })()
                ])
              ])
            )
          ) : h('div', { class: 'empty-state' }, '과거 기억이 없습니다'),
          props.result.historicalFacts.length > INITIAL_SHOW_COUNT && h('button', {
            class: 'expand-btn',
            onClick: () => { expandedHistorical.value = !expandedHistorical.value }
          }, expandedHistorical.value ? `접기 ▲` : `전체 보기 ${props.result.historicalFacts.length}개 ▼`)
        ]),

        // 엔티티 탭
        activeTab.value === 'entities' && h('div', { class: 'entities-panel' }, [
          h('div', { class: 'panel-header' }, [
            h('span', { class: 'panel-title' }, '관련 엔티티'),
            h('span', { class: 'panel-count' }, `총 ${props.result.entities.length}개`)
          ]),
          props.result.entities.length > 0 ? h('div', { class: 'entities-grid' },
            (expandedEntities.value ? props.result.entities : props.result.entities.slice(0, 8)).map((entity, i) =>
              h('div', { class: 'entity-tag', key: i }, [
                h('span', { class: 'entity-name' }, entity.name),
                entity.type && h('span', { class: 'entity-type' }, entity.type)
              ])
            )
          ) : h('div', { class: 'empty-state' }, '관련 엔티티가 없습니다'),
          props.result.entities.length > 8 && h('button', {
            class: 'expand-btn',
            onClick: () => { expandedEntities.value = !expandedEntities.value }
          }, expandedEntities.value ? `접기 ▲` : `전체 보기 ${props.result.entities.length}개 ▼`)
        ])
      ])
    ])
  }
}

// 인터뷰 표시 컴포넌트 - 대화형 스타일(Q&A 형식)
const InterviewDisplay = {
  props: ['result', 'resultLength'],
  setup(props) {
    // 표시용 결과 크기를 형식화합니다
    const formatSize = (length) => {
      if (!length) return ''
      if (length >= 1000) {
        return `${(length / 1000).toFixed(1)}천 자`
      }
      return `${length}자`
    }

    // 인용문 텍스트를 정리합니다 - 앞의 목록 번호를 제거해 중복 번호 매김을 방지합니다
    const cleanQuoteText = (text) => {
      if (!text) return ''
      // "1. ", "2. ", "1、", "（1）", "(1)" 같은 앞부분 패턴을 제거합니다
      return text.replace(/^\s*\d+[\.\、\)）]\s*/, '').trim()
    }

    const activeIndex = ref(0)
    const expandedAnswers = ref(new Set())
    // 각 질문-답변 쌍마다 독립적인 플랫폼 선택 상태를 유지합니다
    const platformTabs = reactive({}) // { 'agentIdx-qIdx': 'twitter' | 'reddit' }

    // 특정 질문의 현재 플랫폼 선택을 가져옵니다
    const getPlatformTab = (agentIdx, qIdx) => {
      const key = `${agentIdx}-${qIdx}`
      return platformTabs[key] || 'twitter'
    }

    // 특정 질문의 플랫폼 선택을 설정합니다
    const setPlatformTab = (agentIdx, qIdx, platform) => {
      const key = `${agentIdx}-${qIdx}`
      platformTabs[key] = platform
    }

    const toggleAnswer = (key) => {
      const newSet = new Set(expandedAnswers.value)
      if (newSet.has(key)) {
        newSet.delete(key)
      } else {
        newSet.add(key)
      }
      expandedAnswers.value = newSet
    }

    const formatAnswer = (text, expanded) => {
      if (!text) return ''
      if (expanded || text.length <= 400) return text
      return text.substring(0, 400) + '...'
    }

    // 플랫폼 자리표시자 텍스트인지 확인합니다
    const isPlaceholderText = (text) => {
      if (!text) return true
      const t = text.trim()
      return (
        t === '(해당 플랫폼에서 응답을 받지 못했습니다)' ||
        t === '（해당 플랫폼에서 응답을 받지 못했습니다）' ||
        t === '（\u8be5\u5e73\u53f0\u672a\u83b7\u5f97\u56de\u590d）' ||
        t === '(\u8be5\u5e73\u53f0\u672a\u83b7\u5f97\u56de\u590d)' ||
        t === '[무응답]' ||
        t === '[\u65e0\u56de\u590d]'
      )
    }

    // 질문 번호를 기준으로 답변을 나눠 봅니다
    const splitAnswerByQuestions = (answerText, questionCount) => {
      if (!answerText || questionCount <= 0) return [answerText]
      if (isPlaceholderText(answerText)) return ['']

      // 두 가지 번호 형식을 지원합니다:
      // 1. "질문X：" 또는 레거시 한자권 형식
      // 2. "1. " 또는 "\n1. "(숫자+점, 구식 형식 호환)
      let matches = []
      let match

      // 먼저 "질문X:" 또는 레거시 한자권 형식을 시도합니다
      const questionPattern = /(?:^|[\r\n]+)(?:질문|\u95ee\u9898)(\d+)[：:]\s*/g
      while ((match = questionPattern.exec(answerText)) !== null) {
        matches.push({
          num: parseInt(match[1]),
          index: match.index,
          fullMatch: match[0]
        })
      }

      // 매칭되지 않으면 "숫자." 형식으로 폴백합니다
      if (matches.length === 0) {
        const numPattern = /(?:^|[\r\n]+)(\d+)\.\s+/g
        while ((match = numPattern.exec(answerText)) !== null) {
          matches.push({
            num: parseInt(match[1]),
            index: match.index,
            fullMatch: match[0]
          })
        }
      }

      // 번호를 찾지 못했거나 하나만 찾으면 전체를 반환합니다
      if (matches.length <= 1) {
        const cleaned = answerText
          .replace(/^(?:질문|\u95ee\u9898)\d+[：:]\s*/, '')
          .replace(/^\d+\.\s+/, '')
          .trim()
        return [cleaned || answerText]
      }

      // 번호에 따라 각 부분을 추출합니다
      const parts = []
      for (let i = 0; i < matches.length; i++) {
        const current = matches[i]
        const next = matches[i + 1]

        const startIdx = current.index + current.fullMatch.length
        const endIdx = next ? next.index : answerText.length

        let part = answerText.substring(startIdx, endIdx).trim()
        part = part.replace(/[\r\n]+$/, '').trim()
        parts.push(part)
      }

      if (parts.length > 0 && parts.some(p => p)) {
        return parts
      }

      return [answerText]
    }

    // 특정 질문에 해당하는 답변을 가져옵니다
    const getAnswerForQuestion = (interview, qIdx, platform) => {
      const answer = platform === 'twitter' ? interview.twitterAnswer : (interview.redditAnswer || interview.twitterAnswer)
      if (!answer || isPlaceholderText(answer)) return answer || ''

      const questionCount = interview.questions?.length || 1
      const answers = splitAnswerByQuestions(answer, questionCount)

      // 분할에 성공했고 인덱스가 유효합니다
      if (answers.length > 1 && qIdx < answers.length) {
        return answers[qIdx] || ''
      }

      // 분할 실패: 첫 번째 질문은 전체 답변을 반환하고, 나머지는 비웁니다
      return qIdx === 0 ? answer : ''
    }

    // 특정 질문에 양 플랫폼 답변이 있는지 확인합니다(자리표시자 제외)
    const hasMultiplePlatforms = (interview, qIdx) => {
      if (!interview.twitterAnswer || !interview.redditAnswer) return false
      const twitterAnswer = getAnswerForQuestion(interview, qIdx, 'twitter')
      const redditAnswer = getAnswerForQuestion(interview, qIdx, 'reddit')
      // 두 플랫폼 모두 실제 답변(자리표시자 아님)이 있고 내용이 다릅니다
      return !isPlaceholderText(twitterAnswer) && !isPlaceholderText(redditAnswer) && twitterAnswer !== redditAnswer
    }

    return () => h('div', { class: 'interview-display' }, [
      // 헤더 섹션
      h('div', { class: 'interview-header' }, [
        h('div', { class: 'header-main' }, [
          h('div', { class: 'header-title' }, '에이전트 인터뷰'),
          h('div', { class: 'header-stats' }, [
            h('span', { class: 'stat-item' }, [
              h('span', { class: 'stat-value' }, props.result.successCount || props.result.interviews.length),
              h('span', { class: 'stat-label' }, '인터뷰 완료')
            ]),
            props.result.totalCount > 0 && h('span', { class: 'stat-divider' }, '/'),
            props.result.totalCount > 0 && h('span', { class: 'stat-item' }, [
              h('span', { class: 'stat-value' }, props.result.totalCount),
              h('span', { class: 'stat-label' }, '전체')
            ]),
            props.resultLength && h('span', { class: 'stat-divider' }, '·'),
            props.resultLength && h('span', { class: 'stat-size' }, formatSize(props.resultLength))
          ])
        ]),
        props.result.topic && h('div', { class: 'header-topic' }, props.result.topic)
      ]),

      // 에이전트 선택 탭
      props.result.interviews.length > 0 && h('div', { class: 'agent-tabs' },
        props.result.interviews.map((interview, i) => h('button', {
          class: ['agent-tab', { active: activeIndex.value === i }],
          key: i,
          onClick: () => { activeIndex.value = i }
        }, [
          h('span', { class: 'tab-avatar' }, interview.name ? interview.name.charAt(0) : (i + 1)),
          h('span', { class: 'tab-name' }, interview.title || interview.name || `에이전트 ${i + 1}`)
        ]))
      ),

      // 활성 인터뷰 상세
      props.result.interviews.length > 0 && h('div', { class: 'interview-detail' }, [
        // 에이전트 프로필 카드
        h('div', { class: 'agent-profile' }, [
          h('div', { class: 'profile-avatar' }, props.result.interviews[activeIndex.value]?.name?.charAt(0) || 'A'),
          h('div', { class: 'profile-info' }, [
            h('div', { class: 'profile-name' }, props.result.interviews[activeIndex.value]?.name || '에이전트'),
            h('div', { class: 'profile-role' }, props.result.interviews[activeIndex.value]?.role || ''),
            props.result.interviews[activeIndex.value]?.bio && h('div', { class: 'profile-bio' }, props.result.interviews[activeIndex.value].bio)
          ])
        ]),

        // 선택 이유
        props.result.interviews[activeIndex.value]?.selectionReason && h('div', { class: 'selection-reason' }, [
          h('div', { class: 'reason-label' }, '선택 이유'),
          h('div', { class: 'reason-content' }, props.result.interviews[activeIndex.value].selectionReason)
        ]),

        // Q&A 대화 스레드 - 한 질문 한 답변 스타일
        h('div', { class: 'qa-thread' },
          (props.result.interviews[activeIndex.value]?.questions?.length > 0
            ? props.result.interviews[activeIndex.value].questions
            : [props.result.interviews[activeIndex.value]?.question || '질문 없음']
          ).map((question, qIdx) => {
            const interview = props.result.interviews[activeIndex.value]
            const currentPlatform = getPlatformTab(activeIndex.value, qIdx)
            const answerText = getAnswerForQuestion(interview, qIdx, currentPlatform)
            const hasDualPlatform = hasMultiplePlatforms(interview, qIdx)
            const expandKey = `${activeIndex.value}-${qIdx}`
            const isExpanded = expandedAnswers.value.has(expandKey)
            const isPlaceholder = isPlaceholderText(answerText)

            return h('div', { class: 'qa-pair', key: qIdx }, [
              // 질문 블록
              h('div', { class: 'qa-question' }, [
                h('div', { class: 'qa-badge q-badge' }, `Q${qIdx + 1}`),
                h('div', { class: 'qa-content' }, [
                  h('div', { class: 'qa-sender' }, '인터뷰어'),
                  h('div', { class: 'qa-text' }, question)
                ])
              ]),

              // 답변 블록
              answerText && h('div', { class: ['qa-answer', { 'answer-placeholder': isPlaceholder }] }, [
                h('div', { class: 'qa-badge a-badge' }, `A${qIdx + 1}`),
                h('div', { class: 'qa-content' }, [
                  h('div', { class: 'qa-answer-header' }, [
                    h('div', { class: 'qa-sender' }, interview?.name || '에이전트'),
                    // 양 플랫폼 전환 버튼(실제 양 플랫폼 답변이 있을 때만 표시)
                    hasDualPlatform && h('div', { class: 'platform-switch' }, [
                      h('button', {
                        class: ['platform-btn', { active: currentPlatform === 'twitter' }],
                        onClick: (e) => { e.stopPropagation(); setPlatformTab(activeIndex.value, qIdx, 'twitter') }
                      }, [
                        h('svg', { class: 'platform-icon', viewBox: '0 0 24 24', width: 12, height: 12, fill: 'none', stroke: 'currentColor', 'stroke-width': 2 }, [
                          h('circle', { cx: '12', cy: '12', r: '10' }),
                          h('line', { x1: '2', y1: '12', x2: '22', y2: '12' }),
                          h('path', { d: 'M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z' })
                        ]),
                        h('span', {}, '세계 1')
                      ]),
                      h('button', {
                        class: ['platform-btn', { active: currentPlatform === 'reddit' }],
                        onClick: (e) => { e.stopPropagation(); setPlatformTab(activeIndex.value, qIdx, 'reddit') }
                      }, [
                        h('svg', { class: 'platform-icon', viewBox: '0 0 24 24', width: 12, height: 12, fill: 'none', stroke: 'currentColor', 'stroke-width': 2 }, [
                          h('path', { d: 'M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z' })
                        ]),
                        h('span', {}, '세계 2')
                      ])
                    ])
                  ]),
                  h('div', {
                    class: ['qa-text', 'answer-text', { 'placeholder-text': isPlaceholder }],
                    innerHTML: isPlaceholder
                      ? answerText
                      : formatAnswer(answerText, isExpanded)
                          .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
                          .replace(/\n/g, '<br>')
                  }),
                  // 펼치기/접기 버튼(자리표시자 텍스트는 표시하지 않음)
                  !isPlaceholder && answerText.length > 400 && h('button', {
                    class: 'expand-answer-btn',
                    onClick: () => toggleAnswer(expandKey)
                  }, isExpanded ? '접기' : '더 보기')
                ])
              ])
            ])
          })
        ),

        // 핵심 인용문 섹션
        props.result.interviews[activeIndex.value]?.quotes?.length > 0 && h('div', { class: 'quotes-section' }, [
          h('div', { class: 'quotes-header' }, '핵심 인용문'),
          h('div', { class: 'quotes-list' },
            props.result.interviews[activeIndex.value].quotes.slice(0, 3).map((quote, qi) => {
              const cleanedQuote = cleanQuoteText(quote)
              const displayQuote = cleanedQuote.length > 200 ? cleanedQuote.substring(0, 200) + '...' : cleanedQuote
              return h('blockquote', {
                key: qi,
                class: 'quote-item',
                innerHTML: renderMarkdown(displayQuote)
              })
            })
          )
        ])
      ]),

      // 요약 섹션(접기 가능)
      props.result.summary && h('div', { class: 'summary-section' }, [
        h('div', { class: 'summary-header' }, '인터뷰 요약'),
        h('div', {
          class: 'summary-content',
          innerHTML: renderMarkdown(props.result.summary.length > 500 ? props.result.summary.substring(0, 500) + '...' : props.result.summary)
        })
      ])
    ])
  }
}

// 빠른 검색 표시 컴포넌트 - 전체 데이터 렌더링을 강화했습니다
const QuickSearchDisplay = {
  props: ['result', 'resultLength'],
  setup(props) {
    const activeTab = ref('facts') // 'facts', 'edges', 'nodes'
    const expandedFacts = ref(false)
    const INITIAL_SHOW_COUNT = 5

    // 탭을 보여줄 간선이나 노드가 있는지 확인합니다
    const hasEdges = computed(() => props.result.edges && props.result.edges.length > 0)
    const hasNodes = computed(() => props.result.nodes && props.result.nodes.length > 0)
    const showTabs = computed(() => hasEdges.value || hasNodes.value)

    // 표시용 결과 크기를 형식화합니다
    const formatSize = (length) => {
      if (!length) return ''
      if (length >= 1000) {
        return `${(length / 1000).toFixed(1)}천 자`
      }
      return `${length}자`
    }

    return () => h('div', { class: 'quick-search-display' }, [
      // 헤더 섹션
      h('div', { class: 'quicksearch-header' }, [
        h('div', { class: 'header-main' }, [
          h('div', { class: 'header-title' }, '빠른 검색'),
          h('div', { class: 'header-stats' }, [
            h('span', { class: 'stat-item' }, [
              h('span', { class: 'stat-value' }, props.result.count || props.result.facts.length),
              h('span', { class: 'stat-label' }, '결과')
            ]),
            props.resultLength && h('span', { class: 'stat-divider' }, '·'),
            props.resultLength && h('span', { class: 'stat-size' }, formatSize(props.resultLength))
          ])
        ]),
        props.result.query && h('div', { class: 'header-query' }, [
          h('span', { class: 'query-label' }, '검색: '),
          h('span', { class: 'query-text' }, props.result.query)
        ])
      ]),

      // 탭 내비게이션(간선이나 노드가 있을 때만 표시)
      showTabs.value && h('div', { class: 'quicksearch-tabs' }, [
        h('button', {
          class: ['quicksearch-tab', { active: activeTab.value === 'facts' }],
          onClick: () => { activeTab.value = 'facts' }
        }, [
          h('span', { class: 'tab-label' }, `사실 (${props.result.facts.length})`)
        ]),
        hasEdges.value && h('button', {
          class: ['quicksearch-tab', { active: activeTab.value === 'edges' }],
          onClick: () => { activeTab.value = 'edges' }
        }, [
          h('span', { class: 'tab-label' }, `관계 (${props.result.edges.length})`)
        ]),
        hasNodes.value && h('button', {
          class: ['quicksearch-tab', { active: activeTab.value === 'nodes' }],
          onClick: () => { activeTab.value = 'nodes' }
        }, [
          h('span', { class: 'tab-label' }, `노드 (${props.result.nodes.length})`)
        ])
      ]),

      // 내용 영역
      h('div', { class: ['quicksearch-content', { 'no-tabs': !showTabs.value }] }, [
        // 사실(탭이 없을 때는 항상, 또는 사실 탭이 활성화되었을 때 표시)
        ((!showTabs.value) || activeTab.value === 'facts') && h('div', { class: 'facts-panel' }, [
          !showTabs.value && h('div', { class: 'panel-header' }, [
            h('span', { class: 'panel-title' }, '검색 결과'),
            h('span', { class: 'panel-count' }, `총 ${props.result.facts.length}개`)
          ]),
          props.result.facts.length > 0 ? h('div', { class: 'facts-list' },
            (expandedFacts.value ? props.result.facts : props.result.facts.slice(0, INITIAL_SHOW_COUNT)).map((fact, i) =>
              h('div', { class: 'fact-item', key: i }, [
                h('span', { class: 'fact-number' }, i + 1),
                h('div', { class: 'fact-content' }, fact)
              ])
            )
          ) : h('div', { class: 'empty-state' }, '관련 결과를 찾지 못했습니다'),
          props.result.facts.length > INITIAL_SHOW_COUNT && h('button', {
            class: 'expand-btn',
            onClick: () => { expandedFacts.value = !expandedFacts.value }
          }, expandedFacts.value ? `접기 ▲` : `전체 보기 ${props.result.facts.length}개 ▼`)
        ]),

        // 간선 탭
        activeTab.value === 'edges' && hasEdges.value && h('div', { class: 'edges-panel' }, [
          h('div', { class: 'panel-header' }, [
            h('span', { class: 'panel-title' }, '관련 관계'),
            h('span', { class: 'panel-count' }, `총 ${props.result.edges.length}개`)
          ]),
          h('div', { class: 'edges-list' },
            props.result.edges.map((edge, i) =>
              h('div', { class: 'edge-item', key: i }, [
                h('span', { class: 'edge-source' }, edge.source),
                h('span', { class: 'edge-arrow' }, [
                  h('span', { class: 'edge-line' }),
                  h('span', { class: 'edge-label' }, edge.relation),
                  h('span', { class: 'edge-line' })
                ]),
                h('span', { class: 'edge-target' }, edge.target)
              ])
            )
          )
        ]),

        // 노드 탭
        activeTab.value === 'nodes' && hasNodes.value && h('div', { class: 'nodes-panel' }, [
          h('div', { class: 'panel-header' }, [
            h('span', { class: 'panel-title' }, '관련 노드'),
            h('span', { class: 'panel-count' }, `총 ${props.result.nodes.length}개`)
          ]),
          h('div', { class: 'nodes-grid' },
            props.result.nodes.map((node, i) =>
              h('div', { class: 'node-tag', key: i }, [
                h('span', { class: 'node-name' }, node.name),
                node.type && h('span', { class: 'node-type' }, node.type)
              ])
            )
          )
        ])
      ])
    ])
  }
}

// 계산 속성
const statusClass = computed(() => {
  if (isComplete.value) return 'completed'
  if (agentLogs.value.length > 0) return 'processing'
  return 'pending'
})

const statusText = computed(() => {
  if (isComplete.value) return '완료'
  if (agentLogs.value.length > 0) return '생성 중...'
  return '대기 중'
})

const totalSections = computed(() => {
  return reportOutline.value?.sections?.length || 0
})

const completedSections = computed(() => {
  return Object.keys(generatedSections.value).length
})

const progressPercent = computed(() => {
  if (totalSections.value === 0) return 0
  return Math.round((completedSections.value / totalSections.value) * 100)
})

const totalToolCalls = computed(() => {
  return agentLogs.value.filter(l => l.action === 'tool_call').length
})

const formatElapsedTime = computed(() => {
  if (!startTime.value) return '0s'
  const lastLog = agentLogs.value[agentLogs.value.length - 1]
  const elapsed = lastLog?.elapsed_seconds || 0
  if (elapsed < 60) return `${Math.round(elapsed)}s`
  const mins = Math.floor(elapsed / 60)
  const secs = Math.round(elapsed % 60)
  return `${mins}m ${secs}s`
})

const displayLogs = computed(() => {
  return agentLogs.value
})

// 워크플로 단계 개요(상태 기반, 중첩 카드 없음)
const activeSectionIndex = computed(() => {
  if (isComplete.value) return null
  if (currentSectionIndex.value) return currentSectionIndex.value
  if (totalSections.value > 0 && completedSections.value < totalSections.value) return completedSections.value + 1
  return null
})

const isPlanningDone = computed(() => {
  return !!reportOutline.value?.sections?.length || agentLogs.value.some(l => l.action === 'planning_complete')
})

const isPlanningStarted = computed(() => {
  return agentLogs.value.some(l => l.action === 'planning_start' || l.action === 'report_start')
})

const isFinalizing = computed(() => {
  return !isComplete.value && isPlanningDone.value && totalSections.value > 0 && completedSections.value >= totalSections.value
})

// 현재 활성 단계(상단 표시용)
const activeStep = computed(() => {
  const steps = workflowSteps.value
  // 현재 활성 단계를 찾습니다
  const active = steps.find(s => s.status === 'active')
  if (active) return active

  // 활성 단계가 없으면 마지막 완료 단계를 반환합니다
  const doneSteps = steps.filter(s => s.status === 'done')
  if (doneSteps.length > 0) return doneSteps[doneSteps.length - 1]

  // 그렇지 않으면 첫 번째 단계를 반환합니다
  return steps[0] || { noLabel: '--', title: '시작 대기', status: 'todo', meta: '' }
})

const workflowSteps = computed(() => {
  const steps = []

  // 기획 / 개요
  const planningStatus = isPlanningDone.value ? 'done' : (isPlanningStarted.value ? 'active' : 'todo')
  steps.push({
    key: 'planning',
    noLabel: 'PL',
    title: '기획 / 개요',
    status: planningStatus,
    meta: planningStatus === 'active' ? '진행 중' : ''
  })

  // 섹션(개요가 있으면)
  const sections = reportOutline.value?.sections || []
  sections.forEach((section, i) => {
    const idx = i + 1
    const status = (isComplete.value || !!generatedSections.value[idx])
      ? 'done'
      : (activeSectionIndex.value === idx ? 'active' : 'todo')

    steps.push({
      key: `section-${idx}`,
      noLabel: String(idx).padStart(2, '0'),
      title: section.title,
      status,
      meta: status === 'active' ? '진행 중' : ''
    })
  })

  // 완료
  const completeStatus = isComplete.value ? 'done' : (isFinalizing.value ? 'active' : 'todo')
  steps.push({
    key: 'complete',
    noLabel: 'OK',
    title: '완료',
    status: completeStatus,
    meta: completeStatus === 'active' ? '마무리 중' : ''
  })

  return steps
})

// 메서드
const addLog = (msg) => {
  emit('add-log', msg)
}

const isSection완료 = (sectionIndex) => {
  return !!generatedSections.value[sectionIndex]
}

const formatTime = (timestamp) => {
  if (!timestamp) return ''
  try {
    return new Date(timestamp).toLocaleTimeString('en-US', {
      hour12: false,
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    })
  } catch {
    return ''
  }
}

const formatParams = (params) => {
  if (!params) return ''
  try {
    return JSON.stringify(params, null, 2)
  } catch {
    return String(params)
  }
}

const formatResultSize = (length) => {
  if (!length) return ''
  if (length < 1000) return `${length}자`
  return `${(length / 1000).toFixed(1)}천 자`
}

const truncateText = (text, maxLen) => {
  if (!text) return ''
  if (text.length <= maxLen) return text
  return text.substring(0, maxLen) + '...'
}

const renderMarkdown = (content) => {
  if (!content) return ''

  // 시작 부분의 2단계 제목(## xxx)을 제거합니다. 섹션 제목은 바깥에서 이미 표시됩니다
  let processedContent = content.replace(/^##\s+.+\n+/, '')

  // 코드 블록을 처리합니다
  let html = processedContent.replace(/```(\w*)\n([\s\S]*?)```/g, '<pre class="code-block"><code>$2</code></pre>')

  // 인라인 코드를 처리합니다
  html = html.replace(/`([^`]+)`/g, '<code class="inline-code">$1</code>')

  // 제목을 처리합니다
  html = html.replace(/^#### (.+)$/gm, '<h5 class="md-h5">$1</h5>')
  html = html.replace(/^### (.+)$/gm, '<h4 class="md-h4">$1</h4>')
  html = html.replace(/^## (.+)$/gm, '<h3 class="md-h3">$1</h3>')
  html = html.replace(/^# (.+)$/gm, '<h2 class="md-h2">$1</h2>')

  // 인용 블록을 처리합니다
  html = html.replace(/^> (.+)$/gm, '<blockquote class="md-quote">$1</blockquote>')

  // 목록을 처리합니다 - 하위 목록을 지원합니다
  html = html.replace(/^(\s*)- (.+)$/gm, (match, indent, text) => {
    const level = Math.floor(indent.length / 2)
    return `<li class="md-li" data-level="${level}">${text}</li>`
  })
  html = html.replace(/^(\s*)(\d+)\. (.+)$/gm, (match, indent, num, text) => {
    const level = Math.floor(indent.length / 2)
    return `<li class="md-oli" data-level="${level}">${text}</li>`
  })

  // 순서 없는 목록을 감쌉니다
  html = html.replace(/(<li class="md-li"[^>]*>.*?<\/li>\s*)+/g, '<ul class="md-ul">$&</ul>')
  // 순서 있는 목록을 감쌉니다
  html = html.replace(/(<li class="md-oli"[^>]*>.*?<\/li>\s*)+/g, '<ol class="md-ol">$&</ol>')

  // 목록 항목 사이의 모든 공백을 정리합니다
  html = html.replace(/<\/li>\s+<li/g, '</li><li')
  // 목록 시작 태그 뒤의 공백을 정리합니다
  html = html.replace(/<ul class="md-ul">\s+/g, '<ul class="md-ul">')
  html = html.replace(/<ol class="md-ol">\s+/g, '<ol class="md-ol">')
  // 목록 종료 태그 앞의 공백을 정리합니다
  html = html.replace(/\s+<\/ul>/g, '</ul>')
  html = html.replace(/\s+<\/ol>/g, '</ol>')

  // 굵게와 기울임을 처리합니다
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
  html = html.replace(/\*(.+?)\*/g, '<em>$1</em>')
  html = html.replace(/_(.+?)_/g, '<em>$1</em>')

  // 구분선을 처리합니다
  html = html.replace(/^---$/gm, '<hr class="md-hr">')

  // 줄바꿈을 처리합니다 - 빈 줄은 문단 구분, 단일 줄바꿈은 <br>로 변환합니다
  html = html.replace(/\n\n/g, '</p><p class="md-p">')
  html = html.replace(/\n/g, '<br>')

  // 문단으로 감쌉니다
  html = '<p class="md-p">' + html + '</p>'

  // 빈 문단을 정리합니다
  html = html.replace(/<p class="md-p"><\/p>/g, '')
  html = html.replace(/<p class="md-p">(<h[2-5])/g, '$1')
  html = html.replace(/(<\/h[2-5]>)<\/p>/g, '$1')
  html = html.replace(/<p class="md-p">(<ul|<ol|<blockquote|<pre|<hr)/g, '$1')
  html = html.replace(/(<\/ul>|<\/ol>|<\/blockquote>|<\/pre>)<\/p>/g, '$1')
  // 블록 요소 앞뒤의 <br> 태그를 정리합니다
  html = html.replace(/<br>\s*(<ul|<ol|<blockquote)/g, '$1')
  html = html.replace(/(<\/ul>|<\/ol>|<\/blockquote>)\s*<br>/g, '$1')
  // 블록 요소 바로 뒤에 붙은 <p><br> 상황을 정리합니다(불필요한 빈 줄 때문)
  html = html.replace(/<p class="md-p">(<br>\s*)+(<ul|<ol|<blockquote|<pre|<hr)/g, '$2')
  // 연속된 <br> 태그를 정리합니다
  html = html.replace(/(<br>\s*){2,}/g, '<br>')
  // 블록 요소 뒤에 바로 이어지는 문단 시작 태그 앞의 <br>을 정리합니다
  html = html.replace(/(<\/ol>|<\/ul>|<\/blockquote>)<br>(<p|<div)/g, '$1$2')

  // 비연속 순서 있는 목록의 번호를 수정합니다. 단일 <ol>이 문단 내용으로 분리되어도 번호를 유지합니다
  const tokens = html.split(/(<ol class="md-ol">(?:<li class="md-oli"[^>]*>[\s\S]*?<\/li>)+<\/ol>)/g)
  let olCounter = 0
  let inSequence = false
  for (let i = 0; i < tokens.length; i++) {
    if (tokens[i].startsWith('<ol class="md-ol">')) {
      const liCount = (tokens[i].match(/<li class="md-oli"/g) || []).length
      if (liCount === 1) {
        olCounter++
        if (olCounter > 1) {
          tokens[i] = tokens[i].replace('<ol class="md-ol">', `<ol class="md-ol" start="${olCounter}">`)
        }
        inSequence = true
      } else {
        olCounter = 0
        inSequence = false
      }
    } else if (inSequence) {
      if (/<h[2-5]/.test(tokens[i])) {
        olCounter = 0
        inSequence = false
      }
    }
  }
  html = tokens.join('')

  return html
}

const getTimelineItemClass = (log, idx, total) => {
  const isLatest = idx === total - 1 && !isComplete.value
  const isMilestone = log.action === 'section_complete' || log.action === 'report_complete'
  return {
    'node--active': isLatest,
    'node--done': !isLatest && isMilestone,
    'node--muted': !isLatest && !isMilestone,
    'node--tool': log.action === 'tool_call' || log.action === 'tool_result'
  }
}

const getConnectorClass = (log, idx, total) => {
  const isLatest = idx === total - 1 && !isComplete.value
  if (isLatest) return 'dot-active'
  if (log.action === 'section_complete' || log.action === 'report_complete') return 'dot-done'
  return 'dot-muted'
}

const getActionLabel = (action) => {
  const labels = {
    'report_start': '보고서 시작',
    'planning_start': '기획',
    'planning_complete': '기획 완료',
    'section_start': '섹션 시작',
    'section_content': '내용 준비',
    'section_complete': '섹션 완료',
    'tool_call': '도구 호출',
    'tool_result': '도구 결과',
    'llm_response': 'LLM 응답',
    'report_complete': '완료'
  }
  return labels[action] || action
}

const getLogLevelClass = (log) => {
  if (log.includes('ERROR') || log.includes('오류')) return 'error'
  if (log.includes('WARNING') || log.includes('경고')) return 'warning'
  // INFO는 기본 색상을 사용하며 success로 표시하지 않습니다
  return ''
}

// 폴링
let agentLogTimer = null
let consoleLogTimer = null

const responseHasToolCall = (response) => {
  if (!response) return false
  if (response.includes('<tool_call>')) return true
  return /"(?:name|tool)"\s*:\s*"(?:insight_forge|panorama_search|quick_search|interview_agents)"/.test(response)
}

const normalizeAgentLog = (log) => {
  if (!log || log.action !== 'llm_response') return log

  const details = { ...(log.details || {}) }
  const response = details.response || ''
  const extractedFinalContent = extractFinalContent(response)

  details.has_tool_calls = Boolean(details.has_tool_calls || responseHasToolCall(response))
  details.has_final_answer = Boolean(details.has_final_answer || extractedFinalContent)

  return {
    ...log,
    details
  }
}

const fetchAgentLog = async () => {
  if (!props.reportId) return

  try {
    const res = await getAgentLog(props.reportId, agentLogLine.value)

    if (res.success && res.data) {
      const newLogs = res.data.logs || []

      if (newLogs.length > 0) {
        newLogs.forEach(rawLog => {
          const log = normalizeAgentLog(rawLog)
          agentLogs.value.push(log)

          if (log.action === 'planning_complete' && log.details?.outline) {
            reportOutline.value = log.details.outline
          }

          if (log.action === 'section_start') {
            currentSectionIndex.value = log.section_index
          }

          // section_complete - 섹션 생성 완료
          if (log.action === 'section_complete') {
            if (log.details?.content) {
              generatedSections.value[log.section_index] = log.details.content
              // 새로 생성된 섹션을 자동으로 펼칩니다
              expandedContent.value.add(log.section_index - 1)
              currentSectionIndex.value = null
            }
          }

          if (log.action === 'report_complete') {
            isComplete.value = true
            currentSectionIndex.value = null  // 로딩 상태가 확실히 지워지도록 합니다
            emit('update-status', 'completed')
            stopPolling()
            // 스크롤 로직은 반복이 끝난 뒤 nextTick에서 일괄 처리합니다
          }

          if (log.action === 'report_start') {
            startTime.value = new Date(log.timestamp)
          }
        })

        agentLogLine.value = res.data.from_line + newLogs.length

        nextTick(() => {
          if (rightPanel.value) {
            // 작업이 완료되면 상단으로, 아니면 하단으로 이동해 최신 로그를 따라갑니다
            if (isComplete.value) {
              rightPanel.value.scrollTop = 0
            } else {
              rightPanel.value.scrollTop = rightPanel.value.scrollHeight
            }
          }
        })
      }
    }
  } catch (err) {
    warnLog('에이전트 로그를 불러오지 못했습니다:', err)
  }
}

// 최종 답변 내용을 추출합니다 - LLM 응답에서 섹션 내용을 추출합니다
const extractFinalContent = (response) => {
  if (!response) return null

  // <final_answer> 태그 안의 내용을 추출해 봅니다
  const finalAnswerTagMatch = response.match(/<final_answer>([\s\S]*?)<\/final_answer>/)
  if (finalAnswerTagMatch) {
    return finalAnswerTagMatch[1].trim()
  }

  // Final Answer: 뒤의 내용을 찾아 봅니다(여러 형식 지원)
  // 형식 1: Final Answer:\n\n내용
  // 형식 2: Final Answer: 내용
  const finalAnswerMatch = response.match(/Final\s*Answer:\s*\n*([\s\S]*)$/i)
  if (finalAnswerMatch) {
    return finalAnswerMatch[1].trim()
  }

  // 최종 답변: 뒤의 내용을 찾아 봅니다
  const koreanFinalMatch = response.match(/최종\s*답변[:：]\s*\n*([\s\S]*)$/i)
  if (koreanFinalMatch) {
    return koreanFinalMatch[1].trim()
  }

  // 최종 답변: 뒤의 내용을 찾아 봅니다
  const legacyFinalMatch = response.match(/\u6700\u7ec8\u7b54\u6848[:：]\s*\n*([\s\S]*)$/i)
  if (legacyFinalMatch) {
    return legacyFinalMatch[1].trim()
  }

  // ##, #, > 로 시작하면 직접 입력된 markdown일 수 있습니다
  const trimmedResponse = response.trim()
  if (trimmedResponse.match(/^[#>]/)) {
    return trimmedResponse
  }

  // 내용이 길고 markdown 형식이 포함되면 사고 과정을 제거한 뒤 반환을 시도합니다
  if (response.length > 300 && (response.includes('**') || response.includes('>'))) {
    // Thought:로 시작하는 사고 과정을 제거합니다
    const thoughtMatch = response.match(/^Thought:[\s\S]*?(?=\n\n[^T]|\n\n$)/i)
    if (thoughtMatch) {
      const afterThought = response.substring(thoughtMatch[0].length).trim()
      if (afterThought.length > 100) {
        return afterThought
      }
    }
  }

  return null
}

const fetchConsoleLog = async () => {
  if (!props.reportId) return

  try {
    const res = await getConsoleLog(props.reportId, consoleLogLine.value)

    if (res.success && res.data) {
      const newLogs = res.data.logs || []

      if (newLogs.length > 0) {
        consoleLogs.value.push(...newLogs)
        consoleLogLine.value = res.data.from_line + newLogs.length

        nextTick(() => {
          if (logContent.value) {
            logContent.value.scrollTop = logContent.value.scrollHeight
          }
        })
      }
    }
  } catch (err) {
    warnLog('콘솔 로그를 불러오지 못했습니다:', err)
  }
}

const startPolling = () => {
  if (agentLogTimer || consoleLogTimer) return

  fetchAgentLog()
  fetchConsoleLog()

  agentLogTimer = setInterval(fetchAgentLog, 2000)
  consoleLogTimer = setInterval(fetchConsoleLog, 1500)
}

const stopPolling = () => {
  if (agentLogTimer) {
    clearInterval(agentLogTimer)
    agentLogTimer = null
  }
  if (consoleLogTimer) {
    clearInterval(consoleLogTimer)
    consoleLogTimer = null
  }
}

onUnmounted(() => {
  stopPolling()
})

watch(() => props.reportId, async (newId) => {
  if (newId) {
    addLog(`보고서 에이전트를 초기화했습니다: ${newId}`)
    resetReportState()
    await loadPersistedReportState()
    startPolling()
  }
}, { immediate: true })
</script>

<style scoped>
.report-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: #F8F9FA;
  font-family: 'Inter', 'Noto Sans KR', system-ui, sans-serif;
  overflow: hidden;
}

/* 메인 분할 레이아웃 */
.main-split-layout {
  flex: 1;
  display: flex;
  overflow: hidden;
}

/* 패널 헤더 */
.panel-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 20px;
  background: #FFFFFF;
  border-bottom: 1px solid #E5E7EB;
  font-size: 13px;
  font-weight: 600;
  color: #374151;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  position: sticky;
  top: 0;
  z-index: 10;
}

.header-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #1F2937;
  box-shadow: 0 0 0 3px rgba(31, 41, 55, 0.15);
  margin-right: 10px;
  flex-shrink: 0;
  animation: pulse-dot 1.5s ease-in-out infinite;
}

@keyframes pulse-dot {
  0%, 100% {
    box-shadow: 0 0 0 3px rgba(31, 41, 55, 0.15);
  }
  50% {
    box-shadow: 0 0 0 5px rgba(31, 41, 55, 0.1);
  }
}

.header-index {
  font-size: 12px;
  font-weight: 600;
  color: #9CA3AF;
  margin-right: 10px;
  flex-shrink: 0;
}

.header-title {
  font-size: 13px;
  font-weight: 600;
  color: #374151;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  text-transform: none;
  letter-spacing: 0;
}

.header-meta {
  margin-left: auto;
  font-size: 10px;
  font-weight: 600;
  color: #6B7280;
  flex-shrink: 0;
}

/* 패널 헤더 상태 변형 */
.panel-header--active {
  background: #FAFAFA;
  border-color: #1F2937;
}

.panel-header--active .header-index {
  color: #1F2937;
}

.panel-header--active .header-title {
  color: #1F2937;
}

.panel-header--active .header-meta {
  color: #1F2937;
}

.panel-header--done {
  background: #F9FAFB;
}

.panel-header--done .header-index {
  color: #10B981;
}

.panel-header--todo .header-index,
.panel-header--todo .header-title {
  color: #9CA3AF;
}

/* 왼쪽 패널 - 보고서 스타일 */
.left-panel.report-style {
  width: 45%;
  min-width: 450px;
  background: #FFFFFF;
  border-right: 1px solid #E5E7EB;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  padding: 30px 50px 60px 50px;
}

.left-panel::-webkit-scrollbar {
  width: 6px;
}

.left-panel::-webkit-scrollbar-track {
  background: transparent;
}

.left-panel::-webkit-scrollbar-thumb {
  background: transparent;
  border-radius: 3px;
  transition: background 0.3s ease;
}

.left-panel:hover::-webkit-scrollbar-thumb {
  background: rgba(0, 0, 0, 0.15);
}

.left-panel::-webkit-scrollbar-thumb:hover {
  background: rgba(0, 0, 0, 0.25);
}

/* 보고서 헤더 */
.report-content-wrapper {
  max-width: 800px;
  margin: 0 auto;
  width: 100%;
}

.report-header-block {
  margin-bottom: 30px;
}

.report-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 24px;
}

.report-tag {
  background: #000000;
  color: #FFFFFF;
  font-size: 11px;
  font-weight: 700;
  padding: 4px 8px;
  letter-spacing: 0.05em;
  text-transform: uppercase;
}

.report-id {
  font-size: 11px;
  color: #9CA3AF;
  font-weight: 500;
  letter-spacing: 0.02em;
}

.main-title {
  font-family: 'Times New Roman', Times, serif;
  font-size: 36px;
  font-weight: 700;
  color: #111827;
  line-height: 1.2;
  margin: 0 0 16px 0;
  letter-spacing: -0.02em;
}

.sub-title {
  font-family: 'Times New Roman', Times, serif;
  font-size: 16px;
  color: #6B7280;
  font-style: italic;
  line-height: 1.6;
  margin: 0 0 30px 0;
  font-weight: 400;
}

.header-divider {
  height: 1px;
  background: #E5E7EB;
  width: 100%;
}

/* 섹션 목록 */
.sections-list {
  display: flex;
  flex-direction: column;
  gap: 32px;
}

.empty-report-state {
  padding: 24px 0;
  border-top: 1px solid #E5E7EB;
  color: #6B7280;
}

.empty-report-state.is-error {
  color: #991B1B;
}

.empty-report-title {
  display: block;
  font-size: 16px;
  font-weight: 600;
  color: inherit;
}

.empty-report-desc {
  margin: 10px 0 0;
  max-width: 620px;
  font-size: 14px;
  line-height: 1.7;
  color: inherit;
}

.report-section-item {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.section-header-row {
  display: flex;
  align-items: baseline;
  gap: 12px;
  transition: background-color 0.2s ease;
  padding: 8px 12px;
  margin: -8px -12px;
  border-radius: 8px;
}

.section-header-row.clickable {
  cursor: pointer;
}

.section-header-row.clickable:hover {
  background-color: #F9FAFB;
}

.collapse-icon {
  margin-left: auto;
  color: #9CA3AF;
  transition: transform 0.3s ease;
  flex-shrink: 0;
  align-self: center;
}

.collapse-icon.is-collapsed {
  transform: rotate(-90deg);
}

.section-number {
  font-family: 'JetBrains Mono', monospace;
  font-size: 16px;
  color: #9CA3AF; /* 진회색, 상태에 따라 변하지 않습니다 */
  font-weight: 500;
}

.section-title {
  font-family: 'Times New Roman', Times, serif;
  font-size: 24px;
  font-weight: 600;
  color: #111827;
  margin: 0;
  transition: color 0.3s ease;
}

/* 상태 */
.report-section-item.is-pending .section-title {
  color: #D1D5DB;
}

.report-section-item.is-active .section-title,
.report-section-item.is-completed .section-title {
  color: #111827;
}

.section-body {
  padding-left: 28px;
  overflow: hidden;
}

/* 생성된 콘텐츠 */
.generated-content {
  font-family: 'Inter', 'Noto Sans KR', system-ui, sans-serif;
  font-size: 14px;
  line-height: 1.8;
  color: #374151;
}

.generated-content :deep(p) {
  margin-bottom: 1em;
}

.generated-content :deep(.md-h2),
.generated-content :deep(.md-h3),
.generated-content :deep(.md-h4) {
  font-family: 'Times New Roman', Times, serif;
  color: #111827;
  margin-top: 1.5em;
  margin-bottom: 0.8em;
  font-weight: 700;
}

.generated-content :deep(.md-h2) { font-size: 20px; border-bottom: 1px solid #F3F4F6; padding-bottom: 8px; }
.generated-content :deep(.md-h3) { font-size: 18px; }
.generated-content :deep(.md-h4) { font-size: 16px; }

.generated-content :deep(.md-ul),
.generated-content :deep(.md-ol) {
  padding-left: 24px;
  margin: 12px 0;
}

.generated-content :deep(.md-li),
.generated-content :deep(.md-oli) {
  margin: 6px 0;
}

.generated-content :deep(.md-quote) {
  border-left: 3px solid #E5E7EB;
  padding-left: 16px;
  margin: 1.5em 0;
  color: #6B7280;
  font-style: italic;
  font-family: 'Times New Roman', Times, serif;
}

.generated-content :deep(.code-block) {
  background: #F9FAFB;
  padding: 12px;
  border-radius: 6px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  overflow-x: auto;
  margin: 1em 0;
  border: 1px solid #E5E7EB;
}

.generated-content :deep(strong) {
  font-weight: 600;
  color: #111827;
}

/* 로딩 상태 */
.loading-state {
  display: flex;
  align-items: center;
  gap: 10px;
  color: #6B7280;
  font-size: 14px;
  margin-top: 4px;
}

.loading-icon {
  width: 18px;
  height: 18px;
  animation: spin 1s linear infinite;
  display: flex;
  align-items: center;
  justify-content: center;
}

.loading-text {
  font-family: 'Times New Roman', Times, serif;
  font-size: 15px;
  color: #4B5563;
}

.cursor-blink {
  display: inline-block;
  width: 8px;
  height: 14px;
  background: #8B5CF6;
  opacity: 0.5;
  animation: blink 1s step-end infinite;
}

@keyframes blink {
  0%, 100% { opacity: 0.5; }
  50% { opacity: 0; }
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* 이 뷰의 콘텐츠 스타일 덮어쓰기 */
.generated-content :deep(.md-h2) {
  font-family: 'Times New Roman', Times, serif;
  font-size: 18px;
  margin-top: 0;
}


/* 슬라이드 콘텐츠 전환 */
.slide-content-enter-active {
  transition: opacity 0.3s ease-out;
}

.slide-content-leave-active {
  transition: opacity 0.2s ease-in;
}

.slide-content-enter-from,
.slide-content-leave-to {
  opacity: 0;
}

.slide-content-enter-to,
.slide-content-leave-from {
  opacity: 1;
}

/* 대기 중 자리표시자 */
.waiting-placeholder {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 20px;
  padding: 40px;
  color: #9CA3AF;
}

.waiting-animation {
  position: relative;
  width: 48px;
  height: 48px;
}

.waiting-ring {
  position: absolute;
  width: 100%;
  height: 100%;
  border: 2px solid #E5E7EB;
  border-radius: 50%;
  animation: ripple 2s cubic-bezier(0.4, 0, 0.2, 1) infinite;
}

.waiting-ring:nth-child(2) {
  animation-delay: 0.4s;
}

.waiting-ring:nth-child(3) {
  animation-delay: 0.8s;
}

@keyframes ripple {
  0% { transform: scale(0.5); opacity: 1; }
  100% { transform: scale(2); opacity: 0; }
}

.waiting-text {
  font-size: 14px;
}

/* 오른쪽 패널 */
.right-panel {
  flex: 1;
  background: #FFFFFF;
  overflow-y: auto;
  display: flex;
  flex-direction: column;

  /* 기능 팔레트(저채도, 상태 기반) */
  --wf-border: #E5E7EB;
  --wf-divider: #F3F4F6;

  --wf-active-bg: #FAFAFA;
  --wf-active-border: #1F2937;
  --wf-active-dot: #1F2937;
  --wf-active-text: #1F2937;

  --wf-done-bg: #F9FAFB;
  --wf-done-border: #E5E7EB;
  --wf-done-dot: #10B981;

  --wf-muted-dot: #D1D5DB;
  --wf-todo-text: #9CA3AF;
}

.right-panel::-webkit-scrollbar {
  width: 6px;
}

.right-panel::-webkit-scrollbar-track {
  background: transparent;
}

.right-panel::-webkit-scrollbar-thumb {
  background: transparent;
  border-radius: 3px;
  transition: background 0.3s ease;
}

.right-panel:hover::-webkit-scrollbar-thumb {
  background: rgba(0, 0, 0, 0.15);
}

.right-panel::-webkit-scrollbar-thumb:hover {
  background: rgba(0, 0, 0, 0.25);
}

.mono {
  font-family: 'JetBrains Mono', monospace;
}

/* 워크플로 개요 */
.workflow-overview {
  padding: 16px 20px 0 20px;
}

.workflow-metrics {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}

.metric {
  display: inline-flex;
  align-items: baseline;
  gap: 6px;
}

.metric-right {
  margin-left: auto;
}

.metric-label {
  font-size: 11px;
  font-weight: 600;
  color: #9CA3AF;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.metric-value {
  font-size: 12px;
  color: #374151;
}

.metric-pill {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  padding: 4px 10px;
  border-radius: 999px;
  border: 1px solid var(--wf-border);
  background: #F9FAFB;
  color: #6B7280;
}

.metric-pill.pill--processing {
  background: var(--wf-active-bg);
  border-color: var(--wf-active-border);
  color: var(--wf-active-text);
}

.metric-pill.pill--completed {
  background: #ECFDF5;
  border-color: #A7F3D0;
  color: #065F46;
}

.metric-pill.pill--pending {
  background: transparent;
  border-style: dashed;
  color: #6B7280;
}

.workflow-steps {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding-bottom: 10px;
}

.wf-step {
  display: grid;
  grid-template-columns: 24px 1fr;
  gap: 12px;
  padding: 10px 12px;
  border: 1px solid var(--wf-divider);
  border-radius: 8px;
  background: #FFFFFF;
}

.wf-step--active {
  background: var(--wf-active-bg);
  border-color: var(--wf-active-border);
}

.wf-step--done {
  background: var(--wf-done-bg);
  border-color: var(--wf-done-border);
}

.wf-step--todo {
  background: transparent;
  border-color: var(--wf-border);
  border-style: dashed;
}

.wf-step-connector {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 24px;
  flex-shrink: 0;
}

.wf-step-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: var(--wf-muted-dot);
  border: 2px solid #FFFFFF;
  z-index: 1;
}

.wf-step-line {
  width: 2px;
  flex: 1;
  background: var(--wf-divider);
  margin-top: -2px;
}

.wf-step--active .wf-step-dot {
  background: var(--wf-active-dot);
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.12);
}

.wf-step--done .wf-step-dot {
  background: var(--wf-done-dot);
}

.wf-step-title-row {
  display: flex;
  align-items: baseline;
  gap: 10px;
  min-width: 0;
}

.wf-step-index {
  font-size: 11px;
  font-weight: 700;
  color: #9CA3AF;
  letter-spacing: 0.02em;
  flex-shrink: 0;
}

.wf-step-title {
  font-family: 'Times New Roman', Times, serif;
  font-size: 13px;
  font-weight: 600;
  color: #111827;
  line-height: 1.35;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.wf-step-meta {
  margin-left: auto;
  font-size: 10px;
  font-weight: 700;
  color: var(--wf-active-text);
  text-transform: uppercase;
  letter-spacing: 0.04em;
  flex-shrink: 0;
}

.wf-step--todo .wf-step-title,
.wf-step--todo .wf-step-index {
  color: var(--wf-todo-text);
}

.workflow-divider {
  height: 1px;
  background: var(--wf-divider);
  margin: 14px 0 0 0;
}

/* 워크플로 타임라인 */
.workflow-timeline {
  padding: 14px 20px 24px;
  flex: 1;
}

.timeline-item {
  display: grid;
  grid-template-columns: 24px 1fr;
  gap: 12px;
  padding: 10px 12px;
  margin-bottom: 10px;
  border: 1px solid var(--wf-divider);
  border-radius: 8px;
  background: #FFFFFF;
  transition: background-color 0.15s ease, border-color 0.15s ease;
}

.timeline-item:hover {
  background: #F9FAFB;
  border-color: var(--wf-border);
}

.timeline-item.node--active {
  background: var(--wf-active-bg);
  border-color: var(--wf-active-border);
}

.timeline-item.node--active:hover {
  background: var(--wf-active-bg);
  border-color: var(--wf-active-border);
}

.timeline-item.node--done {
  background: var(--wf-done-bg);
  border-color: var(--wf-done-border);
}

.timeline-item.node--done:hover {
  background: var(--wf-done-bg);
  border-color: var(--wf-done-border);
}

.timeline-connector {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 24px;
  flex-shrink: 0;
}

.connector-dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: var(--wf-muted-dot);
  border: 2px solid #FFFFFF;
  z-index: 1;
}

.connector-line {
  width: 2px;
  flex: 1;
  background: var(--wf-divider);
  margin-top: -2px;
}

/* 연결 점: 상태만 표시 */
.dot-active {
  background: var(--wf-active-dot);
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.12);
}

.dot-done {
  background: var(--wf-done-dot);
}

.dot-muted {
  background: var(--wf-muted-dot);
}

.timeline-content {
  min-width: 0;
  background: transparent;
  border: none;
  border-radius: 0;
  padding: 0;
  margin: 0;
  transition: none;
}

.timeline-content:hover {
  box-shadow: none;
}

.timeline-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.action-label {
  font-size: 12px;
  font-weight: 600;
  color: #374151;
  text-transform: uppercase;
  letter-spacing: 0.03em;
}

.action-time {
  font-size: 11px;
  color: #9CA3AF;
  font-family: 'JetBrains Mono', monospace;
}

.timeline-body {
  font-size: 13px;
  color: #4B5563;
}

.timeline-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px solid #F3F4F6;
}

.elapsed-placeholder {
  flex-shrink: 0;
}

.footer-actions {
  display: flex;
  gap: 8px;
  margin-left: auto;
}

.elapsed-badge {
  font-size: 11px;
  color: #6B7280;
  background: #F3F4F6;
  padding: 2px 8px;
  border-radius: 10px;
  font-family: 'JetBrains Mono', monospace;
}

/* 타임라인 본문 요소 */
.info-row {
  display: flex;
  gap: 8px;
  margin-bottom: 6px;
}

.info-key {
  font-size: 11px;
  color: #9CA3AF;
  min-width: 80px;
}

.info-val {
  color: #374151;
}

.status-message {
  padding: 8px 12px;
  border-radius: 6px;
  font-size: 13px;
  border: 1px solid transparent;
}

.status-message.planning {
  background: var(--wf-active-bg);
  border-color: var(--wf-active-border);
  color: var(--wf-active-text);
}

.status-message.success {
  background: #ECFDF5;
  border-color: #A7F3D0;
  color: #065F46;
}

.outline-badge {
  display: inline-block;
  margin-top: 8px;
  padding: 4px 10px;
  background: #F9FAFB;
  color: #6B7280;
  border: 1px solid #E5E7EB;
  border-radius: 12px;
  font-size: 11px;
  font-weight: 500;
}

.section-tag {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  background: #F9FAFB;
  border: 1px solid var(--wf-border);
  border-radius: 6px;
}

.section-tag.content-ready {
  background: var(--wf-active-bg);
  border: 1px dashed var(--wf-active-border);
}

.section-tag.content-ready svg {
  color: var(--wf-active-dot);
}


.section-tag.completed {
  background: #ECFDF5;
  border: 1px solid #A7F3D0;
}

.section-tag.completed svg {
  color: #059669;
}

.tag-num {
  font-size: 11px;
  font-weight: 700;
  color: #6B7280;
}

.section-tag.completed .tag-num {
  color: #059669;
}

.tag-title {
  font-size: 13px;
  font-weight: 500;
  color: #374151;
}

.tool-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  background: #F9FAFB;
  color: #374151;
  border: 1px solid var(--wf-border);
  border-radius: 6px;
  font-size: 12px;
  font-weight: 600;
  transition: all 0.2s ease;
}

.tool-icon {
  flex-shrink: 0;
}

/* 도구 색상 - 보라색(심층 분석) */
.tool-badge.tool-purple {
  background: linear-gradient(135deg, #F5F3FF 0%, #EDE9FE 100%);
  border-color: #C4B5FD;
  color: #6D28D9;
}
.tool-badge.tool-purple .tool-icon {
  stroke: #7C3AED;
}

/* 도구 색상 - 파란색(전방위 검색) */
.tool-badge.tool-blue {
  background: linear-gradient(135deg, #EFF6FF 0%, #DBEAFE 100%);
  border-color: #93C5FD;
  color: #1D4ED8;
}
.tool-badge.tool-blue .tool-icon {
  stroke: #2563EB;
}

/* 도구 색상 - 초록색(에이전트 인터뷰) */
.tool-badge.tool-green {
  background: linear-gradient(135deg, #F0FDF4 0%, #DCFCE7 100%);
  border-color: #86EFAC;
  color: #15803D;
}
.tool-badge.tool-green .tool-icon {
  stroke: #16A34A;
}

/* 도구 색상 - 주황색(빠른 검색) */
.tool-badge.tool-orange {
  background: linear-gradient(135deg, #FFF7ED 0%, #FFEDD5 100%);
  border-color: #FDBA74;
  color: #C2410C;
}
.tool-badge.tool-orange .tool-icon {
  stroke: #EA580C;
}

/* 도구 색상 - 청록색(그래프 통계) */
.tool-badge.tool-cyan {
  background: linear-gradient(135deg, #ECFEFF 0%, #CFFAFE 100%);
  border-color: #67E8F9;
  color: #0E7490;
}
.tool-badge.tool-cyan .tool-icon {
  stroke: #0891B2;
}

/* 도구 색상 - 분홍색(엔티티 조회) */
.tool-badge.tool-pink {
  background: linear-gradient(135deg, #FDF2F8 0%, #FCE7F3 100%);
  border-color: #F9A8D4;
  color: #BE185D;
}
.tool-badge.tool-pink .tool-icon {
  stroke: #DB2777;
}

/* 도구 색상 - 회색(기본) */
.tool-badge.tool-gray {
  background: linear-gradient(135deg, #F9FAFB 0%, #F3F4F6 100%);
  border-color: #D1D5DB;
  color: #374151;
}
.tool-badge.tool-gray .tool-icon {
  stroke: #6B7280;
}

.tool-params {
  margin-top: 10px;
  background: transparent;
  border-radius: 0;
  padding: 10px 0 0 0;
  border-top: 1px dashed var(--wf-divider);
  overflow-x: auto;
}

.tool-params pre {
  margin: 0;
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  color: #4B5563;
  white-space: pre-wrap;
  word-break: break-all;
  background: #F9FAFB;
  border: 1px solid #E5E7EB;
  border-radius: 6px;
  padding: 10px;
}

/* 통합 동작 버튼 */
.action-btn {
  background: #F3F4F6;
  border: 1px solid #E5E7EB;
  padding: 4px 10px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 500;
  color: #6B7280;
  cursor: pointer;
  transition: all 0.15s ease;
  white-space: nowrap;
}

.action-btn:hover {
  background: #E5E7EB;
  color: #374151;
  border-color: #D1D5DB;
}

/* 결과 래퍼 */
.result-wrapper {
  background: transparent;
  border: none;
  border-top: 1px solid var(--wf-divider);
  border-radius: 0;
  padding: 12px 0 0 0;
}

.result-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.result-tool {
  font-size: 12px;
  font-weight: 600;
  color: #374151;
}

.result-size {
  font-size: 10px;
  color: #6B7280;
  font-family: 'JetBrains Mono', monospace;
}

.result-raw {
  margin-top: 10px;
  max-height: 300px;
  overflow-y: auto;
}

.result-raw pre {
  margin: 0;
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  white-space: pre-wrap;
  word-break: break-word;
  color: #374151;
  background: #FFFFFF;
  border: 1px solid #E5E7EB;
  padding: 10px;
  border-radius: 6px;
}

.raw-preview {
  margin: 0;
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  white-space: pre-wrap;
  word-break: break-word;
  color: #6B7280;
}

/* 이전 toggle-raw는 제거했고 통합된 .action-btn를 사용합니다 */

/* LLM 응답 */
.llm-meta {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.meta-tag {
  font-size: 11px;
  padding: 3px 8px;
  background: #F3F4F6;
  color: #6B7280;
  border-radius: 4px;
}

.meta-tag.active {
  background: #DBEAFE;
  color: #1E40AF;
}

.meta-tag.final-answer {
  background: #D1FAE5;
  color: #059669;
  font-weight: 600;
}

.final-answer-hint {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 10px;
  padding: 10px 14px;
  background: #ECFDF5;
  border: 1px solid #A7F3D0;
  border-radius: 6px;
  color: #065F46;
  font-size: 12px;
  font-weight: 500;
}

.final-answer-hint svg {
  flex-shrink: 0;
}

.llm-content {
  margin-top: 10px;
  max-height: 200px;
  overflow-y: auto;
}

.llm-content pre {
  margin: 0;
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  white-space: pre-wrap;
  word-break: break-word;
  color: #4B5563;
  background: #F3F4F6;
  padding: 10px;
  border-radius: 6px;
}

/* 완료 배너 */
.complete-banner {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  background: #ECFDF5;
  border: 1px solid #A7F3D0;
  border-radius: 8px;
  color: #065F46;
  font-weight: 600;
  font-size: 14px;
}

.next-step-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  width: calc(100% - 40px);
  margin: 4px 20px 0 20px;
  padding: 14px 20px;
  font-size: 14px;
  font-weight: 600;
  color: #FFFFFF;
  background: #1F2937;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.next-step-btn:hover {
  background: #374151;
}

.next-step-btn svg {
  transition: transform 0.2s ease;
}

.next-step-btn:hover svg {
  transform: translateX(4px);
}

/* 워크플로 비어 있음 */
.workflow-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  color: #9CA3AF;
  font-size: 13px;
}

.empty-pulse {
  width: 24px;
  height: 24px;
  background: #E5E7EB;
  border-radius: 50%;
  margin-bottom: 16px;
  animation: pulse-ring 1.5s infinite;
}

@keyframes pulse-ring {
  0%, 100% { transform: scale(1); opacity: 1; }
  50% { transform: scale(1.2); opacity: 0.5; }
}

/* 타임라인 전환 */
.timeline-item-enter-active {
  transition: all 0.4s ease;
}

.timeline-item-enter-from {
  opacity: 0;
  transform: translateX(-20px);
}

/* ========== 구조화된 결과 표시 컴포넌트 ========== */

/* 공통 스타일 - 동적 컴포넌트에는 :deep()을 사용합니다 */
:deep(.stat-row) {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}

:deep(.stat-box) {
  flex: 1;
  background: #FFFFFF;
  border: 1px solid #E5E7EB;
  border-radius: 6px;
  padding: 10px 8px;
  text-align: center;
}

:deep(.stat-box .stat-num) {
  display: block;
  font-size: 20px;
  font-weight: 700;
  color: #111827;
  font-family: 'JetBrains Mono', monospace;
}

:deep(.stat-box .stat-label) {
  display: block;
  font-size: 10px;
  color: #9CA3AF;
  margin-top: 2px;
  text-transform: uppercase;
  letter-spacing: 0.03em;
}

:deep(.stat-box.highlight) {
  background: #ECFDF5;
  border-color: #A7F3D0;
}

:deep(.stat-box.highlight .stat-num) {
  color: #059669;
}

:deep(.stat-box.muted) {
  background: #F9FAFB;
  border-color: #E5E7EB;
}

:deep(.stat-box.muted .stat-num) {
  color: #6B7280;
}

:deep(.query-display) {
  background: #F9FAFB;
  padding: 10px 14px;
  border-radius: 6px;
  font-size: 12px;
  color: #374151;
  margin-bottom: 12px;
  border: 1px solid #E5E7EB;
  line-height: 1.5;
}

:deep(.expand-details) {
  background: #FFFFFF;
  border: 1px solid #E5E7EB;
  padding: 8px 14px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 500;
  color: #6B7280;
  cursor: pointer;
  transition: all 0.15s ease;
}

:deep(.expand-details:hover) {
  border-color: #D1D5DB;
  color: #374151;
}

:deep(.detail-content) {
  margin-top: 14px;
  background: #FFFFFF;
  border: 1px solid #E5E7EB;
  border-radius: 8px;
  padding: 14px;
}

:deep(.section-label) {
  font-size: 11px;
  font-weight: 600;
  color: #6B7280;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  margin-bottom: 10px;
  padding-bottom: 6px;
  border-bottom: 1px solid #F3F4F6;
}

/* 사실 섹션 */
:deep(.facts-section) {
  margin-bottom: 14px;
}

:deep(.fact-row) {
  display: flex;
  gap: 10px;
  padding: 8px 0;
  border-bottom: 1px solid #F3F4F6;
}

:deep(.fact-row:last-child) {
  border-bottom: none;
}

:deep(.fact-row.active) {
  background: #ECFDF5;
  margin: 0 -10px;
  padding: 8px 10px;
  border-radius: 6px;
  border-bottom: none;
}

:deep(.fact-idx) {
  min-width: 22px;
  height: 22px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #F3F4F6;
  border-radius: 6px;
  font-size: 10px;
  font-weight: 700;
  color: #6B7280;
  flex-shrink: 0;
}

:deep(.fact-row.active .fact-idx) {
  background: #A7F3D0;
  color: #065F46;
}

:deep(.fact-text) {
  font-size: 12px;
  color: #4B5563;
  line-height: 1.6;
}

/* 엔티티 섹션 */
:deep(.entities-section) {
  margin-bottom: 14px;
}

:deep(.entity-chips) {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

:deep(.entity-chip) {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: #F9FAFB;
  border: 1px solid #E5E7EB;
  border-radius: 6px;
  padding: 6px 12px;
}

:deep(.chip-name) {
  font-size: 12px;
  font-weight: 500;
  color: #111827;
}

:deep(.chip-type) {
  font-size: 10px;
  color: #9CA3AF;
  background: #E5E7EB;
  padding: 1px 6px;
  border-radius: 3px;
}

/* 관계 섹션 */
:deep(.relations-section) {
  margin-bottom: 14px;
}

:deep(.relation-row) {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 0;
  flex-wrap: wrap;
  border-bottom: 1px solid #F3F4F6;
}

:deep(.relation-row:last-child) {
  border-bottom: none;
}

:deep(.rel-node) {
  font-size: 12px;
  font-weight: 500;
  color: #111827;
  background: #F3F4F6;
  padding: 4px 10px;
  border-radius: 4px;
}

:deep(.rel-edge) {
  font-size: 10px;
  font-weight: 600;
  color: #FFFFFF;
  background: #4F46E5;
  padding: 3px 10px;
  border-radius: 10px;
}

/* ========== 인터뷰 표시 - 대화형 스타일 ========== */
:deep(.interview-display) {
  padding: 0;
}

/* 헤더 */
:deep(.interview-display .interview-header) {
  padding: 0;
  background: transparent;
  border-bottom: none;
  margin-bottom: 16px;
}

:deep(.interview-display .header-main) {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

:deep(.interview-display .header-title) {
  font-family: 'JetBrains Mono', monospace;
  font-size: 13px;
  font-weight: 600;
  color: #111827;
  letter-spacing: -0.01em;
}

:deep(.interview-display .header-stats) {
  display: flex;
  align-items: center;
  gap: 6px;
}

:deep(.interview-display .stat-item) {
  display: flex;
  align-items: baseline;
  gap: 4px;
}

:deep(.interview-display .stat-value) {
  font-size: 14px;
  font-weight: 600;
  color: #4F46E5;
  font-family: 'JetBrains Mono', monospace;
}

:deep(.interview-display .stat-label) {
  font-size: 11px;
  color: #9CA3AF;
  text-transform: lowercase;
}

:deep(.interview-display .stat-divider) {
  color: #D1D5DB;
  font-size: 12px;
}

:deep(.interview-display .stat-size) {
  font-size: 11px;
  color: #9CA3AF;
  font-family: 'JetBrains Mono', monospace;
}

:deep(.interview-display .header-topic) {
  margin-top: 4px;
  font-size: 12px;
  color: #6B7280;
  line-height: 1.5;
}

/* 에이전트 탭 - 카드 스타일 */
:deep(.interview-display .agent-tabs) {
  display: flex;
  gap: 8px;
  padding: 0 0 14px 0;
  background: transparent;
  border-bottom: 1px solid #F3F4F6;
  overflow-x: auto;
  overflow-y: hidden;
  scrollbar-width: thin;
  scrollbar-color: #E5E7EB transparent;
}

:deep(.interview-display .agent-tabs::-webkit-scrollbar) {
  height: 4px;
}

:deep(.interview-display .agent-tabs::-webkit-scrollbar-track) {
  background: transparent;
}

:deep(.interview-display .agent-tabs::-webkit-scrollbar-thumb) {
  background: #E5E7EB;
  border-radius: 2px;
}

:deep(.interview-display .agent-tabs::-webkit-scrollbar-thumb:hover) {
  background: #D1D5DB;
}

:deep(.interview-display .agent-tab) {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  background: #F9FAFB;
  border: 1px solid #E5E7EB;
  border-radius: 8px;
  font-size: 12px;
  font-weight: 500;
  color: #6B7280;
  cursor: pointer;
  transition: all 0.15s ease;
  white-space: nowrap;
}

:deep(.interview-display .agent-tab:hover) {
  background: #F3F4F6;
  border-color: #D1D5DB;
  color: #374151;
}

:deep(.interview-display .agent-tab.active) {
  background: linear-gradient(135deg, #EEF2FF 0%, #E0E7FF 100%);
  border-color: #A5B4FC;
  color: #4338CA;
  box-shadow: 0 1px 2px rgba(99, 102, 241, 0.1);
}

:deep(.interview-display .tab-avatar) {
  width: 18px;
  height: 18px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #E5E7EB;
  color: #6B7280;
  font-size: 10px;
  font-weight: 700;
  border-radius: 50%;
  flex-shrink: 0;
}

:deep(.interview-display .agent-tab:hover .tab-avatar) {
  background: #D1D5DB;
}

:deep(.interview-display .agent-tab.active .tab-avatar) {
  background: #6366F1;
  color: #FFFFFF;
}

:deep(.interview-display .tab-name) {
  max-width: 100px;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* 인터뷰 상세 */
:deep(.interview-display .interview-detail) {
  padding: 12px 0;
  background: transparent;
}

/* 에이전트 프로필 - 카드 없음 */
:deep(.interview-display .agent-profile) {
  display: flex;
  gap: 12px;
  padding: 0;
  background: transparent;
  border: none;
  margin-bottom: 16px;
}

:deep(.interview-display .profile-avatar) {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #E5E7EB;
  color: #6B7280;
  font-size: 14px;
  font-weight: 600;
  border-radius: 50%;
  flex-shrink: 0;
}

:deep(.interview-display .profile-info) {
  flex: 1;
  min-width: 0;
}

:deep(.interview-display .profile-name) {
  font-size: 13px;
  font-weight: 600;
  color: #111827;
  margin-bottom: 2px;
}

:deep(.interview-display .profile-role) {
  font-size: 11px;
  color: #6B7280;
  margin-bottom: 4px;
}

:deep(.interview-display .profile-bio) {
  font-size: 11px;
  color: #9CA3AF;
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* 선택 이유 */
:deep(.interview-display .selection-reason) {
  background: #F8FAFC;
  border: 1px solid #E2E8F0;
  border-radius: 8px;
  padding: 12px 14px;
  margin-bottom: 16px;
}

:deep(.interview-display .reason-label) {
  font-size: 11px;
  font-weight: 600;
  color: #64748B;
  text-transform: uppercase;
  letter-spacing: 0.03em;
  margin-bottom: 6px;
}

:deep(.interview-display .reason-content) {
  font-size: 12px;
  color: #475569;
  line-height: 1.6;
}

/* Q&A 스레드 - 깔끔한 목록 */
:deep(.interview-display .qa-thread) {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

:deep(.interview-display .qa-pair) {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 0;
  background: transparent;
  border: none;
  border-radius: 0;
}

:deep(.interview-display .qa-question),
:deep(.interview-display .qa-answer) {
  display: flex;
  gap: 12px;
}

:deep(.interview-display .qa-badge) {
  width: 20px;
  height: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: 'JetBrains Mono', monospace;
  font-size: 10px;
  font-weight: 700;
  border-radius: 4px;
  flex-shrink: 0;
}

:deep(.interview-display .q-badge) {
  background: transparent;
  color: #9CA3AF;
  border: 1px solid #E5E7EB;
}

:deep(.interview-display .a-badge) {
  background: #4F46E5;
  color: #FFFFFF;
  border: 1px solid #4F46E5;
}

:deep(.interview-display .qa-content) {
  flex: 1;
  min-width: 0;
}

:deep(.interview-display .qa-sender) {
  font-size: 11px;
  font-weight: 600;
  color: #9CA3AF;
  margin-bottom: 4px;
  text-transform: uppercase;
  letter-spacing: 0.03em;
}

:deep(.interview-display .qa-text) {
  font-size: 13px;
  color: #374151;
  line-height: 1.6;
}

:deep(.interview-display .qa-answer) {
  background: transparent;
  padding: 0;
  border: none;
  margin-top: 0;
}

:deep(.interview-display .answer-placeholder) {
  opacity: 0.6;
}

:deep(.interview-display .placeholder-text) {
  font-style: italic;
  color: #9CA3AF;
}

:deep(.interview-display .qa-answer-header) {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}

/* 플랫폼 전환 */
:deep(.interview-display .platform-switch) {
  display: flex;
  gap: 2px;
  background: transparent;
  padding: 0;
  border-radius: 0;
}

:deep(.interview-display .platform-btn) {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 2px 6px;
  background: transparent;
  border: 1px solid transparent;
  border-radius: 4px;
  font-size: 10px;
  font-weight: 500;
  color: #9CA3AF;
  cursor: pointer;
  transition: all 0.15s ease;
}

:deep(.interview-display .platform-btn:hover) {
  color: #6B7280;
}

:deep(.interview-display .platform-btn.active) {
  background: transparent;
  color: #4F46E5;
  border-color: #E5E7EB;
  box-shadow: none;
}

:deep(.interview-display .platform-icon) {
  flex-shrink: 0;
}

:deep(.interview-display .answer-text) {
  font-size: 13px;
  color: #111827;
  line-height: 1.6;
}

:deep(.interview-display .answer-text strong) {
  color: #111827;
  font-weight: 600;
}

:deep(.interview-display .expand-answer-btn) {
  display: inline-block;
  margin-top: 8px;
  padding: 0;
  background: transparent;
  border: none;
  border-bottom: 1px dotted #D1D5DB;
  border-radius: 0;
  font-size: 11px;
  font-weight: 500;
  color: #9CA3AF;
  cursor: pointer;
  transition: all 0.15s ease;
}

:deep(.interview-display .expand-answer-btn:hover) {
  background: transparent;
  color: #6B7280;
  border-bottom-style: solid;
}

/* 인용문 섹션 - 깔끔한 목록 */
:deep(.interview-display .quotes-section) {
  background: transparent;
  border: none;
  border-top: 1px solid #F3F4F6;
  border-radius: 0;
  padding: 16px 0 0 0;
  margin-top: 16px;
}

:deep(.interview-display .quotes-header) {
  font-size: 11px;
  font-weight: 600;
  color: #9CA3AF;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  margin-bottom: 12px;
}

:deep(.interview-display .quotes-list) {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

:deep(.interview-display .quote-item) {
  margin: 0;
  padding: 10px 12px;
  background: #FFFFFF;
  border: 1px solid #E5E7EB;
  border-radius: 6px;
  font-size: 12px;
  font-style: italic;
  color: #4B5563;
  line-height: 1.5;
}

/* 요약 섹션 */
:deep(.interview-display .summary-section) {
  margin-top: 20px;
  padding: 16px 0 0 0;
  background: transparent;
  border: none;
  border-top: 1px solid #F3F4F6;
  border-radius: 0;
}

:deep(.interview-display .summary-header) {
  font-size: 11px;
  font-weight: 600;
  color: #9CA3AF;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  margin-bottom: 8px;
}

:deep(.interview-display .summary-content) {
  font-size: 13px;
  color: #374151;
  line-height: 1.6;
}

/* 요약의 마크다운 스타일 */
:deep(.interview-display .summary-content h2),
:deep(.interview-display .summary-content h3),
:deep(.interview-display .summary-content h4),
:deep(.interview-display .summary-content h5) {
  margin: 12px 0 8px 0;
  font-weight: 600;
  color: #111827;
}

:deep(.interview-display .summary-content h2) {
  font-size: 15px;
}

:deep(.interview-display .summary-content h3) {
  font-size: 14px;
}

:deep(.interview-display .summary-content h4),
:deep(.interview-display .summary-content h5) {
  font-size: 13px;
}

:deep(.interview-display .summary-content p) {
  margin: 8px 0;
}

:deep(.interview-display .summary-content strong) {
  font-weight: 600;
  color: #111827;
}

:deep(.interview-display .summary-content em) {
  font-style: italic;
}

:deep(.interview-display .summary-content ul),
:deep(.interview-display .summary-content ol) {
  margin: 8px 0;
  padding-left: 20px;
}

:deep(.interview-display .summary-content li) {
  margin: 4px 0;
}

:deep(.interview-display .summary-content blockquote) {
  margin: 8px 0;
  padding-left: 12px;
  border-left: 3px solid #E5E7EB;
  color: #6B7280;
  font-style: italic;
}

/* 인용문의 마크다운 스타일 */
:deep(.interview-display .quote-item strong) {
  font-weight: 600;
  color: #374151;
}

:deep(.interview-display .quote-item em) {
  font-style: italic;
}

/* ========== 강화된 인사이트 표시 스타일 ========== */
:deep(.insight-display) {
  padding: 0;
}

:deep(.insight-header) {
  padding: 12px 16px;
  background: linear-gradient(135deg, #F5F3FF 0%, #EDE9FE 100%);
  border-radius: 8px 8px 0 0;
  border: 1px solid #C4B5FD;
  border-bottom: none;
}

:deep(.insight-header .header-main) {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

:deep(.insight-header .header-title) {
  font-size: 14px;
  font-weight: 700;
  color: #6D28D9;
}

:deep(.insight-header .header-stats) {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
}

:deep(.insight-header .stat-item) {
  display: flex;
  align-items: baseline;
  gap: 2px;
}

:deep(.insight-header .stat-value) {
  font-family: 'JetBrains Mono', monospace;
  font-weight: 700;
  color: #7C3AED;
}

:deep(.insight-header .stat-label) {
  color: #8B5CF6;
  font-size: 10px;
}

:deep(.insight-header .stat-divider) {
  color: #C4B5FD;
  margin: 0 4px;
}

:deep(.insight-header .stat-size) {
  font-family: 'JetBrains Mono', monospace;
  font-size: 10px;
  color: #9CA3AF;
}

:deep(.insight-header .header-topic) {
  font-size: 13px;
  color: #5B21B6;
  line-height: 1.5;
}

:deep(.insight-header .header-scenario) {
  margin-top: 6px;
  font-size: 11px;
  color: #7C3AED;
}

:deep(.insight-header .scenario-label) {
  font-weight: 600;
}

:deep(.insight-tabs) {
  display: flex;
  gap: 2px;
  padding: 8px 12px;
  background: #FAFAFA;
  border: 1px solid #E5E7EB;
  border-top: none;
}

:deep(.insight-tab) {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 10px;
  background: transparent;
  border: 1px solid transparent;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 500;
  color: #6B7280;
  cursor: pointer;
  transition: all 0.15s ease;
}

:deep(.insight-tab:hover) {
  background: #F3F4F6;
  color: #374151;
}

:deep(.insight-tab.active) {
  background: #FFFFFF;
  color: #7C3AED;
  border-color: #C4B5FD;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
}


:deep(.insight-content) {
  padding: 12px;
  background: #FFFFFF;
  border: 1px solid #E5E7EB;
  border-top: none;
  border-radius: 0 0 8px 8px;
}

:deep(.insight-display .panel-header) {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid #F3F4F6;
}

:deep(.insight-display .panel-title) {
  font-size: 12px;
  font-weight: 600;
  color: #374151;
}

:deep(.insight-display .panel-count) {
  font-size: 10px;
  color: #9CA3AF;
}

:deep(.insight-display .facts-list),
:deep(.insight-display .relations-list),
:deep(.insight-display .subqueries-list) {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

:deep(.insight-display .entities-grid) {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

:deep(.insight-display .fact-item) {
  display: flex;
  gap: 10px;
  padding: 10px 12px;
  background: #F9FAFB;
  border: 1px solid #E5E7EB;
  border-radius: 6px;
}

:deep(.insight-display .fact-number) {
  flex-shrink: 0;
  width: 20px;
  height: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #E5E7EB;
  border-radius: 50%;
  font-family: 'JetBrains Mono', monospace;
  font-size: 10px;
  font-weight: 700;
  color: #6B7280;
}

:deep(.insight-display .fact-content) {
  flex: 1;
  font-size: 12px;
  color: #374151;
  line-height: 1.6;
}

/* 엔티티 태그 스타일 - 컴팩트한 다열 레이아웃 */
:deep(.insight-display .entity-tag) {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 8px;
  background: #F9FAFB;
  border: 1px solid #E5E7EB;
  border-radius: 6px;
  cursor: default;
  transition: all 0.15s ease;
}

:deep(.insight-display .entity-tag:hover) {
  background: #F3F4F6;
  border-color: #D1D5DB;
}

:deep(.insight-display .entity-tag .entity-name) {
  font-size: 12px;
  font-weight: 500;
  color: #111827;
}

:deep(.insight-display .entity-tag .entity-type) {
  font-size: 9px;
  color: #7C3AED;
  background: #EDE9FE;
  padding: 1px 4px;
  border-radius: 3px;
}

:deep(.insight-display .entity-tag .entity-fact-count) {
  font-size: 9px;
  color: #9CA3AF;
  margin-left: 2px;
}

/* 이전 버전 호환성을 위한 기존 엔티티 카드 스타일 */
:deep(.insight-display .entity-card) {
  padding: 12px;
  background: #F9FAFB;
  border: 1px solid #E5E7EB;
  border-radius: 8px;
}

:deep(.insight-display .entity-header) {
  display: flex;
  align-items: center;
  gap: 10px;
}

:deep(.insight-display .entity-info) {
  flex: 1;
}

:deep(.insight-display .entity-card .entity-name) {
  font-size: 13px;
  font-weight: 600;
  color: #111827;
}

:deep(.insight-display .entity-card .entity-type) {
  font-size: 10px;
  color: #7C3AED;
  background: #EDE9FE;
  padding: 2px 6px;
  border-radius: 4px;
  display: inline-block;
  margin-top: 2px;
}

:deep(.insight-display .entity-card .entity-fact-count) {
  font-size: 10px;
  color: #9CA3AF;
  background: #F3F4F6;
  padding: 2px 6px;
  border-radius: 4px;
}

:deep(.insight-display .entity-summary) {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid #E5E7EB;
  font-size: 11px;
  color: #6B7280;
  line-height: 1.5;
}

/* 관계 항목 스타일 */
:deep(.insight-display .relation-item) {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  background: #F9FAFB;
  border: 1px solid #E5E7EB;
  border-radius: 6px;
}

:deep(.insight-display .rel-source),
:deep(.insight-display .rel-target) {
  padding: 4px 8px;
  background: #FFFFFF;
  border: 1px solid #D1D5DB;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 500;
  color: #374151;
}

:deep(.insight-display .rel-arrow) {
  display: flex;
  align-items: center;
  gap: 4px;
  flex: 1;
}

:deep(.insight-display .rel-line) {
  flex: 1;
  height: 1px;
  background: #D1D5DB;
}

:deep(.insight-display .rel-label) {
  padding: 2px 6px;
  background: #EDE9FE;
  border-radius: 4px;
  font-size: 10px;
  font-weight: 500;
  color: #7C3AED;
  white-space: nowrap;
}

/* 하위 질의 스타일 */
:deep(.insight-display .subquery-item) {
  display: flex;
  gap: 10px;
  padding: 10px 12px;
  background: #F9FAFB;
  border: 1px solid #E5E7EB;
  border-radius: 6px;
}

:deep(.insight-display .subquery-number) {
  flex-shrink: 0;
  padding: 2px 6px;
  background: #7C3AED;
  border-radius: 4px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 10px;
  font-weight: 700;
  color: #FFFFFF;
}

:deep(.insight-display .subquery-text) {
  font-size: 12px;
  color: #374151;
  line-height: 1.5;
}

/* 펼치기 버튼 */
:deep(.insight-display .expand-btn),
:deep(.panorama-display .expand-btn),
:deep(.quick-search-display .expand-btn) {
  display: block;
  width: 100%;
  margin-top: 12px;
  padding: 8px 12px;
  background: #F9FAFB;
  border: 1px solid #E5E7EB;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 500;
  color: #6B7280;
  cursor: pointer;
  transition: all 0.15s ease;
  text-align: center;
}

:deep(.insight-display .expand-btn:hover),
:deep(.panorama-display .expand-btn:hover),
:deep(.quick-search-display .expand-btn:hover) {
  background: #F3F4F6;
  color: #374151;
  border-color: #D1D5DB;
}

/* 빈 상태 */
:deep(.insight-display .empty-state),
:deep(.panorama-display .empty-state),
:deep(.quick-search-display .empty-state) {
  padding: 24px;
  text-align: center;
  font-size: 12px;
  color: #9CA3AF;
}

/* ========== 강화된 파노라마 표시 스타일 ========== */
:deep(.panorama-display) {
  padding: 0;
}

:deep(.panorama-header) {
  padding: 12px 16px;
  background: linear-gradient(135deg, #EFF6FF 0%, #DBEAFE 100%);
  border-radius: 8px 8px 0 0;
  border: 1px solid #93C5FD;
  border-bottom: none;
}

:deep(.panorama-header .header-main) {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

:deep(.panorama-header .header-title) {
  font-size: 14px;
  font-weight: 700;
  color: #1D4ED8;
}

:deep(.panorama-header .header-stats) {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
}

:deep(.panorama-header .stat-item) {
  display: flex;
  align-items: baseline;
  gap: 2px;
}

:deep(.panorama-header .stat-value) {
  font-family: 'JetBrains Mono', monospace;
  font-weight: 700;
  color: #2563EB;
}

:deep(.panorama-header .stat-label) {
  color: #60A5FA;
  font-size: 10px;
}

:deep(.panorama-header .stat-divider) {
  color: #93C5FD;
  margin: 0 4px;
}

:deep(.panorama-header .stat-size) {
  font-family: 'JetBrains Mono', monospace;
  font-size: 10px;
  color: #9CA3AF;
}

:deep(.panorama-header .header-topic) {
  font-size: 13px;
  color: #1E40AF;
  line-height: 1.5;
}

:deep(.panorama-tabs) {
  display: flex;
  gap: 2px;
  padding: 8px 12px;
  background: #FAFAFA;
  border: 1px solid #E5E7EB;
  border-top: none;
}

:deep(.panorama-tab) {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 10px;
  background: transparent;
  border: 1px solid transparent;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 500;
  color: #6B7280;
  cursor: pointer;
  transition: all 0.15s ease;
}

:deep(.panorama-tab:hover) {
  background: #F3F4F6;
  color: #374151;
}

:deep(.panorama-tab.active) {
  background: #FFFFFF;
  color: #2563EB;
  border-color: #93C5FD;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
}


:deep(.panorama-content) {
  padding: 12px;
  background: #FFFFFF;
  border: 1px solid #E5E7EB;
  border-top: none;
  border-radius: 0 0 8px 8px;
}

:deep(.panorama-display .panel-header) {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid #F3F4F6;
}

:deep(.panorama-display .panel-title) {
  font-size: 12px;
  font-weight: 600;
  color: #374151;
}

:deep(.panorama-display .panel-count) {
  font-size: 10px;
  color: #9CA3AF;
}

:deep(.panorama-display .facts-list) {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

:deep(.panorama-display .fact-item) {
  display: flex;
  gap: 10px;
  padding: 10px 12px;
  background: #F9FAFB;
  border: 1px solid #E5E7EB;
  border-radius: 6px;
}

:deep(.panorama-display .fact-item.active) {
  background: #F9FAFB;
  border-color: #E5E7EB;
}

:deep(.panorama-display .fact-item.historical) {
  background: #F9FAFB;
  border-color: #E5E7EB;
}

:deep(.panorama-display .fact-number) {
  flex-shrink: 0;
  width: 20px;
  height: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #E5E7EB;
  border-radius: 50%;
  font-family: 'JetBrains Mono', monospace;
  font-size: 10px;
  font-weight: 700;
  color: #6B7280;
}

:deep(.panorama-display .fact-item.active .fact-number) {
  background: #E5E7EB;
  color: #6B7280;
}

:deep(.panorama-display .fact-item.historical .fact-number) {
  background: #9CA3AF;
  color: #FFFFFF;
}

:deep(.panorama-display .fact-content) {
  flex: 1;
  font-size: 12px;
  color: #374151;
  line-height: 1.6;
}

:deep(.panorama-display .fact-time) {
  display: block;
  font-size: 10px;
  color: #9CA3AF;
  margin-bottom: 4px;
  font-family: 'JetBrains Mono', monospace;
}

:deep(.panorama-display .fact-text) {
  display: block;
}

/* 엔티티 그리드 */
:deep(.panorama-display .entities-grid) {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

:deep(.panorama-display .entity-tag) {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  background: #F9FAFB;
  border: 1px solid #E5E7EB;
  border-radius: 6px;
}

:deep(.panorama-display .entity-name) {
  font-size: 12px;
  font-weight: 500;
  color: #374151;
}

:deep(.panorama-display .entity-type) {
  font-size: 10px;
  color: #2563EB;
  background: #DBEAFE;
  padding: 2px 6px;
  border-radius: 4px;
}

/* ========== 강화된 빠른 검색 표시 스타일 ========== */
:deep(.quick-search-display) {
  padding: 0;
}

:deep(.quicksearch-header) {
  padding: 12px 16px;
  background: linear-gradient(135deg, #FFF7ED 0%, #FFEDD5 100%);
  border-radius: 8px 8px 0 0;
  border: 1px solid #FDBA74;
  border-bottom: none;
}

:deep(.quicksearch-header .header-main) {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

:deep(.quicksearch-header .header-title) {
  font-size: 14px;
  font-weight: 700;
  color: #C2410C;
}

:deep(.quicksearch-header .header-stats) {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
}

:deep(.quicksearch-header .stat-item) {
  display: flex;
  align-items: baseline;
  gap: 2px;
}

:deep(.quicksearch-header .stat-value) {
  font-family: 'JetBrains Mono', monospace;
  font-weight: 700;
  color: #EA580C;
}

:deep(.quicksearch-header .stat-label) {
  color: #FB923C;
  font-size: 10px;
}

:deep(.quicksearch-header .stat-divider) {
  color: #FDBA74;
  margin: 0 4px;
}

:deep(.quicksearch-header .stat-size) {
  font-family: 'JetBrains Mono', monospace;
  font-size: 10px;
  color: #9CA3AF;
}

:deep(.quicksearch-header .header-query) {
  font-size: 13px;
  color: #9A3412;
  line-height: 1.5;
}

:deep(.quicksearch-header .query-label) {
  font-weight: 600;
}

:deep(.quicksearch-tabs) {
  display: flex;
  gap: 2px;
  padding: 8px 12px;
  background: #FAFAFA;
  border: 1px solid #E5E7EB;
  border-top: none;
}

:deep(.quicksearch-tab) {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 10px;
  background: transparent;
  border: 1px solid transparent;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 500;
  color: #6B7280;
  cursor: pointer;
  transition: all 0.15s ease;
}

:deep(.quicksearch-tab:hover) {
  background: #F3F4F6;
  color: #374151;
}

:deep(.quicksearch-tab.active) {
  background: #FFFFFF;
  color: #EA580C;
  border-color: #FDBA74;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
}


:deep(.quicksearch-content) {
  padding: 12px;
  background: #FFFFFF;
  border: 1px solid #E5E7EB;
  border-top: none;
  border-radius: 0 0 8px 8px;
}

/* 탭이 없으면 내용이 헤더와 바로 연결됩니다 */
:deep(.quicksearch-content.no-tabs) {
  border-top: none;
}

:deep(.quick-search-display .panel-header) {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid #F3F4F6;
}

:deep(.quick-search-display .panel-title) {
  font-size: 12px;
  font-weight: 600;
  color: #374151;
}

:deep(.quick-search-display .panel-count) {
  font-size: 10px;
  color: #9CA3AF;
}

:deep(.quick-search-display .facts-list) {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

:deep(.quick-search-display .fact-item) {
  display: flex;
  gap: 10px;
  padding: 10px 12px;
  background: #F9FAFB;
  border: 1px solid #E5E7EB;
  border-radius: 6px;
}

:deep(.quick-search-display .fact-item.active) {
  background: #F9FAFB;
  border-color: #E5E7EB;
}

:deep(.quick-search-display .fact-number) {
  flex-shrink: 0;
  width: 20px;
  height: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #E5E7EB;
  border-radius: 50%;
  font-family: 'JetBrains Mono', monospace;
  font-size: 10px;
  font-weight: 700;
  color: #6B7280;
}

:deep(.quick-search-display .fact-item.active .fact-number) {
  background: #E5E7EB;
  color: #6B7280;
}

:deep(.quick-search-display .fact-content) {
  flex: 1;
  font-size: 12px;
  color: #374151;
  line-height: 1.6;
}

/* 간선 패널 */
:deep(.quick-search-display .edges-list) {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

:deep(.quick-search-display .edge-item) {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  background: #F9FAFB;
  border: 1px solid #E5E7EB;
  border-radius: 6px;
}

:deep(.quick-search-display .edge-source),
:deep(.quick-search-display .edge-target) {
  padding: 4px 8px;
  background: #FFFFFF;
  border: 1px solid #D1D5DB;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 500;
  color: #374151;
}

:deep(.quick-search-display .edge-arrow) {
  display: flex;
  align-items: center;
  gap: 4px;
  flex: 1;
}

:deep(.quick-search-display .edge-line) {
  flex: 1;
  height: 1px;
  background: #D1D5DB;
}

:deep(.quick-search-display .edge-label) {
  padding: 2px 6px;
  background: #FFEDD5;
  border-radius: 4px;
  font-size: 10px;
  font-weight: 500;
  color: #C2410C;
  white-space: nowrap;
}

/* 노드 그리드 */
:deep(.quick-search-display .nodes-grid) {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

:deep(.quick-search-display .node-tag) {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  background: #F9FAFB;
  border: 1px solid #E5E7EB;
  border-radius: 6px;
}

:deep(.quick-search-display .node-name) {
  font-size: 12px;
  font-weight: 500;
  color: #374151;
}

:deep(.quick-search-display .node-type) {
  font-size: 10px;
  color: #EA580C;
  background: #FFEDD5;
  padding: 2px 6px;
  border-radius: 4px;
}

/* 콘솔 로그 - Step3Simulation.vue와 일치시킵니다 */
.console-logs {
  background: #000;
  color: #DDD;
  padding: 16px;
  font-family: 'JetBrains Mono', monospace;
  border-top: 1px solid #222;
  flex-shrink: 0;
}

.log-header {
  display: flex;
  justify-content: space-between;
  border-bottom: 1px solid #333;
  padding-bottom: 8px;
  margin-bottom: 8px;
  font-size: 10px;
  color: #666;
}

.log-title {
  text-transform: uppercase;
  letter-spacing: 0.1em;
}

.log-content {
  display: flex;
  flex-direction: column;
  gap: 4px;
  height: 100px;
  overflow-y: auto;
  padding-right: 4px;
}

.log-content::-webkit-scrollbar { width: 4px; }
.log-content::-webkit-scrollbar-thumb { background: #333; border-radius: 2px; }

.log-line {
  font-size: 11px;
  line-height: 1.5;
}

.log-msg {
  color: #BBB;
  word-break: break-all;
}

.log-msg.error { color: #EF5350; }
.log-msg.warning { color: #FFA726; }
.log-msg.success { color: #66BB6A; }
</style>
