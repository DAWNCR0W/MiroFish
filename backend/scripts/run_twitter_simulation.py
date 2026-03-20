"""
OASIS Twitter 시뮬레이션 사전 설정 스크립트
이 스크립트는 구성 파일의 매개변수를 읽어 시뮬레이션을 실행하며, 전체 과정을 자동화한다.

기능:
- 시뮬레이션이 끝나도 환경을 바로 닫지 않고 대기 명령 모드로 진입
- IPC를 통해 Interview 명령 수신 지원
- 단일 Agent 인터뷰와 일괄 인터뷰 지원
- 원격 환경 종료 명령 지원

사용 방법:
    python run_twitter_simulation.py --config /path/to/simulation_config.json
    python run_twitter_simulation.py --config /path/to/simulation_config.json --no-wait  # 완료 후 즉시 종료
"""

import argparse
import asyncio
import json
import logging
import os
import random
import signal
import sys
import sqlite3
from datetime import datetime
from typing import Dict, Any, List, Optional

# 전역 변수: 신호 처리용
_shutdown_event = None
_cleanup_done = False

# 프로젝트 경로 추가
_scripts_dir = os.path.dirname(os.path.abspath(__file__))
_backend_dir = os.path.abspath(os.path.join(_scripts_dir, '..'))
_project_root = os.path.abspath(os.path.join(_backend_dir, '..'))
sys.path.insert(0, _scripts_dir)
sys.path.insert(0, _backend_dir)

from llm_runtime_config import load_runtime_env, resolve_llm_runtime_config

load_runtime_env(_project_root, _backend_dir)


import re


class UnicodeFormatter(logging.Formatter):
    """Unicode 이스케이프 시퀀스를 읽을 수 있는 문자로 변환하는 사용자 정의 포매터"""
    
    UNICODE_ESCAPE_PATTERN = re.compile(r'\\u([0-9a-fA-F]{4})')
    
    def format(self, record):
        result = super().format(record)
        
        def replace_unicode(match):
            try:
                return chr(int(match.group(1), 16))
            except (ValueError, OverflowError):
                return match.group(0)
        
        return self.UNICODE_ESCAPE_PATTERN.sub(replace_unicode, result)


class MaxTokensWarningFilter(logging.Filter):
    """camel-ai의 max_tokens 경고를 걸러낸다(의도적으로 max_tokens를 설정하지 않아 모델이 스스로 결정하게 한다)"""
    
    def filter(self, record):
        # max_tokens 경고가 포함된 로그를 필터링
        if "max_tokens" in record.getMessage() and "Invalid or missing" in record.getMessage():
            return False
        return True


# 모듈 로드 시 즉시 필터를 추가해 camel 코드 실행 전에 적용되도록 한다
logging.getLogger().addFilter(MaxTokensWarningFilter())


def setup_oasis_logging(log_dir: str):
    """OASIS 로그를 설정하며 고정 이름의 로그 파일을 사용한다"""
    os.makedirs(log_dir, exist_ok=True)
    
    # 기존 로그 파일을 정리
    for f in os.listdir(log_dir):
        old_log = os.path.join(log_dir, f)
        if os.path.isfile(old_log) and f.endswith('.log'):
            try:
                os.remove(old_log)
            except OSError:
                pass
    
    formatter = UnicodeFormatter("%(levelname)s - %(asctime)s - %(name)s - %(message)s")
    
    loggers_config = {
        "social.agent": os.path.join(log_dir, "social.agent.log"),
        "social.twitter": os.path.join(log_dir, "social.twitter.log"),
        "social.rec": os.path.join(log_dir, "social.rec.log"),
        "oasis.env": os.path.join(log_dir, "oasis.env.log"),
        "table": os.path.join(log_dir, "table.log"),
    }
    
    for logger_name, log_file in loggers_config.items():
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.DEBUG)
        logger.handlers.clear()
        file_handler = logging.FileHandler(log_file, encoding='utf-8', mode='w')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        logger.propagate = False


try:
    from camel.models import ModelFactory
    from camel.types import ModelPlatformType
    import oasis
    from oasis import (
        ActionType,
        LLMAction,
        ManualAction,
        generate_twitter_agent_graph
    )
except ImportError as e:
    print(f"오류: 종속성이 부족합니다 {e}")
    print("먼저 설치하세요: pip install oasis-ai camel-ai")
    sys.exit(1)


# IPC 관련 상수
IPC_COMMANDS_DIR = "ipc_commands"
IPC_RESPONSES_DIR = "ipc_responses"
ENV_STATUS_FILE = "env_status.json"

class CommandType:
    """명령 유형 상수"""
    INTERVIEW = "interview"
    BATCH_INTERVIEW = "batch_interview"
    CLOSE_ENV = "close_env"


class IPCHandler:
    """IPC 명령 처리기"""
    
    def __init__(self, simulation_dir: str, env, agent_graph):
        self.simulation_dir = simulation_dir
        self.env = env
        self.agent_graph = agent_graph
        self.commands_dir = os.path.join(simulation_dir, IPC_COMMANDS_DIR)
        self.responses_dir = os.path.join(simulation_dir, IPC_RESPONSES_DIR)
        self.status_file = os.path.join(simulation_dir, ENV_STATUS_FILE)
        self._running = True
        
        # 디렉터리가 존재하도록 보장
        os.makedirs(self.commands_dir, exist_ok=True)
        os.makedirs(self.responses_dir, exist_ok=True)
    
    def update_status(self, status: str):
        """환경 상태를 갱신한다"""
        with open(self.status_file, 'w', encoding='utf-8') as f:
            json.dump({
                "status": status,
                "timestamp": datetime.now().isoformat()
            }, f, ensure_ascii=False, indent=2)
    
    def poll_command(self) -> Optional[Dict[str, Any]]:
        """처리 대기 중인 명령을 폴링한다"""
        if not os.path.exists(self.commands_dir):
            return None
        
        # 명령 파일을 가져온다(시간순 정렬)
        command_files = []
        for filename in os.listdir(self.commands_dir):
            if filename.endswith('.json'):
                filepath = os.path.join(self.commands_dir, filename)
                command_files.append((filepath, os.path.getmtime(filepath)))
        
        command_files.sort(key=lambda x: x[1])
        
        for filepath, _ in command_files:
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                continue
        
        return None
    
    def send_response(self, command_id: str, status: str, result: Dict = None, error: str = None):
        """응답을 전송한다"""
        response = {
            "command_id": command_id,
            "status": status,
            "result": result,
            "error": error,
            "timestamp": datetime.now().isoformat()
        }
        
        response_file = os.path.join(self.responses_dir, f"{command_id}.json")
        with open(response_file, 'w', encoding='utf-8') as f:
            json.dump(response, f, ensure_ascii=False, indent=2)
        
        # 명령 파일 삭제
        command_file = os.path.join(self.commands_dir, f"{command_id}.json")
        try:
            os.remove(command_file)
        except OSError:
            pass
    
    async def handle_interview(self, command_id: str, agent_id: int, prompt: str) -> bool:
        """
        단일 Agent 인터뷰 명령을 처리한다

        반환값:
            True는 성공, False는 실패를 의미한다
        """
        try:
            # Agent 가져오기
            agent = self.agent_graph.get_agent(agent_id)
            
            # Interview 동작 생성
            interview_action = ManualAction(
                action_type=ActionType.INTERVIEW,
                action_args={"prompt": prompt}
            )
            
            # Interview 실행
            actions = {agent: interview_action}
            await self.env.step(actions)
            
            # 데이터베이스에서 결과를 가져오기
            result = self._get_interview_result(agent_id)
            
            self.send_response(command_id, "completed", result=result)
            print(f"  Interview 완료: agent_id={agent_id}")
            return True
            
        except Exception as e:
            error_msg = str(e)
            print(f"  Interview 실패: agent_id={agent_id}, 오류={error_msg}")
            self.send_response(command_id, "failed", error=error_msg)
            return False
    
    async def handle_batch_interview(self, command_id: str, interviews: List[Dict]) -> bool:
        """
        일괄 인터뷰 명령을 처리한다

        인자:
            interviews: [{"agent_id": int, "prompt": str}, ...]
        """
        try:
            # 동작 딕셔너리 구성
            actions = {}
            agent_prompts = {}  # 각 agent의 prompt를 기록
            
            for interview in interviews:
                agent_id = interview.get("agent_id")
                prompt = interview.get("prompt", "")
                
                try:
                    agent = self.agent_graph.get_agent(agent_id)
                    actions[agent] = ManualAction(
                        action_type=ActionType.INTERVIEW,
                        action_args={"prompt": prompt}
                    )
                    agent_prompts[agent_id] = prompt
                except Exception as e:
                    print(f"  경고: Agent를 가져올 수 없습니다 {agent_id}: {e}")
            
            if not actions:
                self.send_response(command_id, "failed", error="유효한 Agent가 없습니다")
                return False
            
            # 일괄 Interview 실행
            await self.env.step(actions)
            
            # 모든 결과를 가져온다
            results = {}
            for agent_id in agent_prompts.keys():
                result = self._get_interview_result(agent_id)
                results[agent_id] = result
            
            self.send_response(command_id, "completed", result={
                "interviews_count": len(results),
                "results": results
            })
            print(f"  일괄 Interview 완료: Agent {len(results)}명")
            return True
            
        except Exception as e:
            error_msg = str(e)
            print(f"  일괄 Interview 실패: {error_msg}")
            self.send_response(command_id, "failed", error=error_msg)
            return False
    
    def _get_interview_result(self, agent_id: int) -> Dict[str, Any]:
        """데이터베이스에서 최신 Interview 결과를 가져온다"""
        db_path = os.path.join(self.simulation_dir, "twitter_simulation.db")
        
        result = {
            "agent_id": agent_id,
            "response": None,
            "timestamp": None
        }
        
        if not os.path.exists(db_path):
            return result
        
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # 최신 Interview 기록을 조회한다
            cursor.execute("""
                SELECT user_id, info, created_at
                FROM trace
                WHERE action = ? AND user_id = ?
                ORDER BY created_at DESC
                LIMIT 1
            """, (ActionType.INTERVIEW.value, agent_id))
            
            row = cursor.fetchone()
            if row:
                user_id, info_json, created_at = row
                try:
                    info = json.loads(info_json) if info_json else {}
                    result["response"] = info.get("response", info)
                    result["timestamp"] = created_at
                except json.JSONDecodeError:
                    result["response"] = info_json
            
            conn.close()
            
        except Exception as e:
            print(f"  Interview 결과 읽기 실패: {e}")
        
        return result
    
    async def process_commands(self) -> bool:
        """
        처리 대기 중인 모든 명령을 처리한다
        
        반환값:
            True는 계속 실행, False는 종료를 의미한다
        """
        command = self.poll_command()
        if not command:
            return True
        
        command_id = command.get("command_id")
        command_type = command.get("command_type")
        args = command.get("args", {})
        
        print(f"\nIPC 명령 수신: {command_type}, id={command_id}")
        
        if command_type == CommandType.INTERVIEW:
            await self.handle_interview(
                command_id,
                args.get("agent_id", 0),
                args.get("prompt", "")
            )
            return True
            
        elif command_type == CommandType.BATCH_INTERVIEW:
            await self.handle_batch_interview(
                command_id,
                args.get("interviews", [])
            )
            return True
            
        elif command_type == CommandType.CLOSE_ENV:
            print("환경 종료 명령을 수신했습니다")
            self.send_response(command_id, "completed", result={"message": "환경을 곧 종료합니다"})
            return False
        
        else:
            self.send_response(command_id, "failed", error=f"알 수 없는 명령 유형: {command_type}")
            return True


class TwitterSimulationRunner:
    """Twitter 시뮬레이션 실행기"""
    
    # Twitter 사용 가능 동작(Interview는 포함하지 않으며, ManualAction으로만 수동 트리거 가능)
    AVAILABLE_ACTIONS = [
        ActionType.CREATE_POST,
        ActionType.LIKE_POST,
        ActionType.REPOST,
        ActionType.FOLLOW,
        ActionType.DO_NOTHING,
        ActionType.QUOTE_POST,
    ]
    
    def __init__(self, config_path: str, wait_for_commands: bool = True):
        """
        시뮬레이션 실행기를 초기화한다
        
        인자:
            config_path: 구성 파일 경로 (simulation_config.json)
            wait_for_commands: 시뮬레이션 완료 후 명령을 대기할지 여부(기본 True)
        """
        self.config_path = config_path
        self.config = self._load_config()
        self.simulation_dir = os.path.dirname(config_path)
        self.wait_for_commands = wait_for_commands
        self.env = None
        self.agent_graph = None
        self.ipc_handler = None
        
    def _load_config(self) -> Dict[str, Any]:
        """구성 파일을 불러온다"""
        with open(self.config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def _get_profile_path(self) -> str:
        """Profile 파일 경로를 가져온다. OASIS Twitter는 CSV 형식을 사용한다."""
        return os.path.join(self.simulation_dir, "twitter_profiles.csv")
    
    def _get_db_path(self) -> str:
        """데이터베이스 경로를 가져온다"""
        return os.path.join(self.simulation_dir, "twitter_simulation.db")
    
    def _create_model(self):
        """
        LLM 모델을 생성한다

        프로젝트 루트의 `.env` 파일 설정을 통일해서 사용한다(최우선):
        - LLM_API_KEY: API 키
        - LLM_BASE_URL: API 기본 URL
        - LLM_MODEL_NAME: 모델 이름
        """
        runtime = resolve_llm_runtime_config(self.config, use_boost=False)
        print(
            f"LLM 설정: model={runtime['model']}, "
            f"base_url={runtime['base_url'][:40] if runtime['base_url'] else '기본값'}..., "
            f"source={runtime['source']}"
        )
        
        return ModelFactory.create(
            model_platform=ModelPlatformType.OPENAI,
            model_type=runtime["model"],
            api_key=runtime["api_key"],
            url=runtime["base_url"] or None,
            timeout=runtime["timeout"],
            max_retries=runtime["max_retries"],
        )
    
    def _get_active_agents_for_round(
        self, 
        env, 
        current_hour: int,
        round_num: int
    ) -> List:
        """
        시간과 설정에 따라 이번 라운드에 활성화할 Agent를 결정한다
        
        인자:
            env: OASIS 환경
            current_hour: 현재 시뮬레이션 시간(0-23)
            round_num: 현재 라운드 수
            
        반환값:
            활성화된 Agent 목록
        """
        time_config = self.config.get("time_config", {})
        agent_configs = self.config.get("agent_configs", [])
        
        # 기본 활성화 수
        base_min = time_config.get("agents_per_hour_min", 5)
        base_max = time_config.get("agents_per_hour_max", 20)
        
        # 시간대에 따라 조정
        peak_hours = time_config.get("peak_hours", [9, 10, 11, 14, 15, 20, 21, 22])
        off_peak_hours = time_config.get("off_peak_hours", [0, 1, 2, 3, 4, 5])
        
        if current_hour in peak_hours:
            multiplier = time_config.get("peak_activity_multiplier", 1.5)
        elif current_hour in off_peak_hours:
            multiplier = time_config.get("off_peak_activity_multiplier", 0.3)
        else:
            multiplier = 1.0
        
        target_count = int(random.uniform(base_min, base_max) * multiplier)
        
        # 각 Agent 설정을 바탕으로 활성화 확률 계산
        candidates = []
        for cfg in agent_configs:
            agent_id = cfg.get("agent_id", 0)
            active_hours = cfg.get("active_hours", list(range(8, 23)))
            activity_level = cfg.get("activity_level", 0.5)
            
            # 활성 시간인지 확인
            if current_hour not in active_hours:
                continue
            
            # 활동도에 따라 확률 계산
            if random.random() < activity_level:
                candidates.append(agent_id)
        
        # 무작위 선택
        selected_ids = random.sample(
            candidates, 
            min(target_count, len(candidates))
        ) if candidates else []
        
        # Agent 객체로 변환
        active_agents = []
        for agent_id in selected_ids:
            try:
                agent = env.agent_graph.get_agent(agent_id)
                active_agents.append((agent_id, agent))
            except Exception:
                pass
        
        return active_agents
    
    async def run(self, max_rounds: int = None):
        """Twitter 시뮬레이션을 실행한다
        
        인자:
            max_rounds: 최대 시뮬레이션 라운드 수(선택, 너무 긴 시뮬레이션을 잘라내기용)
        """
        print("=" * 60)
        print("OASIS Twitter 시뮬레이션")
        print(f"구성 파일: {self.config_path}")
        print(f"시뮬레이션 ID: {self.config.get('simulation_id', 'unknown')}")
        print(f"명령 대기 모드: {'활성화' if self.wait_for_commands else '비활성화'}")
        print("=" * 60)
        
        # 시간 설정을 불러온다
        time_config = self.config.get("time_config", {})
        total_hours = time_config.get("total_simulation_hours", 72)
        minutes_per_round = time_config.get("minutes_per_round", 30)
        
        # 총 라운드 수를 계산한다
        total_rounds = (total_hours * 60) // minutes_per_round
        
        # 최대 라운드 수가 지정되면 잘라낸다
        if max_rounds is not None and max_rounds > 0:
            original_rounds = total_rounds
            total_rounds = min(total_rounds, max_rounds)
            if total_rounds < original_rounds:
                print(f"\n라운드 수를 잘라냈습니다: {original_rounds} -> {total_rounds} (max_rounds={max_rounds})")
        
        print(f"\n시뮬레이션 매개변수:")
        print(f"  - 총 시뮬레이션 시간: {total_hours}시간")
        print(f"  - 라운드당 시간: {minutes_per_round}분")
        print(f"  - 총 라운드 수: {total_rounds}")
        if max_rounds:
            print(f"  - 최대 라운드 제한: {max_rounds}")
        print(f"  - Agent 수: {len(self.config.get('agent_configs', []))}")
        
        # 모델을 생성한다
        print("\nLLM 모델 초기화...")
        model = self._create_model()
        
        # Agent 그래프를 불러온다
        print("Agent Profile 불러오기...")
        profile_path = self._get_profile_path()
        if not os.path.exists(profile_path):
            print(f"오류: Profile 파일이 존재하지 않습니다: {profile_path}")
            return
        
        self.agent_graph = await generate_twitter_agent_graph(
            profile_path=profile_path,
            model=model,
            available_actions=self.AVAILABLE_ACTIONS,
        )
        
        # 데이터베이스 경로
        db_path = self._get_db_path()
        if os.path.exists(db_path):
            os.remove(db_path)
            print(f"기존 데이터베이스를 삭제했습니다: {db_path}")
        
        # 환경을 생성한다
        print("OASIS 환경 생성...")
        self.env = oasis.make(
            agent_graph=self.agent_graph,
            platform=oasis.DefaultPlatformType.TWITTER,
            database_path=db_path,
            semaphore=30,  # 최대 동시 LLM 요청 수를 제한해 API 과부하를 방지한다
        )
        
        await self.env.reset()
        print("환경 초기화 완료\n")
        
        # IPC 처리기를 초기화한다
        self.ipc_handler = IPCHandler(self.simulation_dir, self.env, self.agent_graph)
        self.ipc_handler.update_status("running")
        
        # 초기 이벤트 실행
        event_config = self.config.get("event_config", {})
        initial_posts = event_config.get("initial_posts", [])
        
        if initial_posts:
            print(f"초기 이벤트 실행 ({len(initial_posts)}개의 초기 게시글)...")
            initial_actions = {}
            for post in initial_posts:
                agent_id = post.get("poster_agent_id", 0)
                content = post.get("content", "")
                try:
                    agent = self.env.agent_graph.get_agent(agent_id)
                    initial_actions[agent] = ManualAction(
                        action_type=ActionType.CREATE_POST,
                        action_args={"content": content}
                    )
                except Exception as e:
                    print(f"  경고: Agent {agent_id}의 초기 게시글을 만들 수 없습니다: {e}")
            
            if initial_actions:
                await self.env.step(initial_actions)
                print(f"  초기 게시글 {len(initial_actions)}개 게시 완료")
        
        # 메인 시뮬레이션 루프
        print("\n시뮬레이션 루프 시작...")
        start_time = datetime.now()
        
        for round_num in range(total_rounds):
            # 현재 시뮬레이션 시간을 계산한다
            simulated_minutes = round_num * minutes_per_round
            simulated_hour = (simulated_minutes // 60) % 24
            simulated_day = simulated_minutes // (60 * 24) + 1
            
            # 이번 라운드에서 활성화할 Agent를 가져온다
            active_agents = self._get_active_agents_for_round(
                self.env, simulated_hour, round_num
            )
            
            if not active_agents:
                continue
            
            # 동작을 구성한다
            actions = {
                agent: LLMAction()
                for _, agent in active_agents
            }
            
            # 동작을 실행한다
            await self.env.step(actions)
            
            # 진행 상황 출력
            if (round_num + 1) % 10 == 0 or round_num == 0:
                elapsed = (datetime.now() - start_time).total_seconds()
                progress = (round_num + 1) / total_rounds * 100
                print(f"  [일 {simulated_day}, {simulated_hour:02d}:00] "
                      f"라운드 {round_num + 1}/{total_rounds} ({progress:.1f}%) "
                      f"- 활성 agent {len(active_agents)}명 "
                      f"- 경과 시간: {elapsed:.1f}초")
        
        total_elapsed = (datetime.now() - start_time).total_seconds()
        print(f"\n시뮬레이션 루프 완료!")
        print(f"  - 총 소요 시간: {total_elapsed:.1f}초")
        print(f"  - 데이터베이스: {db_path}")
        
        # 명령 대기 모드에 들어갈지 결정한다
        if self.wait_for_commands:
            print("\n" + "=" * 60)
            print("명령 대기 모드에 진입합니다. 환경을 계속 유지합니다")
            print("지원되는 명령: interview, batch_interview, close_env")
            print("=" * 60)
            
            self.ipc_handler.update_status("alive")
            
            # 명령 대기 루프(전역 _shutdown_event 사용)
            try:
                while not _shutdown_event.is_set():
                    should_continue = await self.ipc_handler.process_commands()
                    if not should_continue:
                        break
                    try:
                        await asyncio.wait_for(_shutdown_event.wait(), timeout=0.5)
                        break  # 종료 신호를 받았다
                    except asyncio.TimeoutError:
                        pass
            except KeyboardInterrupt:
                print("\n중단 신호를 받았습니다")
            except asyncio.CancelledError:
                print("\n작업이 취소되었습니다")
            except Exception as e:
                print(f"\n명령 처리 오류: {e}")
            
            print("\n환경 종료...")
        
        # 환경 종료
        self.ipc_handler.update_status("stopped")
        await self.env.close()
        
        print("환경이 종료되었습니다")
        print("=" * 60)


async def main():
    parser = argparse.ArgumentParser(description='OASIS Twitter 시뮬레이션')
    parser.add_argument(
        '--config', 
        type=str, 
        required=True,
        help='구성 파일 경로 (simulation_config.json)'
    )
    parser.add_argument(
        '--max-rounds',
        type=int,
        default=None,
        help='최대 시뮬레이션 라운드 수(선택, 너무 긴 시뮬레이션을 잘라내기용)'
    )
    parser.add_argument(
        '--no-wait',
        action='store_true',
        default=False,
        help='시뮬레이션 완료 후 즉시 환경을 종료하고 명령 대기 모드로 들어가지 않습니다'
    )
    
    args = parser.parse_args()
    
    # main 함수 시작 시 shutdown 이벤트를 생성한다
    global _shutdown_event
    _shutdown_event = asyncio.Event()
    
    if not os.path.exists(args.config):
        print(f"오류: 구성 파일이 존재하지 않습니다: {args.config}")
        sys.exit(1)
    
    # 로그 설정 초기화（고정 파일명을 사용하고 기존 로그를 정리한다）
    simulation_dir = os.path.dirname(args.config) or "."
    setup_oasis_logging(os.path.join(simulation_dir, "log"))
    
    runner = TwitterSimulationRunner(
        config_path=args.config,
        wait_for_commands=not args.no_wait
    )
    await runner.run(max_rounds=args.max_rounds)


def setup_signal_handlers():
    """
    SIGTERM/SIGINT를 받았을 때 올바르게 종료되도록 신호 처리기를 설정한다
    프로그램이 리소스를 정상적으로 정리할 기회를 준다(데이터베이스, 환경 등을 종료)
    """
    def signal_handler(signum, frame):
        global _cleanup_done
        sig_name = "SIGTERM" if signum == signal.SIGTERM else "SIGINT"
        print(f"\n{sig_name} 신호를 수신했습니다. 종료하는 중...")
        if not _cleanup_done:
            _cleanup_done = True
            if _shutdown_event:
                _shutdown_event.set()
        else:
            # 신호를 반복해서 받을 때만 강제 종료한다
            print("강제 종료...")
            sys.exit(1)
    
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)


if __name__ == "__main__":
    setup_signal_handlers()
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n프로그램이 중단되었습니다")
    except SystemExit:
        pass
    finally:
        print("시뮬레이션 프로세스가 종료되었습니다")
