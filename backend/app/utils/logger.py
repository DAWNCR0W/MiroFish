"""
로그 설정 모듈
콘솔과 파일에 동시에 출력하는 통합 로그 관리를 제공한다.
"""

import logging
import os
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler
from typing import Optional


def _ensure_utf8_stdout():
    """
    stdout/stderr가 UTF-8 인코딩을 사용하도록 보장한다.
    Windows 콘솔에서 한글 깨짐 문제를 방지한다.
    """
    if sys.platform == 'win32':
        # Windows에서는 표준 출력을 UTF-8로 다시 설정한다.
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        if hasattr(sys.stderr, 'reconfigure'):
            sys.stderr.reconfigure(encoding='utf-8', errors='replace')


# 로그 디렉터리
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'logs')


def resolve_log_level(value: Optional[str], default: int = logging.INFO) -> int:
    """
    환경 변수나 문자열로부터 logging level을 안전하게 계산한다.
    """
    if value is None:
        return default

    if isinstance(value, int):
        return value

    if isinstance(value, str):
        normalized = value.strip().upper()
        if normalized.isdigit():
            return int(normalized)
        return getattr(logging, normalized, default)

    return default


def setup_logger(name: str = 'mirofish', level: Optional[int] = None) -> logging.Logger:
    """
    로거를 설정한다.
    
    Args:
        name: 로거 이름
        level: 로그 레벨
        
    Returns:
        설정된 로거
    """
    if level is None:
        default_level = logging.DEBUG if os.environ.get("FLASK_DEBUG", "false").strip().lower() in {"1", "true", "yes", "on"} else logging.INFO
        level = resolve_log_level(os.environ.get("MIROFISH_LOG_LEVEL"), default_level)

    console_level = resolve_log_level(os.environ.get("MIROFISH_CONSOLE_LOG_LEVEL"), logging.INFO)

    # 로그 디렉터리가 존재하는지 확인한다.
    os.makedirs(LOG_DIR, exist_ok=True)
    
    # 로거를 생성한다.
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # 로그가 루트 logger로 전파되지 않도록 막아 중복 출력을 방지한다.
    logger.propagate = False
    
    # 이미 핸들러가 있으면 중복으로 추가하지 않는다.
    if logger.handlers:
        return logger
    
    # 로그 포맷
    detailed_formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)s [%(name)s.%(funcName)s:%(lineno)d] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    simple_formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)s: %(message)s',
        datefmt='%H:%M:%S'
    )
    
    # 1. 파일 핸들러 - 상세 로그 (날짜별 파일명, 로테이션 포함)
    log_filename = datetime.now().strftime('%Y-%m-%d') + '.log'
    file_handler = RotatingFileHandler(
        os.path.join(LOG_DIR, log_filename),
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(detailed_formatter)
    
    # 2. 콘솔 핸들러 - 간단한 로그 (INFO 이상)
    # Windows에서 UTF-8 인코딩을 사용해 한글 깨짐을 방지한다.
    _ensure_utf8_stdout()
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(console_level)
    console_handler.setFormatter(simple_formatter)
    
    # 핸들러를 추가한다.
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger


def get_logger(name: str = 'mirofish') -> logging.Logger:
    """
    로거를 가져온다. (없으면 생성)
    
    Args:
        name: 로거 이름
        
    Returns:
        로거 인스턴스
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        return setup_logger(name)
    return logger


# 기본 로거를 생성한다.
logger = setup_logger()


# 편의 함수
def debug(msg, *args, **kwargs):
    logger.debug(msg, *args, **kwargs)

def info(msg, *args, **kwargs):
    logger.info(msg, *args, **kwargs)

def warning(msg, *args, **kwargs):
    logger.warning(msg, *args, **kwargs)

def error(msg, *args, **kwargs):
    logger.error(msg, *args, **kwargs)

def critical(msg, *args, **kwargs):
    logger.critical(msg, *args, **kwargs)
