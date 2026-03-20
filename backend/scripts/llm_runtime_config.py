"""
실행 스크립트에서 공통으로 쓰는 LLM 설정 해석 도구.

목표:
1. `.env` 로딩 우선순위를 통일한다
2. `simulation_config.json`에 기록된 `llm_model` / `llm_base_url`을 기본 실행 소스로 사용한다
3. placeholder가 잘못 발동하지 않도록 boost 설정을 명시적으로 제어한다
4. provider 설정을 `ModelFactory`에 직접 전달해 전역 `OPENAI_*` 환경 변수를 오염시키지 않는다
"""

from __future__ import annotations

import os
from typing import Any, Dict

from dotenv import load_dotenv


_PLACEHOLDER_VALUES = {
    "",
    "your_api_key_here",
    "your_base_url_here",
    "your_model_name_here",
}


def load_runtime_env(project_root: str, backend_dir: str) -> None:
    """통일된 우선순위로 환경 변수를 로드한다. 프로젝트 루트가 우선이며 기존 값은 명시적으로 덮어쓴다."""
    env_file = os.path.join(project_root, ".env")
    if os.path.exists(env_file):
        load_dotenv(env_file, override=True)
        print(f"환경 설정을 불러왔습니다: {env_file}")
        return

    backend_env = os.path.join(backend_dir, ".env")
    if os.path.exists(backend_env):
        load_dotenv(backend_env, override=True)
        print(f"환경 설정을 불러왔습니다: {backend_env}")


def _clean_env_value(value: Any) -> str:
    text = str(value or "").strip()
    if text in _PLACEHOLDER_VALUES:
        return ""
    return text


def _is_truthy_env(name: str) -> bool:
    return _clean_env_value(os.environ.get(name, "")).lower() in {"1", "true", "yes", "on"}


def resolve_llm_runtime_config(config: Dict[str, Any], use_boost: bool = False) -> Dict[str, Any]:
    """
    스크립트 실행 시 실제로 사용할 LLM 설정을 해석한다.

    우선순위:
    1. `simulation_config.json`에 기록된 `llm_model` / `llm_base_url` (`prepare`와 `run`의 일치 보장)
    2. 환경 변수의 `LLM_MODEL_NAME` / `LLM_BASE_URL` (대체 경로)
    3. 명시적으로 활성화된 boost 설정

    API Key는 여전히 환경 변수에서만 읽어 설정 파일에 기록되지 않도록 한다.
    """
    default_api_key = _clean_env_value(os.environ.get("LLM_API_KEY"))
    default_base_url = _clean_env_value(os.environ.get("LLM_BASE_URL"))
    default_model = _clean_env_value(os.environ.get("LLM_MODEL_NAME"))

    config_base_url = _clean_env_value(config.get("llm_base_url"))
    config_model = _clean_env_value(config.get("llm_model"))

    allow_env_override = _is_truthy_env("LLM_RUNTIME_ALLOW_ENV_OVERRIDE")
    timeout = float(_clean_env_value(os.environ.get("LLM_REQUEST_TIMEOUT")) or "180")
    max_retries = int(_clean_env_value(os.environ.get("LLM_MAX_RETRIES")) or "3")

    if allow_env_override:
        resolved_base_url = default_base_url or config_base_url
        resolved_model = default_model or config_model or "gpt-4o-mini"
    else:
        resolved_base_url = config_base_url or default_base_url
        resolved_model = config_model or default_model or "gpt-4o-mini"

    if use_boost:
        boost_enabled = _is_truthy_env("LLM_BOOST_ENABLED")
        boost_api_key = _clean_env_value(os.environ.get("LLM_BOOST_API_KEY"))
        boost_base_url = _clean_env_value(os.environ.get("LLM_BOOST_BASE_URL"))
        boost_model = _clean_env_value(os.environ.get("LLM_BOOST_MODEL_NAME"))

        if boost_enabled:
            if not boost_api_key:
                raise ValueError("LLM_BOOST_ENABLED=true 이지만 LLM_BOOST_API_KEY가 설정되지 않았습니다")
            if not boost_base_url:
                raise ValueError("LLM_BOOST_ENABLED=true 이지만 LLM_BOOST_BASE_URL이 설정되지 않았습니다")

            return {
                "label": "[가속 LLM]",
                "api_key": boost_api_key,
                "base_url": boost_base_url,
                "model": boost_model or resolved_model,
                "timeout": timeout,
                "max_retries": max_retries,
                "source": "boost-env",
            }

    if not default_api_key:
        raise ValueError("API Key 설정이 없습니다. 프로젝트 루트의 `.env` 파일에 `LLM_API_KEY`를 설정하세요")

    return {
        "label": "[범용 LLM]",
        "api_key": default_api_key,
        "base_url": resolved_base_url,
        "model": resolved_model,
        "timeout": timeout,
        "max_retries": max_retries,
        "source": "config+env" if config_base_url or config_model else "env",
    }
