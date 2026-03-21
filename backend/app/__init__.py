"""
MiroFish 백엔드 - Flask 애플리케이션 팩토리
"""

import json
import logging
import os
import time
import uuid
import warnings

# multiprocessing resource_tracker 경고를 억제한다. (transformers 같은 서드파티 라이브러리에서 발생)
# 다른 모든 import보다 먼저 설정해야 한다.
warnings.filterwarnings("ignore", message=".*resource_tracker.*")

from flask import Flask, g, request
from flask_cors import CORS

from .config import Config
from .utils.api_errors import strip_debug_error_fields
from .utils.logger import setup_logger, get_logger


def _summarize_json_payload(payload):
    """요청 본문 전체 대신 구조 요약만 로그에 남긴다."""
    if isinstance(payload, dict):
        return {
            "type": "object",
            "key_count": len(payload),
            "keys": list(payload.keys())[:10],
        }

    if isinstance(payload, list):
        return {
            "type": "list",
            "length": len(payload),
        }

    if payload is None:
        return None

    return {"type": type(payload).__name__}


def _summarize_request():
    summary = {
        "content_type": request.content_type,
        "content_length": request.content_length,
    }

    if request.files:
        summary["files"] = {
            "count": len(request.files),
            "field_names": sorted(request.files.keys()),
        }

    if request.form:
        form_keys = sorted(request.form.keys())
        summary["form"] = {
            "key_count": len(form_keys),
            "keys": form_keys[:10],
        }

    if request.content_type and 'json' in request.content_type:
        summary["body"] = _summarize_json_payload(request.get_json(silent=True))

    return summary


def create_app(config_class=Config):
    """Flask 애플리케이션 팩토리 함수"""
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # JSON 인코딩 설정: 한글이 \uXXXX 형식이 아니라 그대로 표시되도록 한다.
    # Flask >= 2.3에서는 app.json.ensure_ascii를 사용하고, 구버전에서는 JSON_AS_ASCII 설정을 사용한다.
    if hasattr(app, 'json') and hasattr(app.json, 'ensure_ascii'):
        app.json.ensure_ascii = False
    
    # 로거 설정
    logger = setup_logger('mirofish')
    
    # reloader 자식 프로세스에서만 시작 정보를 출력한다. (debug 모드에서 중복 출력 방지)
    is_reloader_process = os.environ.get('WERKZEUG_RUN_MAIN') == 'true'
    debug_mode = app.config.get('DEBUG', False)
    should_log_startup = not debug_mode or is_reloader_process
    
    if should_log_startup:
        logger.info("=" * 50)
        logger.info("MiroFish 백엔드 시작 중...")
        logger.info("=" * 50)
    
    # CORS 활성화
    CORS(app, resources={r"/api/*": {"origins": "*"}})
    
    # 시뮬레이션 프로세스 정리 함수를 등록한다. (서버 종료 시 모든 시뮬레이션 프로세스 종료 보장)
    from .services.simulation_runner import SimulationRunner
    SimulationRunner.register_cleanup()
    if should_log_startup:
        logger.info("시뮬레이션 프로세스 정리 함수가 등록됨")
    
    # 요청 로그 미들웨어
    @app.before_request
    def log_request():
        g.request_id = uuid.uuid4().hex[:12]
        g.request_started_at = time.perf_counter()
        logger = get_logger('mirofish.request')

        if not logger.isEnabledFor(logging.DEBUG):
            return

        logger.debug(
            "요청: request_id=%s method=%s path=%s summary=%s",
            g.request_id,
            request.method,
            request.path,
            _summarize_request(),
        )
    
    @app.after_request
    def log_response(response):
        logger = get_logger('mirofish.request')
        request_id = getattr(g, 'request_id', None)
        duration_ms = None
        if hasattr(g, 'request_started_at'):
            duration_ms = round((time.perf_counter() - g.request_started_at) * 1000, 1)
        if request_id:
            response.headers['X-Request-ID'] = request_id

        if response.is_json:
            payload = response.get_json(silent=True)
            if isinstance(payload, (dict, list)):
                if isinstance(payload, dict) and payload.get('traceback'):
                    logger.error(
                        "요청 실패: request_id=%s method=%s path=%s status=%s error=%s\n%s",
                        request_id,
                        request.method,
                        request.path,
                        response.status_code,
                        payload.get('error'),
                        payload.get('traceback'),
                    )
                sanitized_payload = (
                    strip_debug_error_fields(payload, include_debug=app.config.get('DEBUG', False))
                    if isinstance(payload, dict)
                    else payload
                )
                if sanitized_payload != payload:
                    if isinstance(sanitized_payload, dict) and response.status_code >= 500:
                        sanitized_payload['error'] = "서버 내부 오류가 발생했습니다. 잠시 후 다시 시도해 주세요."
                        sanitized_payload['request_id'] = request_id
                    response.set_data(json.dumps(sanitized_payload, ensure_ascii=False))
                    response.headers['Content-Type'] = 'application/json; charset=utf-8'
                    response.content_length = len(response.get_data())

        if response.status_code >= 500:
            logger.error(
                "응답: request_id=%s method=%s path=%s status=%s duration_ms=%s",
                request_id,
                request.method,
                request.path,
                response.status_code,
                duration_ms if duration_ms is not None else "-",
            )
        elif response.status_code >= 400:
            logger.warning(
                "응답: request_id=%s method=%s path=%s status=%s duration_ms=%s",
                request_id,
                request.method,
                request.path,
                response.status_code,
                duration_ms if duration_ms is not None else "-",
            )
        else:
            logger.debug(
                "응답: request_id=%s method=%s path=%s status=%s duration_ms=%s",
                request_id,
                request.method,
                request.path,
                response.status_code,
                duration_ms if duration_ms is not None else "-",
            )
        return response
    
    # 블루프린트 등록
    from .api import graph_bp, simulation_bp, report_bp
    app.register_blueprint(graph_bp, url_prefix='/api/graph')
    app.register_blueprint(simulation_bp, url_prefix='/api/simulation')
    app.register_blueprint(report_bp, url_prefix='/api/report')
    
    # 상태 확인
    @app.route('/health')
    def health():
        return {'status': 'ok', 'service': 'MiroFish Backend'}
    
    if should_log_startup:
        logger.info("MiroFish 백엔드 시작 완료")
    
    return app
