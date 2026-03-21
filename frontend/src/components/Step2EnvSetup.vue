<template>
  <div class="env-setup-panel">
    <div class="scroll-container">
      <!-- 1단계: 시뮬레이션 인스턴스 -->
      <div class="step-card" :class="{ 'active': phase === 0, 'completed': phase > 0 }">
        <div class="card-header">
          <div class="step-info">
            <span class="step-num">01</span>
            <span class="step-title">시뮬레이션 인스턴스 초기화</span>
          </div>
          <div class="step-status">
            <span v-if="phase > 0" class="badge success">완료</span>
            <span v-else class="badge processing">초기화 중</span>
          </div>
        </div>

        <div class="card-content">
          <p class="api-note">POST /api/simulation/create</p>
          <p class="description">
            새 시뮬레이션 인스턴스를 생성하고 시뮬레이션 세계 파라미터 템플릿을 불러옵니다.
          </p>

          <div v-if="simulationId" class="info-card">
            <div class="info-row">
              <span class="info-label">프로젝트 ID</span>
              <span class="info-value mono">{{ projectData?.project_id }}</span>
            </div>
            <div class="info-row">
              <span class="info-label">그래프 ID</span>
              <span class="info-value mono">{{ projectData?.graph_id }}</span>
            </div>
            <div class="info-row">
              <span class="info-label">시뮬레이션 ID</span>
              <span class="info-value mono">{{ simulationId }}</span>
            </div>
            <div class="info-row">
              <span class="info-label">작업 ID</span>
              <span class="info-value mono">{{ taskId || '비동기 작업 완료' }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 2단계: 에이전트 페르소나 생성 -->
      <div class="step-card" :class="{ 'active': phase === 1, 'completed': phase > 1 }">
        <div class="card-header">
          <div class="step-info">
            <span class="step-num">02</span>
            <span class="step-title">에이전트 페르소나 생성</span>
          </div>
          <div class="step-status">
            <span v-if="phase > 1" class="badge success">완료</span>
            <span v-else-if="phase === 1" class="badge processing">{{ prepareProgress }}%</span>
            <span v-else class="badge pending">대기 중</span>
          </div>
        </div>

        <div class="card-content">
          <p class="api-note">POST /api/simulation/prepare</p>
          <p class="description">
            문맥을 바탕으로 도구를 자동 호출해 지식 그래프의 엔터티와 관계를 정리하고, 시뮬레이션 개체를 초기화한 뒤 현실 시드를 기반으로 고유한 행동과 기억을 부여합니다.
          </p>

          <!-- 프로필 통계 -->
          <div v-if="profiles.length > 0" class="stats-grid">
            <div class="stat-card">
              <span class="stat-value">{{ profiles.length }}</span>
              <span class="stat-label">현재 에이전트 수</span>
            </div>
            <div class="stat-card">
              <span class="stat-value">{{ expectedTotal || '-' }}</span>
              <span class="stat-label">예상 총 에이전트 수</span>
            </div>
            <div class="stat-card">
              <span class="stat-value">{{ totalTopicsCount }}</span>
              <span class="stat-label">현재 현실 시드 연관 주제 수</span>
            </div>
          </div>

          <!-- 프로필 목록 미리보기 -->
          <div v-if="profiles.length > 0" class="profiles-preview">
            <div class="preview-header">
              <span class="preview-title">생성된 에이전트 페르소나</span>
            </div>
            <div class="profiles-list">
              <div
                v-for="(profile, idx) in profiles"
                :key="idx"
                class="profile-card"
                @click="selectProfile(profile)"
              >
                <div class="profile-header">
                  <span class="profile-realname">{{ profile.username || '알 수 없음' }}</span>
                  <span class="profile-username">@{{ profile.name || `agent_${idx}` }}</span>
                </div>
                <div class="profile-meta">
                  <span class="profile-profession">{{ profile.profession || '알 수 없는 직업' }}</span>
                </div>
                <p class="profile-bio">{{ profile.bio || '소개 없음' }}</p>
                <div v-if="profile.interested_topics?.length" class="profile-topics">
                  <span
                    v-for="topic in profile.interested_topics.slice(0, 3)"
                    :key="topic"
                    class="topic-tag"
                  >{{ topic }}</span>
                  <span v-if="profile.interested_topics.length > 3" class="topic-more">
                    +{{ profile.interested_topics.length - 3 }}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 3단계: 양 플랫폼 시뮬레이션 설정 생성 -->
      <div class="step-card" :class="{ 'active': phase === 2, 'completed': phase > 2 }">
        <div class="card-header">
          <div class="step-info">
            <span class="step-num">03</span>
            <span class="step-title">양 플랫폼 시뮬레이션 설정 생성</span>
          </div>
          <div class="step-status">
            <span v-if="phase > 2" class="badge success">완료</span>
            <span v-else-if="phase === 2" class="badge processing">생성 중</span>
            <span v-else class="badge pending">대기 중</span>
          </div>
        </div>

        <div class="card-content">
          <p class="api-note">POST /api/simulation/prepare</p>
          <p class="description">
            LLM이 시뮬레이션 요구사항과 현실 시드를 바탕으로 세계 시간 흐름 속도, 추천 알고리즘, 각 개체의 활성 시간대, 발언 빈도, 이벤트 트리거 등의 매개변수를 지능적으로 설정합니다.
          </p>

          <!-- 설정 미리보기 -->
          <div v-if="simulationConfig" class="config-detail-panel">
            <!-- 시간 설정 -->
            <div class="config-block">
              <div class="config-grid">
                <div class="config-item">
                  <span class="config-item-label">시뮬레이션 시간</span>
                  <span class="config-item-value">{{ simulationConfig.time_config?.total_simulation_hours || '-' }} 시간</span>
                </div>
                <div class="config-item">
                  <span class="config-item-label">회차당 시간</span>
                  <span class="config-item-value">{{ simulationConfig.time_config?.minutes_per_round || '-' }} 분</span>
                </div>
                <div class="config-item">
                  <span class="config-item-label">총 회차</span>
                  <span class="config-item-value">{{ Math.floor((simulationConfig.time_config?.total_simulation_hours * 60 / simulationConfig.time_config?.minutes_per_round)) || '-' }}회</span>
                </div>
                <div class="config-item">
                  <span class="config-item-label">시간당 활성 수</span>
                  <span class="config-item-value">{{ simulationConfig.time_config?.agents_per_hour_min }}-{{ simulationConfig.time_config?.agents_per_hour_max }}</span>
                </div>
              </div>
              <div class="time-periods">
                <div class="period-item">
                  <span class="period-label">피크 시간대</span>
                  <span class="period-hours">{{ simulationConfig.time_config?.peak_hours?.join(':00, ') }}:00</span>
                  <span class="period-multiplier">×{{ simulationConfig.time_config?.peak_activity_multiplier }}</span>
                </div>
                <div class="period-item">
                  <span class="period-label">근무 시간대</span>
                  <span class="period-hours">{{ simulationConfig.time_config?.work_hours?.[0] }}:00-{{ simulationConfig.time_config?.work_hours?.slice(-1)[0] }}:00</span>
                  <span class="period-multiplier">×{{ simulationConfig.time_config?.work_activity_multiplier }}</span>
                </div>
                <div class="period-item">
                  <span class="period-label">아침 시간대</span>
                  <span class="period-hours">{{ simulationConfig.time_config?.morning_hours?.[0] }}:00-{{ simulationConfig.time_config?.morning_hours?.slice(-1)[0] }}:00</span>
                  <span class="period-multiplier">×{{ simulationConfig.time_config?.morning_activity_multiplier }}</span>
                </div>
                <div class="period-item">
                  <span class="period-label">비활성 시간대</span>
                  <span class="period-hours">{{ simulationConfig.time_config?.off_peak_hours?.[0] }}:00-{{ simulationConfig.time_config?.off_peak_hours?.slice(-1)[0] }}:00</span>
                  <span class="period-multiplier">×{{ simulationConfig.time_config?.off_peak_activity_multiplier }}</span>
                </div>
              </div>
            </div>

            <!-- 에이전트 설정 -->
            <div class="config-block">
              <div class="config-block-header">
                <span class="config-block-title">에이전트 설정</span>
                <span class="config-block-badge">{{ simulationConfig.agent_configs?.length || 0 }}명</span>
              </div>
              <div class="agents-cards">
                <div
                  v-for="agent in simulationConfig.agent_configs"
                  :key="agent.agent_id"
                  class="agent-card"
                >
                  <!-- 카드 상단 -->
                  <div class="agent-card-header">
                    <div class="agent-identity">
                      <span class="agent-id">에이전트 {{ agent.agent_id }}</span>
                      <span class="agent-name">{{ agent.entity_name }}</span>
                    </div>
                    <div class="agent-tags">
                      <span class="agent-type">{{ agent.entity_type }}</span>
                      <span class="agent-stance" :class="'stance-' + agent.stance">{{ agent.stance }}</span>
                    </div>
                  </div>

                  <!-- 활성 시간대 -->
                  <div class="agent-timeline">
                    <span class="timeline-label">활성 시간대</span>
                    <div class="mini-timeline">
                      <div
                        v-for="hour in 24"
                        :key="hour - 1"
                        class="timeline-hour"
                        :class="{ 'active': agent.active_hours?.includes(hour - 1) }"
                        :title="`${hour - 1}:00`"
                      ></div>
                    </div>
                    <div class="timeline-marks">
                      <span>0</span>
                      <span>6</span>
                      <span>12</span>
                      <span>18</span>
                      <span>24</span>
                    </div>
                  </div>

                  <!-- 행동 매개변수 -->
                  <div class="agent-params">
                    <div class="param-group">
                      <div class="param-item">
                        <span class="param-label">게시/시간</span>
                        <span class="param-value">{{ agent.posts_per_hour }}</span>
                      </div>
                      <div class="param-item">
                        <span class="param-label">댓글/시간</span>
                        <span class="param-value">{{ agent.comments_per_hour }}</span>
                      </div>
                      <div class="param-item">
                        <span class="param-label">응답 지연</span>
                        <span class="param-value">{{ agent.response_delay_min }}-{{ agent.response_delay_max }}min</span>
                      </div>
                    </div>
                    <div class="param-group">
                      <div class="param-item">
                        <span class="param-label">활동성</span>
                        <span class="param-value with-bar">
                          <span class="mini-bar" :style="{ width: (agent.activity_level * 100) + '%' }"></span>
                          {{ (agent.activity_level * 100).toFixed(0) }}%
                        </span>
                      </div>
                      <div class="param-item">
                        <span class="param-label">감정 성향</span>
                        <span class="param-value" :class="agent.sentiment_bias > 0 ? 'positive' : agent.sentiment_bias < 0 ? 'negative' : 'neutral'">
                          {{ agent.sentiment_bias > 0 ? '+' : '' }}{{ agent.sentiment_bias?.toFixed(1) }}
                        </span>
                      </div>
                      <div class="param-item">
                        <span class="param-label">영향력</span>
                        <span class="param-value highlight">{{ agent.influence_weight?.toFixed(1) }}</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <!-- 플랫폼 설정 -->
            <div class="config-block">
              <div class="config-block-header">
                <span class="config-block-title">추천 알고리즘 설정</span>
              </div>
              <div class="platforms-grid">
                <div v-if="simulationConfig.twitter_config" class="platform-card">
                  <div class="platform-card-header">
                    <span class="platform-name">플랫폼 1: 광장 / 피드</span>
                  </div>
                  <div class="platform-params">
                    <div class="param-row">
                      <span class="param-label">시의성 가중치</span>
                      <span class="param-value">{{ simulationConfig.twitter_config.recency_weight }}</span>
                    </div>
                    <div class="param-row">
                      <span class="param-label">인기 가중치</span>
                      <span class="param-value">{{ simulationConfig.twitter_config.popularity_weight }}</span>
                    </div>
                    <div class="param-row">
                      <span class="param-label">관련성 가중치</span>
                      <span class="param-value">{{ simulationConfig.twitter_config.relevance_weight }}</span>
                    </div>
                    <div class="param-row">
                      <span class="param-label">바이럴 임계값</span>
                      <span class="param-value">{{ simulationConfig.twitter_config.viral_threshold }}</span>
                    </div>
                    <div class="param-row">
                      <span class="param-label">에코 챔버 강도</span>
                      <span class="param-value">{{ simulationConfig.twitter_config.echo_chamber_strength }}</span>
                    </div>
                  </div>
                </div>
                <div v-if="simulationConfig.reddit_config" class="platform-card">
                  <div class="platform-card-header">
                    <span class="platform-name">플랫폼 2: 주제 / 커뮤니티</span>
                  </div>
                  <div class="platform-params">
                    <div class="param-row">
                      <span class="param-label">시의성 가중치</span>
                      <span class="param-value">{{ simulationConfig.reddit_config.recency_weight }}</span>
                    </div>
                    <div class="param-row">
                      <span class="param-label">인기 가중치</span>
                      <span class="param-value">{{ simulationConfig.reddit_config.popularity_weight }}</span>
                    </div>
                    <div class="param-row">
                      <span class="param-label">관련성 가중치</span>
                      <span class="param-value">{{ simulationConfig.reddit_config.relevance_weight }}</span>
                    </div>
                    <div class="param-row">
                      <span class="param-label">바이럴 임계값</span>
                      <span class="param-value">{{ simulationConfig.reddit_config.viral_threshold }}</span>
                    </div>
                    <div class="param-row">
                      <span class="param-label">에코 챔버 강도</span>
                      <span class="param-value">{{ simulationConfig.reddit_config.echo_chamber_strength }}</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <!-- LLM 설정 추론 -->
            <div v-if="simulationConfig.generation_reasoning" class="config-block">
              <div class="config-block-header">
                <span class="config-block-title">LLM 설정 추론</span>
              </div>
              <div class="reasoning-content">
                <div
                  v-for="(reason, idx) in simulationConfig.generation_reasoning.split('|').slice(0, 2)"
                  :key="idx"
                  class="reasoning-item"
                >
                  <p class="reasoning-text">{{ reason.trim() }}</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 4단계: 초기 활성화 편성 -->
      <div class="step-card" :class="{ 'active': phase === 3, 'completed': phase > 3 }">
        <div class="card-header">
          <div class="step-info">
            <span class="step-num">04</span>
            <span class="step-title">초기 활성화 편성</span>
          </div>
          <div class="step-status">
            <span v-if="phase > 3" class="badge success">완료</span>
            <span v-else-if="phase === 3" class="badge processing">편성 중</span>
            <span v-else class="badge pending">대기 중</span>
          </div>
        </div>

        <div class="card-content">
          <p class="api-note">POST /api/simulation/prepare</p>
          <p class="description">
            서사 방향을 바탕으로 초기 활성화 이벤트와 핫 토픽을 자동 생성해 시뮬레이션 세계의 초기 상태를 이끕니다.
          </p>

          <div v-if="simulationConfig?.event_config" class="orchestration-content">
            <!-- 서사 방향 -->
            <div class="narrative-box">
              <span class="box-label narrative-label">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" class="special-icon">
                  <path d="M12 22C17.5228 22 22 17.5228 22 12C22 6.47715 17.5228 2 12 2C6.47715 2 2 6.47715 2 12C2 17.5228 6.47715 22 12 22Z" stroke="url(#paint0_linear)" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
                  <path d="M16.24 7.76L14.12 14.12L7.76 16.24L9.88 9.88L16.24 7.76Z" fill="url(#paint0_linear)" stroke="url(#paint0_linear)" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
                  <defs>
                    <linearGradient id="paint0_linear" x1="2" y1="2" x2="22" y2="22" gradientUnits="userSpaceOnUse">
                      <stop stop-color="#FF5722"/>
                      <stop offset="1" stop-color="#FF9800"/>
                    </linearGradient>
                  </defs>
                </svg>
                서사 유도 방향
              </span>
              <p class="narrative-text">{{ simulationConfig.event_config.narrative_direction }}</p>
            </div>

            <!-- 인기 주제 -->
            <div class="topics-section">
              <span class="box-label">초기 핫 토픽</span>
              <div class="hot-topics-grid">
                <span v-for="topic in simulationConfig.event_config.hot_topics" :key="topic" class="hot-topic-tag">
                  # {{ topic }}
                </span>
              </div>
            </div>

            <!-- 초기 게시글 흐름 -->
            <div class="initial-posts-section">
              <span class="box-label">초기 활성화 시퀀스 ({{ simulationConfig.event_config.initial_posts.length }})</span>
              <div class="posts-timeline">
                <div v-for="(post, idx) in simulationConfig.event_config.initial_posts" :key="idx" class="timeline-item">
                  <div class="timeline-marker"></div>
                  <div class="timeline-content">
                    <div class="post-header">
                      <span class="post-role">{{ post.poster_type }}</span>
                      <span class="post-agent-info">
                        <span class="post-id">에이전트 {{ post.poster_agent_id }}</span>
                        <span class="post-username">@{{ getAgentUsername(post.poster_agent_id) }}</span>
                      </span>
                    </div>
                    <p class="post-text">{{ post.content }}</p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 5단계: 준비 완료 -->
      <div class="step-card" :class="{ 'active': phase === 4 }">
        <div class="card-header">
          <div class="step-info">
            <span class="step-num">05</span>
            <span class="step-title">준비 완료</span>
          </div>
          <div class="step-status">
            <span v-if="phase >= 4" class="badge processing">진행 중</span>
            <span v-else class="badge pending">대기 중</span>
          </div>
        </div>

        <div class="card-content">
          <p class="api-note">POST /api/simulation/start</p>
          <p class="description">시뮬레이션 환경 준비가 완료되었습니다. 이제 시뮬레이션을 시작할 수 있습니다.</p>

          <!-- 시뮬레이션 회차 설정 - 설정 생성이 완료되고 회차가 계산된 후에만 표시 -->
          <div v-if="simulationConfig && autoGeneratedRounds" class="rounds-config-section">
            <div class="rounds-header">
              <div class="header-left">
                <span class="section-title">시뮬레이션 회차 설정</span>
                <span class="section-desc">MiroFish가 현실 전개를 자동 설계합니다. <span class="desc-highlight">{{ simulationConfig?.time_config?.total_simulation_hours || '-' }}</span> 시간, 각 회차는 현실 <span class="desc-highlight">{{ simulationConfig?.time_config?.minutes_per_round || '-' }}</span> 분의 시간 흐름을 의미합니다</span>
              </div>
              <label class="switch-control">
                <input type="checkbox" v-model="useCustomRounds">
                <span class="switch-track"></span>
                <span class="switch-label">사용자 지정</span>
              </label>
            </div>

            <Transition name="fade" mode="out-in">
              <div v-if="useCustomRounds" class="rounds-content custom" key="custom">
                <div class="slider-display">
                  <div class="slider-main-value">
                    <span class="val-num">{{ customMaxRounds }}</span>
                    <span class="val-unit">회</span>
                  </div>
                  <div class="slider-meta-info">
                    <span>에이전트 수가 100명일 경우: 예상 소요 시간 약 {{ Math.round(customMaxRounds * 0.6) }} 분</span>
                  </div>
                </div>

                <div class="range-wrapper">
                  <input
                    type="range"
                    v-model.number="customMaxRounds"
                    min="10"
                    :max="autoGeneratedRounds"
                    step="5"
                    class="minimal-slider"
                    :style="{ '--percent': ((customMaxRounds - 10) / (autoGeneratedRounds - 10)) * 100 + '%' }"
                  />
                  <div class="range-marks">
                    <span>10</span>
                    <span
                      class="mark-recommend"
                      :class="{ active: customMaxRounds === 40 }"
                      @click="customMaxRounds = 40"
                      :style="{ position: 'absolute', left: `calc(${(40 - 10) / (autoGeneratedRounds - 10) * 100}% - 30px)` }"
                    >40 (권장)</span>
                    <span>{{ autoGeneratedRounds }}</span>
                  </div>
                </div>
              </div>

              <div v-else class="rounds-content auto" key="auto">
                <div class="auto-info-card">
                  <div class="auto-value">
                    <span class="val-num">{{ autoGeneratedRounds }}</span>
                    <span class="val-unit">회</span>
                  </div>
                  <div class="auto-content">
                    <div class="auto-meta-row">
                      <span class="duration-badge">
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                          <circle cx="12" cy="12" r="10"></circle>
                          <polyline points="12 6 12 12 16 14"></polyline>
                        </svg>
                        에이전트 수가 100명일 경우: 예상 소요 시간 {{ Math.round(autoGeneratedRounds * 0.6) }} 분
                      </span>
                    </div>
                    <div class="auto-desc">
                      <p class="highlight-tip" @click="useCustomRounds = true">처음 실행할 경우에는 '사용자 지정 모드'로 전환해 시뮬레이션 회차를 줄이는 것을 강력히 권장합니다. 빠르게 미리 보고 오류 위험도 낮출 수 있습니다 ➝</p>
                    </div>
                  </div>
                </div>
              </div>
            </Transition>
          </div>

          <div class="action-group dual">
            <button
              class="action-btn secondary"
              @click="$emit('go-back')"
            >
              ← 그래프 구축으로 돌아가기
            </button>
            <button
              class="action-btn primary"
              :disabled="phase < 4"
              @click="handleStartSimulation"
            >
              양 세계 병렬 시뮬레이션 시작 ➝
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- 프로필 상세 모달 -->
    <Transition name="modal">
      <div v-if="selectedProfile" class="profile-modal-overlay" @click.self="selectedProfile = null">
        <div class="profile-modal">
          <div class="modal-header">
          <div class="modal-header-info">
            <div class="modal-name-row">
              <span class="modal-realname">{{ selectedProfile.username }}</span>
              <span class="modal-username">@{{ selectedProfile.name }}</span>
            </div>
            <span class="modal-profession">{{ selectedProfile.profession }}</span>
          </div>
          <button class="close-btn" @click="selectedProfile = null">×</button>
        </div>

        <div class="modal-body">
          <!-- 기본 정보 -->
          <div class="modal-info-grid">
            <div class="info-item">
              <span class="info-label">표면 연령</span>
              <span class="info-value">{{ selectedProfile.age || '-' }}세</span>
            </div>
            <div class="info-item">
              <span class="info-label">표면 성별</span>
              <span class="info-value">{{ { male: '남성', female: '여성', other: '기타' }[selectedProfile.gender] || selectedProfile.gender }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">국가/지역</span>
              <span class="info-value">{{ selectedProfile.country || '-' }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">표면 MBTI</span>
              <span class="info-value mbti">{{ selectedProfile.mbti || '-' }}</span>
            </div>
          </div>

          <!-- 소개 -->
          <div class="modal-section">
            <span class="section-label">인물 소개</span>
            <p class="section-bio">{{ selectedProfile.bio || '소개 없음' }}</p>
          </div>

          <!-- 관심 주제 -->
          <div class="modal-section" v-if="selectedProfile.interested_topics?.length">
            <span class="section-label">현실 시드 연관 주제</span>
            <div class="topics-grid">
              <span
                v-for="topic in selectedProfile.interested_topics"
                :key="topic"
                class="topic-item"
              >{{ topic }}</span>
            </div>
          </div>

          <!-- 상세 인물 배경 -->
          <div class="modal-section" v-if="selectedProfile.persona">
            <span class="section-label">상세 인물 배경</span>

            <!-- 인물 배경 차원 개요 -->
            <div class="persona-dimensions">
              <div class="dimension-card">
                <span class="dim-title">사건 전반 경험</span>
                <span class="dim-desc">이 사건에서의 전체 행동 궤적</span>
              </div>
              <div class="dimension-card">
                <span class="dim-title">행동 패턴 프로필</span>
                <span class="dim-desc">경험 요약과 행동 스타일 선호</span>
              </div>
              <div class="dimension-card">
                <span class="dim-title">고유 기억 흔적</span>
                <span class="dim-desc">현실 시드에서 형성된 기억</span>
              </div>
              <div class="dimension-card">
                <span class="dim-title">사회 관계망</span>
                <span class="dim-desc">개체 간 연결과 상호작용 그래프</span>
              </div>
            </div>

            <div class="persona-content">
              <p class="section-persona">{{ selectedProfile.persona }}</p>
            </div>
          </div>
        </div>
      </div>
      </div>
    </Transition>

    <!-- 하단 정보 / 로그 -->
    <div class="system-logs">
      <div class="log-header">
        <span class="log-title">시스템 로그</span>
        <span class="log-id">{{ simulationId || '시뮬레이션 없음' }}</span>
      </div>
      <div class="log-content" ref="logContent">
        <div class="log-line" v-for="(log, idx) in systemLogs" :key="idx">
          <span class="log-time">{{ log.time }}</span>
          <span class="log-msg">{{ log.msg }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import {
  prepareSimulation,
  getPrepareStatus,
  getSimulation,
  getSimulationProfilesRealtime,
  getSimulationConfigRealtime
} from '../api/simulation'
import { warnLog } from '../utils/logger'

const props = defineProps({
  simulationId: String,  // 부모 컴포넌트에서 전달됩니다
  projectData: Object,
  graphData: Object,
  systemLogs: Array
})

const emit = defineEmits(['go-back', 'next-step', 'add-log', 'update-status'])

// 상태
const phase = ref(0) // 0: 초기화 중, 1: 페르소나 생성, 2: 설정 생성, 3: 완료
const taskId = ref(null)
const prepareProgress = ref(0)
const currentStage = ref('')
const progressMessage = ref('')
const profiles = ref([])
const entityTypes = ref([])
const expectedTotal = ref(null)
const simulationConfig = ref(null)
const selectedProfile = ref(null)
const showProfilesDetail = ref(true)

// 로그 중복을 방지합니다. 마지막으로 출력한 핵심 정보를 기록합니다.
let lastLoggedMessage = ''
let lastLoggedProfileCount = 0
let lastLoggedConfigStage = ''

// 시뮬레이션 회차 설정
const useCustomRounds = ref(false) // 기본값은 자동 설정 회차를 사용합니다
const customMaxRounds = ref(40)   // 기본 권장값은 40회입니다

// 단계 변화를 감시해 phase를 갱신합니다
watch(currentStage, (newStage) => {
  if (newStage === '에이전트 페르소나 생성' || newStage === 'generating_profiles') {
    phase.value = 1
  } else if (newStage === '시뮬레이션 설정 생성' || newStage === 'generating_config') {
    phase.value = 2
    // 설정 생성 단계로 들어가면 설정 폴링을 시작합니다
    if (!configTimer) {
      addLog('양 플랫폼 시뮬레이션 설정 생성을 시작합니다...')
      startConfigPolling()
    }
  } else if (newStage === '시뮬레이션 스크립트 준비' || newStage === 'copying_scripts') {
    phase.value = 2 // 여전히 설정 단계입니다
  }
})

// 설정에서 자동 생성 회차를 계산합니다(하드코딩된 기본값은 사용하지 않습니다)
const autoGeneratedRounds = computed(() => {
  if (!simulationConfig.value?.time_config) {
    return null // 설정이 아직 없으면 null을 반환합니다
  }
  const totalHours = simulationConfig.value.time_config.total_simulation_hours
  const minutesPerRound = simulationConfig.value.time_config.minutes_per_round
  if (!totalHours || !minutesPerRound) {
    return null // 설정 데이터가 불완전하면 null을 반환합니다
  }
  const calculatedRounds = Math.floor((totalHours * 60) / minutesPerRound)
  // 최대 회차가 40(권장값) 미만으로 내려가지 않도록 해 슬라이더 범위를 벗어나지 않게 합니다
  return Math.max(calculatedRounds, 40)
})

// 폴링 타이머
let pollTimer = null
let profilesTimer = null
let configTimer = null
let pollFailureCount = 0

const getPrepareTaskStorageKey = () => {
  return props.simulationId ? `mirofish.prepareTaskId.${props.simulationId}` : ''
}

const persistPrepareTaskId = (value) => {
  const key = getPrepareTaskStorageKey()
  if (!key) return
  if (value) {
    sessionStorage.setItem(key, value)
  } else {
    sessionStorage.removeItem(key)
  }
}

const restorePrepareTaskId = () => {
  const key = getPrepareTaskStorageKey()
  return key ? sessionStorage.getItem(key) : null
}

// 계산 속성
const displayProfiles = computed(() => {
  if (showProfilesDetail.value) {
    return profiles.value
  }
  return profiles.value.slice(0, 6)
})

// agent_id에 해당하는 username을 가져옵니다
const getAgentUsername = (agentId) => {
  if (profiles.value && profiles.value.length > agentId && agentId >= 0) {
    const profile = profiles.value[agentId]
    return profile?.username || `agent_${agentId}`
  }
  return `agent_${agentId}`
}

// 모든 페르소나의 연관 주제 총수를 계산합니다
const totalTopicsCount = computed(() => {
  return profiles.value.reduce((sum, p) => {
    return sum + (p.interested_topics?.length || 0)
  }, 0)
})

// 메서드
const addLog = (msg) => {
  emit('add-log', msg)
}

// 시뮬레이션 시작 버튼 클릭을 처리합니다
const handleStartSimulation = () => {
  // 부모 컴포넌트에 전달할 매개변수를 구성합니다
  const params = {}

  if (useCustomRounds.value) {
    // 사용자 지정 회차를 사용하므로 maxRounds 매개변수를 전달합니다
    params.maxRounds = customMaxRounds.value
    addLog(`시뮬레이션 시작, 사용자 지정 회차: ${customMaxRounds.value}회`)
  } else {
    // 사용자가 자동 생성 회차를 유지하므로 maxRounds 매개변수를 전달하지 않습니다
    addLog(`시뮬레이션 시작, 자동 설정 회차: ${autoGeneratedRounds.value}회`)
  }

  emit('next-step', params)
}

const truncateBio = (bio) => {
  if (bio.length > 80) {
    return bio.substring(0, 80) + '...'
  }
  return bio
}

const selectProfile = (profile) => {
  selectedProfile.value = profile
}

// 시뮬레이션 준비를 자동으로 시작합니다
const startPrepareSimulation = async () => {
  if (!props.simulationId) {
    addLog('오류: simulationId가 없습니다')
    emit('update-status', 'error')
    return
  }

  // 첫 단계를 완료로 표시하고 두 번째 단계로 넘어갑니다
  phase.value = 1
  addLog(`시뮬레이션 인스턴스를 생성했습니다: ${props.simulationId}`)
  addLog('시뮬레이션 환경을 준비하는 중...')
  emit('update-status', 'processing')

  try {
    const res = await prepareSimulation({
      simulation_id: props.simulationId,
      use_llm_for_profiles: true,
      parallel_profile_count: 5
    })

    if (res.success && res.data) {
      if (res.data.already_prepared) {
        addLog('이미 준비가 완료된 작업을 감지해 그대로 사용합니다')
        await loadPreparedData()
        return
      }

      taskId.value = res.data.task_id
      persistPrepareTaskId(res.data.task_id)
      addLog(`준비 작업이 시작되었습니다`)
      addLog(`  └─ 작업 ID: ${res.data.task_id}`)

      // 즉시 예상 총 에이전트 수를 설정합니다(prepare API 응답값에서 가져옴)
      if (res.data.expected_entities_count) {
        expectedTotal.value = res.data.expected_entities_count
        addLog(`로컬 그래프에서 엔티티 ${res.data.expected_entities_count}개를 읽어왔습니다`)
        if (res.data.entity_types && res.data.entity_types.length > 0) {
          addLog(`  └─ 엔티티 유형: ${res.data.entity_types.join(', ')}`)
        }
      }

      addLog('준비 진행 상황을 폴링하기 시작합니다...')
      // 진행 상황 폴링을 시작합니다
      startPolling()
      // 프로필 실시간 가져오기를 시작합니다
      startProfilesPolling()
    } else {
      addLog(`준비 실패: ${res.error || '알 수 없는 오류'}`)
      emit('update-status', 'error')
    }
  } catch (err) {
    addLog(`준비 중 예외 발생: ${err.message}`)
    emit('update-status', 'error')
  }
}

const startPolling = () => {
  pollTimer = setInterval(pollPrepareStatus, 2000)
}

const stopPolling = () => {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

const startProfilesPolling = () => {
  profilesTimer = setInterval(fetchProfilesRealtime, 3000)
}

const stopProfilesPolling = () => {
  if (profilesTimer) {
    clearInterval(profilesTimer)
    profilesTimer = null
  }
}

const pollPrepareStatus = async () => {
  if (!props.simulationId) return

  try {
    pollFailureCount = 0

    if (!taskId.value) {
      const stateRes = await getSimulation(props.simulationId)
      if (stateRes.success && stateRes.data) {
        const simulation = stateRes.data
        if (simulation.status === 'ready') {
          addLog('✓ 기존 준비 완료 상태를 감지했습니다')
          stopPolling()
          stopProfilesPolling()
          persistPrepareTaskId(null)
          await loadPreparedData()
          return
        }
        if (simulation.status === 'failed') {
          addLog(`✗ 준비 실패: ${simulation.error || '알 수 없는 오류'}`)
          stopPolling()
          stopProfilesPolling()
          persistPrepareTaskId(null)
          emit('update-status', 'error')
          return
        }
        if (simulation.status === 'preparing') {
          phase.value = 1
          emit('update-status', 'processing')
          if (progressMessage.value !== '기존 준비 작업을 이어서 기다리는 중...') {
            progressMessage.value = '기존 준비 작업을 이어서 기다리는 중...'
            addLog('기존 준비 작업을 다시 연결하는 중...')
          }
          await fetchProfilesRealtime()
          return
        }
      }
    }

    const res = await getPrepareStatus({
      task_id: taskId.value,
      simulation_id: props.simulationId
    })

    if (res.success && res.data) {
      const data = res.data

      // 진행률을 갱신합니다
      prepareProgress.value = data.progress || 0
      progressMessage.value = data.message || ''

      // 단계 정보를 해석하고 상세 로그를 출력합니다
      if (data.progress_detail) {
        currentStage.value = data.progress_detail.current_stage_name || ''

        // 상세 진행 로그를 출력합니다(중복 방지)
        const detail = data.progress_detail
        const logKey = `${detail.current_stage}-${detail.current_item}-${detail.total_items}`
        if (logKey !== lastLoggedMessage && detail.item_description) {
          lastLoggedMessage = logKey
          const stageInfo = `[${detail.stage_index}/${detail.total_stages}]`
          if (detail.total_items > 0) {
            addLog(`${stageInfo} ${detail.current_stage_name}: ${detail.current_item}/${detail.total_items} - ${detail.item_description}`)
          } else {
            addLog(`${stageInfo} ${detail.current_stage_name}: ${detail.item_description}`)
          }
        }
      } else if (data.message) {
        // 메시지에서 단계를 추출합니다
        const match = data.message.match(/\[(\d+)\/(\d+)\]\s*([^:]+)/)
        if (match) {
          currentStage.value = match[3].trim()
        }
        // 메시지 로그를 출력합니다(중복 방지)
        if (data.message !== lastLoggedMessage) {
          lastLoggedMessage = data.message
          addLog(data.message)
        }
      }

      // 완료 여부를 확인합니다
      if (data.status === 'completed' || data.status === 'ready' || data.already_prepared) {
        addLog('✓ 준비 작업이 완료되었습니다')
        stopPolling()
        stopProfilesPolling()
        persistPrepareTaskId(null)
        await loadPreparedData()
      } else if (data.status === 'failed') {
        addLog(`✗ 준비 실패: ${data.error || '알 수 없는 오류'}`)
        stopPolling()
        stopProfilesPolling()
        persistPrepareTaskId(null)
        emit('update-status', 'error')
      }
    }
  } catch (err) {
    pollFailureCount += 1
    warnLog('폴링 상태 확인 실패:', err)
    if (pollFailureCount === 3) {
      addLog(`준비 상태를 연속으로 불러오지 못했습니다: ${err.message}`)
    }
  }
}

const fetchProfilesRealtime = async () => {
  if (!props.simulationId) return

  try {
    const res = await getSimulationProfilesRealtime(props.simulationId, 'reddit')

    if (res.success && res.data) {
      const prevCount = profiles.value.length
      profiles.value = res.data.profiles || []
      // API가 유효한 값을 반환할 때만 갱신해 기존 값을 덮어쓰지 않도록 합니다
      if (res.data.total_expected) {
        expectedTotal.value = res.data.total_expected
      }

      // 엔티티 유형을 추출합니다
      const types = new Set()
      profiles.value.forEach(p => {
        if (p.entity_type) types.add(p.entity_type)
      })
      entityTypes.value = Array.from(types)

      // 프로필 생성 진행 로그를 출력합니다(수량이 바뀔 때만)
      const currentCount = profiles.value.length
      if (currentCount > 0 && currentCount !== lastLoggedProfileCount) {
        lastLoggedProfileCount = currentCount
        const total = expectedTotal.value || '?'
        const latestProfile = profiles.value[currentCount - 1]
        const profileName = latestProfile?.name || latestProfile?.username || `Agent_${currentCount}`
        if (currentCount === 1) {
          addLog(`에이전트 페르소나 생성을 시작합니다...`)
        }
        addLog(`→ 에이전트 페르소나 ${currentCount}/${total}: ${profileName} (${latestProfile?.profession || '알 수 없는 직업'})`)

        // 모두 생성되었는지 확인합니다
        if (expectedTotal.value && currentCount >= expectedTotal.value) {
          addLog(`✓ 에이전트 페르소나 ${currentCount}개 생성을 모두 마쳤습니다`)
        }
      }
    }
  } catch (err) {
    warnLog('프로필 조회 실패:', err)
  }
}

// 설정 폴링
const startConfigPolling = () => {
  configTimer = setInterval(fetchConfigRealtime, 2000)
}

const stopConfigPolling = () => {
  if (configTimer) {
    clearInterval(configTimer)
    configTimer = null
  }
}

const fetchConfigRealtime = async () => {
  if (!props.simulationId) return

  try {
    const res = await getSimulationConfigRealtime(props.simulationId)

    if (res.success && res.data) {
      const data = res.data

      // 설정 생성 단계 로그를 출력합니다(중복 방지)
      if (data.generation_stage && data.generation_stage !== lastLoggedConfigStage) {
        lastLoggedConfigStage = data.generation_stage
        if (data.generation_stage === 'generating_profiles') {
          addLog('에이전트 페르소나 설정을 생성하는 중...')
        } else if (data.generation_stage === 'generating_config') {
          addLog('LLM으로 시뮬레이션 설정 값을 생성하는 중...')
        }
      }

      // 설정이 생성되었는지 확인합니다
      if (data.config_generated && data.config) {
        simulationConfig.value = data.config
        addLog('✓ 시뮬레이션 설정 생성이 완료되었습니다')

        // 상세 설정 요약을 표시합니다
        if (data.summary) {
          addLog(`  ├─ 에이전트 수: ${data.summary.total_agents}개`)
          addLog(`  ├─ 시뮬레이션 시간: ${data.summary.simulation_hours}시간`)
          addLog(`  ├─ 초기 게시물: ${data.summary.initial_posts_count}개`)
          addLog(`  ├─ 인기 주제: ${data.summary.hot_topics_count}개`)
          addLog(`  └─ 플랫폼 설정: Twitter ${data.summary.has_twitter_config ? '✓' : '✗'}, Reddit ${data.summary.has_reddit_config ? '✓' : '✗'}`)
        }

        // 시간 설정 상세를 표시합니다
        if (data.config.time_config) {
          const tc = data.config.time_config
          addLog(`시간 설정: 회차당 ${tc.minutes_per_round}분, 총 ${Math.floor((tc.total_simulation_hours * 60) / tc.minutes_per_round)}회`)
        }

        // 이벤트 설정을 표시합니다
        if (data.config.event_config?.narrative_direction) {
          const narrative = data.config.event_config.narrative_direction
          addLog(`서사 방향: ${narrative.length > 50 ? narrative.substring(0, 50) + '...' : narrative}`)
        }

        stopConfigPolling()
        phase.value = 4
        addLog('✓ 환경 설정이 완료되었습니다. 시뮬레이션을 시작할 수 있습니다')
        emit('update-status', 'completed')
      }
    }
  } catch (err) {
    warnLog('설정 조회 실패:', err)
  }
}

const loadPreparedData = async () => {
  phase.value = 2
  taskId.value = null
  persistPrepareTaskId(null)
  addLog('기존 설정 데이터를 불러오는 중...')

  // 마지막으로 한 번 프로필을 가져옵니다
  await fetchProfilesRealtime()
  addLog(`에이전트 페르소나 ${profiles.value.length}개를 불러왔습니다`)

  // 설정을 가져옵니다(실시간 API 사용)
  try {
    const res = await getSimulationConfigRealtime(props.simulationId)
    if (res.success && res.data) {
      if (res.data.config_generated && res.data.config) {
        simulationConfig.value = res.data.config
        addLog('✓ 시뮬레이션 설정을 성공적으로 불러왔습니다')

        // 상세 설정 요약을 표시합니다
        if (res.data.summary) {
          addLog(`  ├─ 에이전트 수: ${res.data.summary.total_agents}개`)
          addLog(`  ├─ 시뮬레이션 시간: ${res.data.summary.simulation_hours}시간`)
          addLog(`  └─ 초기 게시물: ${res.data.summary.initial_posts_count}개`)
        }

        addLog('✓ 환경 설정이 완료되었습니다. 시뮬레이션을 시작할 수 있습니다')
        phase.value = 4
        emit('update-status', 'completed')
      } else {
        // 설정이 아직 생성되지 않았으므로 폴링을 시작합니다
        addLog('설정을 생성하는 중입니다. 폴링을 시작합니다...')
        startConfigPolling()
      }
    }
  } catch (err) {
    addLog(`설정 불러오기 실패: ${err.message}`)
    emit('update-status', 'error')
  }
}

// 로그를 아래로 스크롤합니다
const logContent = ref(null)
watch(() => props.systemLogs?.length, () => {
  nextTick(() => {
    if (logContent.value) {
      logContent.value.scrollTop = logContent.value.scrollHeight
    }
  })
})

onMounted(() => {
  const resumeOrStartPrepare = async () => {
    if (!props.simulationId) return

    addLog('2단계 환경 설정을 초기화했습니다')
    taskId.value = restorePrepareTaskId()

    try {
      const stateRes = await getSimulation(props.simulationId)
      if (stateRes.success && stateRes.data) {
        const simulation = stateRes.data
        if (simulation.status === 'ready') {
          addLog('이미 준비가 완료된 시뮬레이션을 감지했습니다')
          await loadPreparedData()
          return
        }
        if (simulation.status === 'failed') {
          addLog(`✗ 이전 준비 작업 실패: ${simulation.error || '알 수 없는 오류'}`)
          emit('update-status', 'error')
          return
        }
        if (simulation.status === 'preparing') {
          phase.value = 1
          emit('update-status', 'processing')
          addLog('진행 중인 준비 작업을 이어서 표시합니다')
          if (taskId.value) {
            addLog(`  └─ 복원한 작업 ID: ${taskId.value}`)
          }
          startPolling()
          startProfilesPolling()
          return
        }
      }
    } catch (err) {
      warnLog('시뮬레이션 상태 확인 실패:', err)
    }

    await startPrepareSimulation()
  }

  resumeOrStartPrepare()
})

onUnmounted(() => {
  stopPolling()
  stopProfilesPolling()
  stopConfigPolling()
})
</script>

<style scoped>
.env-setup-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: #FAFAFA;
  font-family: 'Space Grotesk', 'Noto Sans KR', system-ui, sans-serif;
}

.scroll-container {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

/* 단계 카드 */
.step-card {
  background: #FFF;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.04);
  border: 1px solid #EAEAEA;
  transition: all 0.3s ease;
  position: relative;
}

.step-card.active {
  border-color: #FF5722;
  box-shadow: 0 4px 12px rgba(255, 87, 34, 0.08);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.step-info {
  display: flex;
  align-items: center;
  gap: 12px;
}

.step-num {
  font-family: 'JetBrains Mono', monospace;
  font-size: 20px;
  font-weight: 700;
  color: #E0E0E0;
}

.step-card.active .step-num,
.step-card.completed .step-num {
  color: #000;
}

.step-title {
  font-weight: 600;
  font-size: 14px;
  letter-spacing: 0.5px;
}

.badge {
  font-size: 10px;
  padding: 4px 8px;
  border-radius: 4px;
  font-weight: 600;
  text-transform: uppercase;
}

.badge.success { background: #E8F5E9; color: #2E7D32; }
.badge.processing { background: #FF5722; color: #FFF; }
.badge.pending { background: #F5F5F5; color: #999; }
.badge.accent { background: #E3F2FD; color: #1565C0; }

.card-content {
  /* 추가 패딩 없음 - step-card의 패딩을 그대로 사용합니다 */
}

.api-note {
  font-family: 'JetBrains Mono', monospace;
  font-size: 10px;
  color: #999;
  margin-bottom: 8px;
}

.description {
  font-size: 12px;
  color: #666;
  line-height: 1.5;
  margin-bottom: 16px;
}

/* 동작 영역 */
.action-section {
  margin-top: 16px;
}

.action-btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 12px 24px;
  font-size: 14px;
  font-weight: 600;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.action-btn.primary {
  background: #000;
  color: #FFF;
}

.action-btn.primary:hover:not(:disabled) {
  opacity: 0.8;
}

.action-btn.secondary {
  background: #F5F5F5;
  color: #333;
}

.action-btn.secondary:hover:not(:disabled) {
  background: #E5E5E5;
}

.action-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.action-group {
  display: flex;
  gap: 12px;
  margin-top: 16px;
}

.action-group.dual {
  display: grid;
  grid-template-columns: 1fr 1fr;
}

.action-group.dual .action-btn {
  width: 100%;
}

/* 정보 카드 */
.info-card {
  background: #F5F5F5;
  border-radius: 6px;
  padding: 16px;
  margin-top: 16px;
}

.info-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 0;
  border-bottom: 1px dashed #E0E0E0;
}

.info-row:last-child {
  border-bottom: none;
}

.info-label {
  font-size: 12px;
  color: #666;
}

.info-value {
  font-size: 13px;
  font-weight: 500;
}

.info-value.mono {
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
}

/* 통계 그리드 */
.stats-grid {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 12px;
  background: #F9F9F9;
  padding: 16px;
  border-radius: 6px;
}

.stat-card {
  text-align: center;
}

.stat-value {
  display: block;
  font-size: 20px;
  font-weight: 700;
  color: #000;
  font-family: 'JetBrains Mono', monospace;
}

.stat-label {
  font-size: 9px;
  color: #999;
  text-transform: uppercase;
  margin-top: 4px;
  display: block;
}

/* 프로필 미리보기 */
.profiles-preview {
  margin-top: 20px;
  border-top: 1px solid #E5E5E5;
  padding-top: 16px;
}

.preview-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.preview-title {
  font-size: 12px;
  font-weight: 600;
  color: #666;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.profiles-list {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
  max-height: 320px;
  overflow-y: auto;
  padding-right: 4px;
}

.profiles-list::-webkit-scrollbar {
  width: 4px;
}

.profiles-list::-webkit-scrollbar-thumb {
  background: #DDD;
  border-radius: 2px;
}

.profiles-list::-webkit-scrollbar-thumb:hover {
  background: #CCC;
}

.profile-card {
  background: #FAFAFA;
  border: 1px solid #E5E5E5;
  border-radius: 6px;
  padding: 14px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.profile-card:hover {
  border-color: #999;
  background: #FFF;
}

.profile-header {
  display: flex;
  align-items: baseline;
  gap: 8px;
  margin-bottom: 6px;
}

.profile-realname {
  font-size: 14px;
  font-weight: 700;
  color: #000;
}

.profile-username {
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  color: #999;
}

.profile-meta {
  margin-bottom: 8px;
}

.profile-profession {
  font-size: 11px;
  color: #666;
  background: #F0F0F0;
  padding: 2px 8px;
  border-radius: 3px;
}

.profile-bio {
  font-size: 12px;
  color: #444;
  line-height: 1.6;
  margin: 0 0 10px 0;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.profile-topics {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.topic-tag {
  font-size: 10px;
  color: #1565C0;
  background: #E3F2FD;
  padding: 2px 8px;
  border-radius: 10px;
}

.topic-more {
  font-size: 10px;
  color: #999;
  padding: 2px 6px;
}

/* 설정 미리보기 */
/* 설정 상세 패널 */
.config-detail-panel {
  margin-top: 16px;
}

.config-block {
  margin-top: 16px;
  border-top: 1px solid #E5E5E5;
  padding-top: 12px;
}

.config-block:first-child {
  margin-top: 0;
  border-top: none;
  padding-top: 0;
}

.config-block-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.config-block-title {
  font-size: 12px;
  font-weight: 600;
  color: #666;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.config-block-badge {
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  background: #F1F5F9;
  color: #475569;
  padding: 2px 8px;
  border-radius: 10px;
}

/* 설정 그리드 */
.config-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}

.config-item {
  background: #F9F9F9;
  padding: 12px 14px;
  border-radius: 6px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.config-item-label {
  font-size: 11px;
  color: #94A3B8;
}

.config-item-value {
  font-family: 'JetBrains Mono', monospace;
  font-size: 16px;
  font-weight: 600;
  color: #1E293B;
}

/* 시간 구간 */
.time-periods {
  margin-top: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.period-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 12px;
  background: #F9F9F9;
  border-radius: 6px;
}

.period-label {
  font-size: 12px;
  font-weight: 500;
  color: #64748B;
  min-width: 70px;
}

.period-hours {
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  color: #475569;
  flex: 1;
}

.period-multiplier {
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  font-weight: 600;
  color: #6366F1;
  background: #EEF2FF;
  padding: 2px 6px;
  border-radius: 4px;
}

/* 에이전트 카드 */
.agents-cards {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
  max-height: 400px;
  overflow-y: auto;
  padding-right: 4px;
}

.agents-cards::-webkit-scrollbar {
  width: 4px;
}

.agents-cards::-webkit-scrollbar-thumb {
  background: #DDD;
  border-radius: 2px;
}

.agents-cards::-webkit-scrollbar-thumb:hover {
  background: #CCC;
}

.agent-card {
  background: #F9F9F9;
  border: 1px solid #E5E5E5;
  border-radius: 6px;
  padding: 14px;
  transition: all 0.2s ease;
}

.agent-card:hover {
  border-color: #999;
  background: #FFF;
}

/* 에이전트 카드 헤더 */
.agent-card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 14px;
  padding-bottom: 12px;
  border-bottom: 1px solid #F1F5F9;
}

.agent-identity {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.agent-id {
  font-family: 'JetBrains Mono', monospace;
  font-size: 10px;
  color: #94A3B8;
}

.agent-name {
  font-size: 14px;
  font-weight: 600;
  color: #1E293B;
}

.agent-tags {
  display: flex;
  gap: 6px;
}

.agent-type {
  font-size: 10px;
  color: #64748B;
  background: #F1F5F9;
  padding: 2px 8px;
  border-radius: 4px;
}

.agent-stance {
  font-size: 10px;
  font-weight: 500;
  text-transform: uppercase;
  padding: 2px 8px;
  border-radius: 4px;
}

.stance-neutral {
  background: #F1F5F9;
  color: #64748B;
}

.stance-supportive {
  background: #DCFCE7;
  color: #16A34A;
}

.stance-opposing {
  background: #FEE2E2;
  color: #DC2626;
}

.stance-observer {
  background: #FEF3C7;
  color: #D97706;
}

/* 에이전트 타임라인 */
.agent-timeline {
  margin-bottom: 14px;
}

.timeline-label {
  display: block;
  font-size: 10px;
  color: #94A3B8;
  margin-bottom: 6px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.mini-timeline {
  display: flex;
  gap: 2px;
  height: 16px;
  background: #F8FAFC;
  border-radius: 4px;
  padding: 3px;
}

.timeline-hour {
  flex: 1;
  background: #E2E8F0;
  border-radius: 2px;
  transition: all 0.2s;
}

.timeline-hour.active {
  background: linear-gradient(180deg, #6366F1, #818CF8);
}

.timeline-marks {
  display: flex;
  justify-content: space-between;
  margin-top: 4px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 9px;
  color: #94A3B8;
}

/* 에이전트 매개변수 */
.agent-params {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.param-group {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
}

.param-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.param-item .param-label {
  font-size: 10px;
  color: #94A3B8;
}

.param-item .param-value {
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  font-weight: 600;
  color: #475569;
}

.param-value.with-bar {
  display: flex;
  align-items: center;
  gap: 6px;
}

.mini-bar {
  height: 4px;
  background: linear-gradient(90deg, #6366F1, #A855F7);
  border-radius: 2px;
  min-width: 4px;
  max-width: 40px;
}

.param-value.positive {
  color: #16A34A;
}

.param-value.negative {
  color: #DC2626;
}

.param-value.neutral {
  color: #64748B;
}

.param-value.highlight {
  color: #6366F1;
}

/* 플랫폼 그리드 */
.platforms-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}

.platform-card {
  background: #F9F9F9;
  padding: 14px;
  border-radius: 6px;
}

.platform-card-header {
  margin-bottom: 10px;
  padding-bottom: 8px;
  border-bottom: 1px solid #E5E5E5;
}

.platform-name {
  font-size: 13px;
  font-weight: 600;
  color: #333;
}

.platform-params {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.param-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.param-label {
  font-size: 12px;
  color: #64748B;
}

.param-value {
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  font-weight: 600;
  color: #1E293B;
}

/* 추론 내용 */
.reasoning-content {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.reasoning-item {
  padding: 12px 14px;
  background: #F9F9F9;
  border-radius: 6px;
}

.reasoning-text {
  font-size: 13px;
  color: #555;
  line-height: 1.7;
  margin: 0;
}

/* 프로필 모달 */
.profile-modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  backdrop-filter: blur(4px);
}

.profile-modal {
  background: #FFF;
  border-radius: 16px;
  width: 90%;
  max-width: 600px;
  max-height: 85vh;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding: 24px;
  background: #FFF;
  border-bottom: 1px solid #F0F0F0;
}

.modal-header-info {
  flex: 1;
}

.modal-name-row {
  display: flex;
  align-items: baseline;
  gap: 10px;
  margin-bottom: 8px;
}

.modal-realname {
  font-size: 20px;
  font-weight: 700;
  color: #000;
}

.modal-username {
  font-family: 'JetBrains Mono', monospace;
  font-size: 13px;
  color: #999;
}

.modal-profession {
  font-size: 12px;
  color: #666;
  background: #F5F5F5;
  padding: 4px 10px;
  border-radius: 4px;
  display: inline-block;
  font-weight: 500;
}

.close-btn {
  width: 32px;
  height: 32px;
  border: none;
  background: none;
  color: #999;
  border-radius: 50%;
  font-size: 24px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  line-height: 1;
  transition: color 0.2s;
  padding: 0;
}

.close-btn:hover {
  color: #333;
}

.modal-body {
  padding: 24px;
  overflow-y: auto;
  flex: 1;
}

/* 기본 정보 그리드 */
.modal-info-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 24px 16px;
  margin-bottom: 32px;
  padding: 0;
  background: transparent;
  border-radius: 0;
}

.info-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.info-label {
  font-size: 11px;
  color: #999;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  font-weight: 600;
}

.info-value {
  font-size: 15px;
  font-weight: 600;
  color: #333;
}

.info-value.mbti {
  font-family: 'JetBrains Mono', monospace;
  color: #FF5722;
}

/* 섹션 영역 */
.modal-section {
  margin-bottom: 28px;
}

.section-label {
  display: block;
  font-size: 11px;
  font-weight: 600;
  color: #999;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 12px;
}

.section-bio {
  font-size: 14px;
  color: #333;
  line-height: 1.6;
  margin: 0;
  padding: 16px;
  background: #F9F9F9;
  border-radius: 6px;
  border-left: 3px solid #E0E0E0;
}

/* 주제 태그 */
.topics-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.topic-item {
  font-size: 11px;
  color: #1565C0;
  background: #E3F2FD;
  padding: 4px 10px;
  border-radius: 12px;
  transition: all 0.2s;
  border: none;
}

.topic-item:hover {
  background: #BBDEFB;
  color: #0D47A1;
}

/* 상세 인물 배경 */
.persona-dimensions {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
  margin-bottom: 16px;
}

.dimension-card {
  background: #F8F9FA;
  padding: 12px;
  border-radius: 6px;
  border-left: 3px solid #DDD;
  transition: all 0.2s;
}

.dimension-card:hover {
  background: #F0F0F0;
  border-left-color: #999;
}

.dim-title {
  display: block;
  font-size: 12px;
  font-weight: 700;
  color: #333;
  margin-bottom: 4px;
}

.dim-desc {
  display: block;
  font-size: 10px;
  color: #888;
  line-height: 1.4;
}

.persona-content {
  max-height: none;
  overflow: visible;
  padding: 0;
  background: transparent;
  border: none;
  border-radius: 0;
}

.persona-content::-webkit-scrollbar {
  width: 4px;
}

.persona-content::-webkit-scrollbar-thumb {
  background: #DDD;
  border-radius: 2px;
}

.section-persona {
  font-size: 13px;
  color: #555;
  line-height: 1.8;
  margin: 0;
  text-align: justify;
}

/* 시스템 로그 */
.system-logs {
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
  color: #888;
}

.log-content {
  display: flex;
  flex-direction: column;
  gap: 4px;
  height: 80px; /* 대략 4줄이 보입니다 */
  overflow-y: auto;
  padding-right: 4px;
}

.log-content::-webkit-scrollbar {
  width: 4px;
}

.log-content::-webkit-scrollbar-thumb {
  background: #333;
  border-radius: 2px;
}

.log-line {
  font-size: 11px;
  display: flex;
  gap: 12px;
  line-height: 1.5;
}

.log-time {
  color: #666;
  min-width: 75px;
}

.log-msg {
  color: #CCC;
  word-break: break-all;
}

/* 스피너 */
.spinner-sm {
  width: 16px;
  height: 16px;
  border: 2px solid #E5E5E5;
  border-top-color: #FF5722;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
/* 오케스트레이션 내용 */
.orchestration-content {
  display: flex;
  flex-direction: column;
  gap: 20px;
  margin-top: 16px;
}

.box-label {
  display: block;
  font-size: 12px;
  font-weight: 600;
  color: #666;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 12px;
}

.narrative-box {
  background: #FFFFFF;
  padding: 20px 24px;
  border-radius: 12px;
  border: 1px solid #EEF2F6;
  box-shadow: 0 4px 24px rgba(0,0,0,0.03);
  transition: all 0.3s ease;
}

.narrative-box .box-label {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #666;
  font-size: 13px;
  letter-spacing: 0.5px;
  margin-bottom: 12px;
  font-weight: 600;
}

.special-icon {
  filter: drop-shadow(0 2px 4px rgba(255, 87, 34, 0.2));
  transition: transform 0.6s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.narrative-box:hover .special-icon {
  transform: rotate(180deg);
}

.narrative-text {
  font-family: 'Inter', 'Noto Sans KR', system-ui, sans-serif;
  font-size: 14px;
  color: #334155;
  line-height: 1.8;
  margin: 0;
  text-align: justify;
  letter-spacing: 0.01em;
}

.topics-section {
  background: #FFF;
}

.hot-topics-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.hot-topic-tag {
  font-size: 12px;
  color:rgba(255, 86, 34, 0.88);
  background: #FFF3E0;
  padding: 4px 10px;
  border-radius: 12px;
  font-weight: 500;
}

.hot-topic-more {
  font-size: 11px;
  color: #999;
  padding: 4px 6px;
}

.initial-posts-section {
  border-top: 1px solid #EAEAEA;
  padding-top: 16px;
}

.posts-timeline {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding-left: 8px;
  border-left: 2px solid #F0F0F0;
  margin-top: 12px;
}

.timeline-item {
  position: relative;
  padding-left: 20px;
}

.timeline-marker {
  position: absolute;
  left: 0;
  top: 14px;
  width: 12px;
  height: 2px;
  background: #DDD;
}

.timeline-content {
  background: #F9F9F9;
  padding: 12px;
  border-radius: 6px;
  border: 1px solid #EEE;
}

.post-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 6px;
}

.post-role {
  font-size: 11px;
  font-weight: 700;
  color: #333;
  text-transform: uppercase;
}

.post-agent-info {
  display: flex;
  align-items: center;
  gap: 6px;
}

.post-id,
.post-username {
  font-family: 'JetBrains Mono', monospace;
  font-size: 10px;
  color: #666;
  line-height: 1;
  vertical-align: baseline;
}

.post-username {
  margin-right: 6px;
}

.post-text {
  font-size: 12px;
  color: #555;
  line-height: 1.5;
  margin: 0;
}

/* 시뮬레이션 회차 설정 스타일 */
.rounds-config-section {
  margin: 24px 0;
  padding-top: 24px;
  border-top: 1px solid #EAEAEA;
}

.rounds-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.header-left {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.section-title {
  font-size: 14px;
  font-weight: 600;
  color: #1E293B;
}

.section-desc {
  font-size: 12px;
  color: #94A3B8;
}

.desc-highlight {
  font-family: 'JetBrains Mono', monospace;
  font-weight: 600;
  color: #1E293B;
  background: #F1F5F9;
  padding: 1px 6px;
  border-radius: 4px;
  margin: 0 2px;
}

/* 스위치 컨트롤 */
.switch-control {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  padding: 4px 8px 4px 4px;
  border-radius: 20px;
  transition: background 0.2s;
}

.switch-control:hover {
  background: #F8FAFC;
}

.switch-control input {
  display: none;
}

.switch-track {
  width: 36px;
  height: 20px;
  background: #E2E8F0;
  border-radius: 10px;
  position: relative;
  transition: all 0.3s cubic-bezier(0.4, 0.0, 0.2, 1);
}

.switch-track::after {
  content: '';
  position: absolute;
  left: 2px;
  top: 2px;
  width: 16px;
  height: 16px;
  background: #FFF;
  border-radius: 50%;
  box-shadow: 0 1px 3px rgba(0,0,0,0.1);
  transition: transform 0.3s cubic-bezier(0.4, 0.0, 0.2, 1);
}

.switch-control input:checked + .switch-track {
  background: #000;
}

.switch-control input:checked + .switch-track::after {
  transform: translateX(16px);
}

.switch-label {
  font-size: 12px;
  font-weight: 500;
  color: #64748B;
}

.switch-control input:checked ~ .switch-label {
  color: #1E293B;
}

/* 슬라이더 내용 */
.rounds-content {
  animation: fadeIn 0.3s ease;
}

.slider-display {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  margin-bottom: 16px;
}

.slider-main-value {
  display: flex;
  align-items: baseline;
  gap: 4px;
}

.val-num {
  font-family: 'JetBrains Mono', monospace;
  font-size: 24px;
  font-weight: 700;
  color: #000;
}

.val-unit {
  font-size: 12px;
  color: #666;
  font-weight: 500;
}

.slider-meta-info {
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  color: #64748B;
  background: #F1F5F9;
  padding: 4px 8px;
  border-radius: 4px;
}

.range-wrapper {
  position: relative;
  padding: 0 2px;
}

.minimal-slider {
  -webkit-appearance: none;
  width: 100%;
  height: 4px;
  background: #E2E8F0;
  border-radius: 2px;
  outline: none;
  background-image: linear-gradient(#000, #000);
  background-size: var(--percent, 0%) 100%;
  background-repeat: no-repeat;
  cursor: pointer;
}

.minimal-slider::-webkit-slider-thumb {
  -webkit-appearance: none;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: #FFF;
  border: 2px solid #000;
  cursor: pointer;
  box-shadow: 0 1px 4px rgba(0,0,0,0.1);
  transition: transform 0.1s;
  margin-top: -6px; /* thumb를 중앙에 맞춥니다 */
}

.minimal-slider::-webkit-slider-thumb:hover {
  transform: scale(1.1);
}

.minimal-slider::-webkit-slider-runnable-track {
  height: 4px;
  border-radius: 2px;
}

.range-marks {
  display: flex;
  justify-content: space-between;
  margin-top: 8px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 10px;
  color: #94A3B8;
  position: relative;
}

.mark-recommend {
  cursor: pointer;
  transition: color 0.2s;
  position: relative;
}

.mark-recommend:hover {
  color: #000;
}

.mark-recommend.active {
  color: #000;
  font-weight: 600;
}

.mark-recommend::after {
  content: '';
  position: absolute;
  top: -12px;
  left: 50%;
  transform: translateX(-50%);
  width: 1px;
  height: 4px;
  background: #CBD5E1;
}

/* 자동 정보 */
.auto-info-card {
  display: flex;
  align-items: center;
  gap: 24px;
  background: #F8FAFC;
  padding: 16px 20px;
  border-radius: 8px;
}

.auto-value {
  display: flex;
  flex-direction: row;
  align-items: baseline;
  gap: 4px;
  padding-right: 24px;
  border-right: 1px solid #E2E8F0;
}

.auto-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 8px;
  justify-content: center;
}

.auto-meta-row {
  display: flex;
  align-items: center;
}

.duration-badge {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  font-weight: 500;
  color: #64748B;
  background: #FFFFFF;
  border: 1px solid #E2E8F0;
  padding: 3px 8px;
  border-radius: 6px;
  box-shadow: 0 1px 2px rgba(0,0,0,0.02);
}

.auto-desc {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.auto-desc p {
  margin: 0;
  font-size: 13px;
  color: #64748B;
  line-height: 1.5;
}

.highlight-tip {
  margin-top: 4px !important;
  font-size: 12px !important;
  color: #000 !important;
  font-weight: 500;
  cursor: pointer;
}

.highlight-tip:hover {
  text-decoration: underline;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(4px); }
  to { opacity: 1; transform: translateY(0); }
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

/* 모달 전환 */
.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.3s ease;
}

.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}

.modal-enter-active .profile-modal {
  transition: all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.modal-leave-active .profile-modal {
  transition: all 0.3s ease-in;
}

.modal-enter-from .profile-modal,
.modal-leave-to .profile-modal {
  transform: scale(0.95) translateY(10px);
  opacity: 0;
}
</style>
