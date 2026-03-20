"""
설정 관리
프로젝트 루트의 .env 파일에서 설정을 일괄 로드한다.
"""

import os
from dotenv import load_dotenv

# 프로젝트 루트의 .env 파일을 로드한다.
# 경로: MiroFish/.env (backend/app/config.py 기준 상대 경로)
project_root_env = os.path.join(os.path.dirname(__file__), '../../.env')

if os.path.exists(project_root_env):
    load_dotenv(project_root_env, override=True)
else:
    # 루트에 .env가 없으면 환경 변수를 로드한다. (운영 환경용)
    load_dotenv(override=True)


class Config:
    """Flask 설정 클래스"""
    
    # Flask 설정
    SECRET_KEY = os.environ.get('SECRET_KEY', 'mirofish-secret-key')
    DEBUG = os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'
    
    # JSON 설정 - ASCII 이스케이프를 비활성화하여 한글이 그대로 표시되도록 한다.
    JSON_AS_ASCII = False
    
    # LLM 설정 (OpenAI 형식으로 통일)
    LLM_API_KEY = os.environ.get('LLM_API_KEY')
    LLM_BASE_URL = os.environ.get('LLM_BASE_URL', 'https://api.openai.com/v1')
    LLM_MODEL_NAME = os.environ.get('LLM_MODEL_NAME', 'gpt-4o-mini')
    LLM_REQUEST_TIMEOUT = float(os.environ.get('LLM_REQUEST_TIMEOUT', '180'))
    LLM_MAX_RETRIES = int(os.environ.get('LLM_MAX_RETRIES', '3'))
    
    # 파일 업로드 설정
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB
    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), '../uploads')
    LOCAL_GRAPH_FOLDER = os.path.join(UPLOAD_FOLDER, 'graphs')
    ALLOWED_EXTENSIONS = {'pdf', 'md', 'txt', 'markdown'}
    
    # 텍스트 처리 설정
    DEFAULT_CHUNK_SIZE = 500  # 기본 청크 크기
    DEFAULT_CHUNK_OVERLAP = 50  # 기본 오버랩 크기
    GRAPH_BUILD_BATCH_SIZE = int(
        os.environ.get('GRAPH_BUILD_BATCH_SIZE', os.environ.get('DEFAULT_GRAPH_BATCH_SIZE', '3'))
    )
    GRAPH_BUILD_PARALLEL_WORKERS = int(os.environ.get('GRAPH_BUILD_PARALLEL_WORKERS', '4'))
    GRAPH_BUILD_MAX_PARALLEL_WORKERS = int(os.environ.get('GRAPH_BUILD_MAX_PARALLEL_WORKERS', '16'))
    FILE_EXTRACTION_PARALLEL_WORKERS = int(
        os.environ.get('FILE_EXTRACTION_PARALLEL_WORKERS', os.environ.get('FILE_PARSE_PARALLEL_WORKERS', '4'))
    )
    LLM_MAX_PARALLEL_REQUESTS = int(os.environ.get('LLM_MAX_PARALLEL_REQUESTS', '0'))
    LLM_CAPABILITY_REQUEST_TIMEOUT = float(os.environ.get('LLM_CAPABILITY_REQUEST_TIMEOUT', '3'))
    LLM_CAPABILITY_CACHE_TTL_SECONDS = int(os.environ.get('LLM_CAPABILITY_CACHE_TTL_SECONDS', '30'))

    # 기존 이름과의 호환 별칭
    DEFAULT_GRAPH_BATCH_SIZE = GRAPH_BUILD_BATCH_SIZE
    FILE_PARSE_PARALLEL_WORKERS = FILE_EXTRACTION_PARALLEL_WORKERS
    
    # OASIS 시뮬레이션 설정
    OASIS_DEFAULT_MAX_ROUNDS = int(os.environ.get('OASIS_DEFAULT_MAX_ROUNDS', '10'))
    OASIS_SIMULATION_DATA_DIR = os.path.join(os.path.dirname(__file__), '../uploads/simulations')
    
    # OASIS 플랫폼 사용 가능 액션 설정
    OASIS_TWITTER_ACTIONS = [
        'CREATE_POST', 'LIKE_POST', 'REPOST', 'FOLLOW', 'DO_NOTHING', 'QUOTE_POST'
    ]
    OASIS_REDDIT_ACTIONS = [
        'LIKE_POST', 'DISLIKE_POST', 'CREATE_POST', 'CREATE_COMMENT',
        'LIKE_COMMENT', 'DISLIKE_COMMENT', 'SEARCH_POSTS', 'SEARCH_USER',
        'TREND', 'REFRESH', 'DO_NOTHING', 'FOLLOW', 'MUTE'
    ]
    
    # Report Agent 설정
    REPORT_AGENT_MAX_TOOL_CALLS = int(os.environ.get('REPORT_AGENT_MAX_TOOL_CALLS', '5'))
    REPORT_AGENT_MAX_REFLECTION_ROUNDS = int(os.environ.get('REPORT_AGENT_MAX_REFLECTION_ROUNDS', '2'))
    @classmethod
    def validate(cls):
        """필수 설정을 검증한다"""
        errors = []
        if not cls.LLM_API_KEY:
            errors.append("LLM_API_KEY가 설정되지 않음")
        return errors
