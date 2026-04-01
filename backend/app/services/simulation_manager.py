"""
OASIS 시뮬레이션 관리자
    트위터와 레딧 양 플랫폼의 병렬 시뮬레이션을 관리합니다.
사전 정의된 스크립트 + LLM으로 설정 파라미터를 지능적으로 생성합니다.
"""

import os
import csv
import json
import shutil
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from ..utils.logger import get_logger
from .graph_entity_reader import GraphEntityReader
from .oasis_profile_generator import OasisProfileGenerator, OasisAgentProfile
from .profile_localization import ProfileLocalizationService
from .simulation_config_generator import SimulationConfigGenerator, SimulationParameters

logger = get_logger('mirofish.simulation')


class SimulationStatus(str, Enum):
    """시뮬레이션 상태"""
    CREATED = "created"
    PREPARING = "preparing"
    READY = "ready"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"      # 시뮬레이션이 수동으로 중지됨
    COMPLETED = "completed"  # 시뮬레이션이 자연스럽게 완료됨
    FAILED = "failed"


class PlatformType(str, Enum):
    """플랫폼 유형"""
    TWITTER = "twitter"
    REDDIT = "reddit"


@dataclass
class SimulationState:
    """시뮬레이션 상태"""
    simulation_id: str
    project_id: str
    graph_id: str

    # 플랫폼 활성화 상태
    enable_twitter: bool = True
    enable_reddit: bool = True

    # 상태
    status: SimulationStatus = SimulationStatus.CREATED

    # 준비 단계 데이터
    entities_count: int = 0
    profiles_count: int = 0
    entity_types: List[str] = field(default_factory=list)

    # 설정 생성 정보
    config_generated: bool = False
    config_reasoning: str = ""

    # 런타임 데이터
    current_round: int = 0
    twitter_status: str = "not_started"
    reddit_status: str = "not_started"

    # 타임스탬프
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    # 오류 정보
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """전체 상태 딕셔너리(내부 사용)"""
        return {
            "simulation_id": self.simulation_id,
            "project_id": self.project_id,
            "graph_id": self.graph_id,
            "enable_twitter": self.enable_twitter,
            "enable_reddit": self.enable_reddit,
            "status": self.status.value,
            "entities_count": self.entities_count,
            "profiles_count": self.profiles_count,
            "entity_types": self.entity_types,
            "config_generated": self.config_generated,
            "config_reasoning": self.config_reasoning,
            "current_round": self.current_round,
            "twitter_status": self.twitter_status,
            "reddit_status": self.reddit_status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "error": self.error,
        }

    def to_simple_dict(self) -> Dict[str, Any]:
        """간소화된 상태 딕셔너리(API 반환용)"""
        return {
            "simulation_id": self.simulation_id,
            "project_id": self.project_id,
            "graph_id": self.graph_id,
            "status": self.status.value,
            "entities_count": self.entities_count,
            "profiles_count": self.profiles_count,
            "entity_types": self.entity_types,
            "config_generated": self.config_generated,
            "error": self.error,
        }


class SimulationManager:
    """
    시뮬레이션 관리자

    핵심 기능:
    1. 로컬 그래프에서 엔티티를 읽고 필터링
    2. OASIS 에이전트 프로필 생성
    3. LLM으로 시뮬레이션 설정 파라미터를 지능적으로 생성
    4. 사전 정의된 스크립트에 필요한 모든 파일 준비
    """

    # 시뮬레이션 데이터 저장 디렉터리
    SIMULATION_DATA_DIR = os.path.join(
        os.path.dirname(__file__),
        '../../uploads/simulations'
    )

    def __init__(self):
        # 디렉터리가 존재하도록 보장
        os.makedirs(self.SIMULATION_DATA_DIR, exist_ok=True)

        # 메모리 내 시뮬레이션 상태 캐시
        self._simulations: Dict[str, SimulationState] = {}
        self.profile_localizer = ProfileLocalizationService()

    def _get_simulation_dir(self, simulation_id: str) -> str:
        """시뮬레이션 데이터 디렉터리 가져오기"""
        sim_dir = os.path.join(self.SIMULATION_DATA_DIR, simulation_id)
        os.makedirs(sim_dir, exist_ok=True)
        return sim_dir

    def _save_simulation_state(self, state: SimulationState):
        """시뮬레이션 상태를 파일에 저장"""
        sim_dir = self._get_simulation_dir(state.simulation_id)
        state_file = os.path.join(sim_dir, "state.json")

        state.updated_at = datetime.now().isoformat()

        with open(state_file, 'w', encoding='utf-8') as f:
            json.dump(state.to_dict(), f, ensure_ascii=False, indent=2)

        self._simulations[state.simulation_id] = state

    def _load_simulation_state(self, simulation_id: str) -> Optional[SimulationState]:
        """파일에서 시뮬레이션 상태를 로드"""
        if simulation_id in self._simulations:
            return self._simulations[simulation_id]

        sim_dir = self._get_simulation_dir(simulation_id)
        state_file = os.path.join(sim_dir, "state.json")

        if not os.path.exists(state_file):
            return None

        with open(state_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        state = SimulationState(
            simulation_id=simulation_id,
            project_id=data.get("project_id", ""),
            graph_id=data.get("graph_id", ""),
            enable_twitter=data.get("enable_twitter", True),
            enable_reddit=data.get("enable_reddit", True),
            status=SimulationStatus(data.get("status", "created")),
            entities_count=data.get("entities_count", 0),
            profiles_count=data.get("profiles_count", 0),
            entity_types=data.get("entity_types", []),
            config_generated=data.get("config_generated", False),
            config_reasoning=data.get("config_reasoning", ""),
            current_round=data.get("current_round", 0),
            twitter_status=data.get("twitter_status", "not_started"),
            reddit_status=data.get("reddit_status", "not_started"),
            created_at=data.get("created_at", datetime.now().isoformat()),
            updated_at=data.get("updated_at", datetime.now().isoformat()),
            error=data.get("error"),
        )

        self._simulations[simulation_id] = state
        return state

    def create_simulation(
        self,
        project_id: str,
        graph_id: str,
        enable_twitter: bool = True,
        enable_reddit: bool = True,
    ) -> SimulationState:
        """
        새 시뮬레이션 생성

        인자:
            project_id: 프로젝트 ID
            graph_id: 그래프 ID
            enable_twitter: 트위터 시뮬레이션 활성화 여부
            enable_reddit: 레딧 시뮬레이션 활성화 여부

        반환값:
            SimulationState
        """
        import uuid
        simulation_id = f"sim_{uuid.uuid4().hex[:12]}"

        state = SimulationState(
            simulation_id=simulation_id,
            project_id=project_id,
            graph_id=graph_id,
            enable_twitter=enable_twitter,
            enable_reddit=enable_reddit,
            status=SimulationStatus.CREATED,
        )

        self._save_simulation_state(state)
        logger.info(f"시뮬레이션 생성: {simulation_id}, project={project_id}, graph={graph_id}")

        return state

    def prepare_simulation(
        self,
        simulation_id: str,
        simulation_requirement: str,
        document_text: str,
        defined_entity_types: Optional[List[str]] = None,
        use_llm_for_profiles: bool = True,
        progress_callback: Optional[callable] = None,
        parallel_profile_count: int = 3
    ) -> SimulationState:
        """
        시뮬레이션 환경을 준비합니다(전 과정 자동화).

        단계:
        1. 로컬 그래프에서 엔티티를 읽고 필터링
        2. 각 엔티티에 대해 OASIS 에이전트 프로필 생성(선택적으로 LLM 강화, 병렬 지원)
        3. LLM으로 시뮬레이션 설정 파라미터를 지능적으로 생성(시간, 활동도, 발언 빈도 등)
        4. 설정 파일과 프로필 파일 저장
        5. 사전 정의된 스크립트를 시뮬레이션 디렉터리로 준비

        인자:
            simulation_id: 시뮬레이션 ID
            simulation_requirement: 시뮬레이션 요구사항 설명(LLM 설정 생성용)
            document_text: 원본 문서 내용(LLM이 배경을 이해하는 데 사용)
            defined_entity_types: 미리 정의된 엔티티 유형(선택 사항)
            use_llm_for_profiles: LLM으로 상세 인물 설정을 생성할지 여부
            progress_callback: 진행 콜백 함수(stage, progress, message)
            parallel_profile_count: 병렬로 인물 설정을 생성할 개수, 기본 3

        반환값:
            SimulationState
        """
        state = self._load_simulation_state(simulation_id)
        if not state:
            raise ValueError(f"시뮬레이션이 존재하지 않습니다: {simulation_id}")

        try:
            state.status = SimulationStatus.PREPARING
            self._save_simulation_state(state)

            sim_dir = self._get_simulation_dir(simulation_id)

            # ========== 단계 1: 엔티티를 읽고 필터링 ==========
            if progress_callback:
                progress_callback("reading", 0, "로컬 그래프를 읽는 중...")

            reader = GraphEntityReader()

            if progress_callback:
                progress_callback("reading", 30, "노드 데이터를 읽는 중...")

            filtered = reader.filter_defined_entities(
                graph_id=state.graph_id,
                defined_entity_types=defined_entity_types,
                enrich_with_edges=True
            )

            state.entities_count = filtered.filtered_count
            state.entity_types = list(filtered.entity_types)

            if progress_callback:
                progress_callback(
                    "reading", 100,
                    f"완료, 총 {filtered.filtered_count}개 엔티티",
                    current=filtered.filtered_count,
                    total=filtered.filtered_count
                )

            if filtered.filtered_count == 0:
                state.status = SimulationStatus.FAILED
                state.error = "조건에 맞는 엔티티를 찾지 못했습니다. 그래프가 올바르게 구성되었는지 확인하세요."
                self._save_simulation_state(state)
                return state

            # ========== 단계 2: 에이전트 프로필 생성 ==========
            total_entities = len(filtered.entities)

            if progress_callback:
                progress_callback(
                    "generating_profiles", 0,
                    "생성 시작...",
                    current=0,
                    total=total_entities
                )

            # graph_id를 전달해 그래프 검색을 활성화하고 더 풍부한 컨텍스트를 가져옵니다.
            generator = OasisProfileGenerator(graph_id=state.graph_id)

            def profile_progress(current, total, msg):
                if progress_callback:
                    progress_callback(
                        "generating_profiles",
                        int(current / total * 100),
                        msg,
                        current=current,
                        total=total,
                        item_name=msg
                    )

            # 실시간 저장 파일 경로를 설정합니다(우선 레딧 JSON 형식 사용).
            realtime_output_path = None
            realtime_platform = "reddit"
            if state.enable_reddit:
                realtime_output_path = os.path.join(sim_dir, "reddit_profiles.json")
                realtime_platform = "reddit"
            elif state.enable_twitter:
                realtime_output_path = os.path.join(sim_dir, "twitter_profiles.csv")
                realtime_platform = "twitter"

            profiles = generator.generate_profiles_from_entities(
                entities=filtered.entities,
                use_llm=use_llm_for_profiles,
                progress_callback=profile_progress,
                graph_id=state.graph_id,  # 그래프 검색용 graph_id 전달
                parallel_count=parallel_profile_count,  # 병렬 생성 수
                realtime_output_path=realtime_output_path,  # 실시간 저장 경로
                output_platform=realtime_platform  # 출력 형식
            )

            state.profiles_count = len(profiles)

            # 프로필 파일을 저장합니다(트위터는 CSV 형식, 레딧은 JSON 형식).
            # 레딧은 생성 과정에서 이미 실시간 저장되었으므로, 여기서 한 번 더 저장해 완전성을 보장합니다.
            if progress_callback:
                progress_callback(
                    "generating_profiles", 95,
                    "프로필 파일 저장 중...",
                    current=total_entities,
                    total=total_entities
                )

            if state.enable_reddit:
                generator.save_profiles(
                    profiles=profiles,
                    file_path=os.path.join(sim_dir, "reddit_profiles.json"),
                    platform="reddit"
                )

            if state.enable_twitter:
                # 트위터는 CSV 형식을 사용합니다. OASIS 요구사항입니다.
                generator.save_profiles(
                    profiles=profiles,
                    file_path=os.path.join(sim_dir, "twitter_profiles.csv"),
                    platform="twitter"
                )

            if progress_callback:
                progress_callback(
                    "generating_profiles", 100,
                    f"완료, 총 {len(profiles)}개 프로필",
                    current=len(profiles),
                    total=len(profiles)
                )

            # ========== 단계 3: LLM으로 시뮬레이션 설정 지능 생성 ==========
            if progress_callback:
                progress_callback(
                    "generating_config", 0,
                    "시뮬레이션 요구사항 분석 중...",
                    current=0,
                    total=3
                )

            config_generator = SimulationConfigGenerator()

            if progress_callback:
                progress_callback(
                    "generating_config", 30,
                    "LLM으로 설정을 생성하는 중...",
                    current=1,
                    total=3
                )

            sim_params = config_generator.generate_config(
                simulation_id=simulation_id,
                project_id=state.project_id,
                graph_id=state.graph_id,
                simulation_requirement=simulation_requirement,
                document_text=document_text,
                entities=filtered.entities,
                enable_twitter=state.enable_twitter,
                enable_reddit=state.enable_reddit
            )

            if progress_callback:
                progress_callback(
                    "generating_config", 70,
                    "설정 파일 저장 중...",
                    current=2,
                    total=3
                )

            # 설정 파일을 저장합니다.
            config_path = os.path.join(sim_dir, "simulation_config.json")
            with open(config_path, 'w', encoding='utf-8') as f:
                f.write(sim_params.to_json())

            state.config_generated = True
            state.config_reasoning = sim_params.generation_reasoning

            if progress_callback:
                progress_callback(
                    "generating_config", 100,
                    "설정 생성이 완료되었습니다",
                    current=3,
                    total=3
                )

            # 참고: 실행 스크립트는 backend/scripts/ 디렉터리에 유지하며, 더 이상 시뮬레이션 디렉터리로 복사하지 않습니다.
            # 시뮬레이션 시작 시 simulation_runner가 scripts/ 디렉터리에서 스크립트를 실행합니다.

            # 상태를 갱신합니다.
            state.status = SimulationStatus.READY
            self._save_simulation_state(state)

            logger.info(f"시뮬레이션 준비 완료: {simulation_id}, "
                       f"entities={state.entities_count}, profiles={state.profiles_count}")

            return state

        except Exception as e:
            logger.exception("시뮬레이션 준비 실패: simulation_id=%s", simulation_id)
            state.status = SimulationStatus.FAILED
            state.error = str(e)
            self._save_simulation_state(state)
            raise

    def get_simulation(self, simulation_id: str) -> Optional[SimulationState]:
        """시뮬레이션 상태 가져오기"""
        return self._load_simulation_state(simulation_id)

    def list_simulations(self, project_id: Optional[str] = None) -> List[SimulationState]:
        """모든 시뮬레이션 목록 가져오기"""
        simulations = []

        if os.path.exists(self.SIMULATION_DATA_DIR):
            for sim_id in os.listdir(self.SIMULATION_DATA_DIR):
                # 숨김 파일(.DS_Store 등)과 디렉터리가 아닌 파일은 건너뜁니다.
                sim_path = os.path.join(self.SIMULATION_DATA_DIR, sim_id)
                if sim_id.startswith('.') or not os.path.isdir(sim_path):
                    continue

                state = self._load_simulation_state(sim_id)
                if state:
                    if project_id is None or state.project_id == project_id:
                        simulations.append(state)

        return simulations

    def get_profiles(self, simulation_id: str, platform: str = "reddit") -> List[Dict[str, Any]]:
        """시뮬레이션의 에이전트 프로필 가져오기"""
        state = self._load_simulation_state(simulation_id)
        if not state:
            raise ValueError(f"시뮬레이션이 존재하지 않습니다: {simulation_id}")

        sim_dir = self._get_simulation_dir(simulation_id)
        profiles = self._load_profiles_from_storage(sim_dir, platform)
        return self.normalize_profiles_for_display(profiles, platform)

    def normalize_profiles_for_display(
        self,
        profiles: List[Dict[str, Any]],
        platform: str = "reddit",
        localize: bool = True,
    ) -> List[Dict[str, Any]]:
        """프런트 공통 표시 형식으로 맞추고 한국어 UI 기준으로 정리한다."""
        if localize:
            return self.profile_localizer.adapt_and_localize_profiles(profiles, platform)
        return self.profile_localizer.adapt_profiles(profiles, platform)

    def _load_profiles_from_storage(self, sim_dir: str, platform: str) -> List[Dict[str, Any]]:
        """저장 파일에서 프로필을 읽는다."""
        if platform == "twitter":
            profile_path = os.path.join(sim_dir, "twitter_profiles.csv")
            if not os.path.exists(profile_path):
                return []
            with open(profile_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                return list(reader)

        profile_path = os.path.join(sim_dir, "reddit_profiles.json")
        if not os.path.exists(profile_path):
            return []

        with open(profile_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def get_simulation_config(self, simulation_id: str) -> Optional[Dict[str, Any]]:
        """시뮬레이션 설정 가져오기"""
        sim_dir = self._get_simulation_dir(simulation_id)
        config_path = os.path.join(sim_dir, "simulation_config.json")

        if not os.path.exists(config_path):
            return None

        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def get_run_instructions(self, simulation_id: str) -> Dict[str, str]:
        """실행 안내 가져오기"""
        sim_dir = self._get_simulation_dir(simulation_id)
        config_path = os.path.join(sim_dir, "simulation_config.json")
        scripts_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../scripts'))

        return {
            "simulation_dir": sim_dir,
            "scripts_dir": scripts_dir,
            "config_file": config_path,
            "commands": {
                "twitter": f"python {scripts_dir}/run_twitter_simulation.py --config {config_path}",
                "reddit": f"python {scripts_dir}/run_reddit_simulation.py --config {config_path}",
                "parallel": f"python {scripts_dir}/run_parallel_simulation.py --config {config_path}",
            },
            "instructions": (
                f"1. conda 환경 활성화: conda activate MiroFish\n"
                f"2. 시뮬레이션 실행(스크립트 위치: {scripts_dir}):\n"
                f"   - 트위터만 실행: python {scripts_dir}/run_twitter_simulation.py --config {config_path}\n"
                f"   - 레딧만 실행: python {scripts_dir}/run_reddit_simulation.py --config {config_path}\n"
                f"   - 양 플랫폼 병렬 실행: python {scripts_dir}/run_parallel_simulation.py --config {config_path}"
            )
        }
