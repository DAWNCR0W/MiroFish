"""
LLM 클라이언트 래퍼
OpenAI 형식 호출을 통일해서 사용한다.
"""

import json
import re
import threading
import time
from typing import Optional, Dict, Any, List
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from openai import OpenAI

from ..config import Config
from ..utils.logger import get_logger


logger = get_logger('mirofish.llm_client')

# 일부 OpenAI 호환 서비스는 json_object를 그대로 받지 못한다.
# LM Studio는 json_schema로 우회하고, 그마저 안 되면 text 모드로 되돌린다.
JSON_ONLY_RESPONSE_INSTRUCTION = (
    "중요: 유효한 JSON만 반환하고, Markdown 코드 블록, 설명 또는 기타 추가 텍스트는 출력하지 마세요."
)


def _get_client_base_url(client: OpenAI) -> str:
    """OpenAI 클라이언트에서 base_url 문자열을 안전하게 꺼낸다"""
    base_url = getattr(client, "base_url", None) or getattr(client, "_base_url", None)
    return str(base_url or "")


def _normalize_parallel_value(value: Any) -> Optional[int]:
    """병렬 설정값을 안전한 양의 정수로 정규화한다."""
    try:
        resolved = int(value)
    except (TypeError, ValueError):
        return None

    return resolved if resolved > 0 else None


def _is_lm_studio_client(client: OpenAI) -> bool:
    """LM Studio OpenAI 호환 서버를 사용하는지 추정한다"""
    base_url = _get_client_base_url(client).lower()
    if not base_url:
        return False

    lm_studio_markers = (
        "lmstudio",
        "localhost:1234",
        "127.0.0.1:1234",
        "0.0.0.0:1234",
    )
    return any(marker in base_url for marker in lm_studio_markers)


def _build_json_schema_response_format(name: str = "structured_response") -> Dict[str, Any]:
    """json_object 호환용 느슨한 json_schema 요청을 구성한다"""
    return {
        "type": "json_schema",
        "json_schema": {
            "name": name,
            "schema": {
                "type": "object",
                "additionalProperties": True,
            },
        },
    }


def _normalize_response_format_for_provider(
    client: OpenAI,
    response_format: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """provider 특성에 맞게 response_format을 보정한다"""
    if not response_format:
        return response_format

    if (
        response_format.get("type") == "json_object"
        and _is_lm_studio_client(client)
    ):
        return _build_json_schema_response_format()

    return response_format


def _build_token_budgets(max_tokens: Optional[int]) -> List[Optional[int]]:
    """think/reasoning 모델을 위한 단계적 출력 예산을 구성한다"""
    if max_tokens is None:
        return [None]

    budgets: List[int] = []
    for candidate in (
        max_tokens,
        max(max_tokens * 2, 8192),
        max(max_tokens * 4, 16384),
    ):
        if candidate not in budgets:
            budgets.append(candidate)
    return budgets


def _log_retry_with_optional_budget(
    message_with_budget: str,
    message_without_budget: str,
    *,
    token_budget: Optional[int],
    next_budget: Optional[int],
    **kwargs: Any,
) -> None:
    """명시적 토큰 예산이 있을 때만 budget 정보를 포함해 재시도 로그를 남긴다"""
    if token_budget is not None and next_budget is not None:
        logger.warning(message_with_budget, *kwargs.values(), token_budget, next_budget)
        return

    logger.warning(message_without_budget, *kwargs.values())


def _should_retry_without_response_format(
    response_format: Optional[Dict[str, Any]],
    error: Exception
) -> bool:
    """response_format 비호환 때문에 다운그레이드 재시도가 필요한지 판단한다"""
    if not response_format or response_format.get("type") != "json_object":
        return False

    error_message = str(error).lower()
    unsupported_json_mode_markers = [
        "json_object",
        "response_format.type",
        "unsupported response_format",
        "invalid response_format",
        "json mode",
        "response_format",
    ]
    capability_markers = ["json_schema", "text", "unsupported", "must be", "not support", "invalid"]
    return (
        any(marker in error_message for marker in unsupported_json_mode_markers)
        and any(marker in error_message for marker in capability_markers)
    )


def _ensure_json_only_messages(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """메시지에 JSON 전용 제약을 보완해 text 모드로 돌아간 뒤 설명 텍스트가 나오지 않도록 한다"""
    normalized_messages = [dict(message) for message in messages]

    for message in normalized_messages:
        if message.get("role") != "system":
            continue

        content = message.get("content")
        if isinstance(content, str) and JSON_ONLY_RESPONSE_INSTRUCTION not in content:
            message["content"] = f"{content.rstrip()}\n\n{JSON_ONLY_RESPONSE_INSTRUCTION}"
        return normalized_messages

    normalized_messages.insert(0, {
        "role": "system",
        "content": JSON_ONLY_RESPONSE_INSTRUCTION,
    })
    return normalized_messages


def extract_structured_response_text(message: Any) -> str:
    """구조화 응답 본문을 content 우선, reasoning_content 차선으로 추출한다"""
    content = _clean_response_text(getattr(message, "content", None))
    if content:
        return content

    return _clean_response_text(getattr(message, "reasoning_content", None))


def create_chat_completion_with_fallback(
    client: OpenAI,
    *,
    request_logger=None,
    **kwargs
):
    """
    chat completion을 생성하고, provider 특성에 맞춰 구조화 응답 요청을 보정한다.
    """
    requested_response_format = kwargs.get("response_format")
    request_kwargs = dict(kwargs)
    normalized_response_format = _normalize_response_format_for_provider(
        client,
        requested_response_format,
    )
    if normalized_response_format:
        request_kwargs["response_format"] = normalized_response_format

    try:
        return client.chat.completions.create(**request_kwargs)
    except Exception as exc:
        if not _should_retry_without_response_format(requested_response_format, exc):
            raise

        fallback_kwargs = dict(request_kwargs)
        fallback_kwargs.pop("response_format", None)
        fallback_kwargs["messages"] = _ensure_json_only_messages(
            fallback_kwargs.get("messages", [])
        )

        active_logger = request_logger or logger
        active_logger.warning(
            "현재 LLM 서비스는 response_format=json_object를 지원하지 않아, 텍스트 모드로 자동 전환해 재시도한다"
        )
        return client.chat.completions.create(**fallback_kwargs)


def _clean_response_text(content: Optional[str]) -> str:
    """모델 텍스트 출력을 정리해 가능한 한 깨끗한 JSON 텍스트를 추출한다"""
    cleaned = (content or "").strip()
    cleaned = re.sub(r'<think>[\s\S]*?</think>', '', cleaned).strip()
    cleaned = re.sub(r'^```(?:json)?\s*\n?', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\n?```\s*$', '', cleaned)
    return cleaned.strip()


def _parse_json_from_content(content: Optional[str]) -> Dict[str, Any]:
    """모델 출력에서 JSON 객체를 파싱한다"""
    cleaned = _clean_response_text(content)
    if not cleaned:
        raise ValueError("LLM 응답이 비어 있음")

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        json_match = re.search(r'\{[\s\S]*\}', cleaned)
        if json_match:
            return json.loads(json_match.group(0))
        logger.debug("LLM JSON 파싱 실패, 원문 미리보기=%s", cleaned[:200])
        raise ValueError("LLM 응답의 JSON 형식이 유효하지 않음") from exc


class LLMClient:
    """LLM 클라이언트"""

    _parallel_cache: Dict[str, Dict[str, Any]] = {}
    _parallel_cache_lock = threading.Lock()

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        max_parallel_requests: Optional[int] = None,
    ):
        self.api_key = api_key or Config.LLM_API_KEY
        self.base_url = base_url or Config.LLM_BASE_URL
        self.model = model or Config.LLM_MODEL_NAME
        self.max_parallel_requests_override = _normalize_parallel_value(max_parallel_requests)

        if not self.api_key:
            raise ValueError("LLM_API_KEY가 설정되지 않음")

        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=Config.LLM_REQUEST_TIMEOUT,
            max_retries=Config.LLM_MAX_RETRIES,
        )

    def get_max_parallel_requests(
        self,
        fallback: Optional[int] = None,
        max_cap: Optional[int] = None,
    ) -> int:
        """설정, 서버 메타데이터, 안전한 fallback을 반영한 병렬 요청 수를 반환한다."""
        if self.max_parallel_requests_override is not None:
            cap = max(1, int(max_cap or Config.GRAPH_BUILD_MAX_PARALLEL_WORKERS))
            return min(self.max_parallel_requests_override, cap)

        return self.get_recommended_parallel_requests(
            api_key=self.api_key,
            base_url=self.base_url,
            model=self.model,
            fallback=fallback,
            max_cap=max_cap,
        )

    @classmethod
    def get_recommended_parallel_requests(
        cls,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        fallback: Optional[int] = None,
        max_cap: Optional[int] = None,
    ) -> int:
        workers, _ = cls.get_recommended_parallel_requests_with_source(
            api_key=api_key,
            base_url=base_url,
            model=model,
            fallback=fallback,
            max_cap=max_cap,
        )
        return workers

    @classmethod
    def get_recommended_parallel_requests_with_source(
        cls,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        fallback: Optional[int] = None,
        max_cap: Optional[int] = None,
    ) -> tuple[int, str]:
        resolved_api_key = api_key or Config.LLM_API_KEY
        resolved_base_url = (base_url or Config.LLM_BASE_URL or "").rstrip("/")
        resolved_model = model or Config.LLM_MODEL_NAME or ""
        fallback_workers = max(1, int(fallback or Config.GRAPH_BUILD_PARALLEL_WORKERS))
        worker_cap = max(1, int(max_cap or Config.GRAPH_BUILD_MAX_PARALLEL_WORKERS))

        if Config.LLM_MAX_PARALLEL_REQUESTS > 0:
            return min(Config.LLM_MAX_PARALLEL_REQUESTS, worker_cap), "env_override"

        cache_key = f"{resolved_base_url}::{resolved_model}"
        now = time.time()

        with cls._parallel_cache_lock:
            cached = cls._parallel_cache.get(cache_key)
            if cached and now - cached["ts"] <= Config.LLM_CAPABILITY_CACHE_TTL_SECONDS:
                return cached["workers"], cached["source"]

        detected = cls._detect_parallel_requests(
            api_key=resolved_api_key,
            base_url=resolved_base_url,
            model=resolved_model,
        )
        if detected:
            workers = max(1, min(int(detected), worker_cap))
            source = "server_capability"
        else:
            workers = min(fallback_workers, worker_cap)
            source = "config_fallback"

        with cls._parallel_cache_lock:
            cls._parallel_cache[cache_key] = {
                "workers": workers,
                "source": source,
                "ts": now,
            }

        return workers, source

    @classmethod
    def _detect_parallel_requests(
        cls,
        *,
        api_key: Optional[str],
        base_url: str,
        model: str,
    ) -> Optional[int]:
        endpoints = cls._candidate_model_metadata_endpoints(base_url)
        failed_endpoints = []

        for endpoint in endpoints:
            try:
                payload = cls._fetch_json(
                    endpoint,
                    api_key=api_key,
                    timeout=Config.LLM_CAPABILITY_REQUEST_TIMEOUT,
                )
            except Exception as exc:
                failed_endpoints.append(endpoint)
                logger.debug(
                    "LLM 서버 메타데이터 조회 실패: endpoint=%s, error=%s",
                    endpoint,
                    exc,
                )
                continue

            detected = cls._extract_parallel_from_payload(payload, model=model)
            if detected:
                logger.info("LLM 서버 메타데이터에서 병렬 설정을 감지함: endpoint=%s, parallel=%s", endpoint, detected)
                return detected

        if failed_endpoints and len(failed_endpoints) == len(endpoints):
            logger.warning(
                "LLM 서버 메타데이터 조회에 모두 실패해 fallback 병렬 설정을 사용합니다: base_url=%s",
                base_url,
            )

        return None

    @classmethod
    def _candidate_model_metadata_endpoints(cls, base_url: str) -> List[str]:
        if not base_url:
            return []

        stripped = base_url.rstrip("/")
        parsed = urlparse(stripped)
        path = parsed.path.rstrip("/")
        roots = []
        metadata_roots = []

        if path.endswith("/v1"):
            roots.append(stripped)
            metadata_roots.append(stripped[: -len("/v1")])
        else:
            roots.append(stripped)

        if path.endswith("/api/v1"):
            metadata_roots.append(stripped[: -len("/api/v1")])
        elif not path.endswith("/v1"):
            metadata_roots.append(stripped)

        candidates: List[str] = []
        for root in roots:
            normalized = root.rstrip("/")
            for suffix in ("/models",):
                candidate = f"{normalized}{suffix}"
                if candidate not in candidates:
                    candidates.append(candidate)
        for root in metadata_roots:
            normalized = root.rstrip("/")
            for suffix in ("/api/v1/models", "/api/v0/models"):
                candidate = f"{normalized}{suffix}"
                if candidate not in candidates:
                    candidates.append(candidate)
        return candidates

    @classmethod
    def _fetch_json(
        cls,
        url: str,
        *,
        api_key: Optional[str],
        timeout: float,
    ) -> Dict[str, Any]:
        headers = {"Accept": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        request = Request(url, headers=headers, method="GET")
        try:
            with urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            raise RuntimeError(f"HTTP {exc.code}") from exc
        except URLError as exc:
            raise RuntimeError(str(exc)) from exc

    @classmethod
    def _extract_parallel_from_payload(cls, payload: Dict[str, Any], *, model: str) -> Optional[int]:
        models = payload.get("models")
        if not isinstance(models, list):
            models = payload.get("data")
        if not isinstance(models, list):
            return None

        matched = cls._find_matching_model_entry(models, model=model)
        if matched:
            detected = cls._extract_parallel_from_model_entry(matched)
            if detected:
                return detected

        for entry in models:
            detected = cls._extract_parallel_from_model_entry(entry)
            if detected:
                return detected

        return None

    @classmethod
    def _find_matching_model_entry(cls, models: List[Dict[str, Any]], *, model: str) -> Optional[Dict[str, Any]]:
        if not model:
            return None

        for entry in models:
            entry_id = str(entry.get("id") or "")
            entry_key = str(entry.get("key") or "")
            if model in {entry_id, entry_key}:
                return entry

            loaded_instances = entry.get("loaded_instances")
            if isinstance(loaded_instances, list):
                for instance in loaded_instances:
                    instance_id = str(instance.get("id") or "")
                    if model == instance_id:
                        return entry
        return None

    @classmethod
    def _extract_parallel_from_model_entry(cls, entry: Dict[str, Any]) -> Optional[int]:
        loaded_instances = entry.get("loaded_instances")
        if isinstance(loaded_instances, list):
            for instance in loaded_instances:
                detected = cls._extract_parallel_from_mapping(instance.get("config"))
                if detected:
                    return detected
                detected = cls._extract_parallel_from_mapping(instance)
                if detected:
                    return detected

        return cls._extract_parallel_from_mapping(entry)

    @staticmethod
    def _extract_parallel_from_mapping(value: Any) -> Optional[int]:
        if not isinstance(value, dict):
            return None

        for key in (
            "parallel",
            "n_parallel",
            "max_parallel",
            "max_concurrent_predictions",
            "maxConcurrentPredictions",
            "num_parallel",
        ):
            candidate = value.get(key)
            try:
                candidate_int = int(candidate)
            except (TypeError, ValueError):
                continue
            if candidate_int > 0:
                return candidate_int

        return None

    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        response_format: Optional[Dict] = None
    ) -> str:
        """
        채팅 요청을 보낸다.

        Args:
            messages: 메시지 목록
            temperature: 온도 파라미터(None이면 provider 기본값 사용)
            max_tokens: 최대 token 수(None이면 provider 기본값 사용)
            response_format: 응답 형식 (예: JSON 모드)

        Returns:
            모델 응답 텍스트
        """
        token_budgets = _build_token_budgets(max_tokens)
        last_error = None

        for index, token_budget in enumerate(token_budgets):
            kwargs = {
                "model": self.model,
                "messages": messages,
            }

            if temperature is not None:
                kwargs["temperature"] = temperature
            if token_budget is not None:
                kwargs["max_tokens"] = token_budget
            if response_format:
                kwargs["response_format"] = response_format

            response = create_chat_completion_with_fallback(
                self.client,
                request_logger=logger,
                **kwargs
            )
            choice = response.choices[0]
            message = choice.message
            finish_reason = choice.finish_reason
            content = (
                extract_structured_response_text(message)
                if response_format else _clean_response_text(message.content)
            )
            has_reasoning = bool(getattr(message, "reasoning_content", None))

            if finish_reason == "length" and index < len(token_budgets) - 1:
                next_budget = token_budgets[index + 1]
                _log_retry_with_optional_budget(
                    "LLM 텍스트 출력이 잘려 max_tokens=%s에서 %s로 상향해 재시도",
                    "LLM 텍스트 출력이 잘려 재시도",
                    token_budget=token_budget,
                    next_budget=next_budget,
                )
                continue

            if content:
                return content

            last_error = ValueError(
                f"LLM 응답이 비어 있음 (finish_reason={finish_reason}, has_reasoning={has_reasoning})"
            )

            if (
                (has_reasoning or finish_reason == "length")
                and index < len(token_budgets) - 1
            ):
                next_budget = token_budgets[index + 1]
                _log_retry_with_optional_budget(
                    "LLM 텍스트 출력이 비어 있음 (finish_reason=%s). max_tokens=%s에서 %s로 상향해 재시도",
                    "LLM 텍스트 출력이 비어 있음 (finish_reason=%s). 재시도",
                    token_budget=token_budget,
                    next_budget=next_budget,
                    finish_reason=finish_reason,
                )
                continue

            raise last_error

        raise last_error or ValueError("LLM 응답이 비어 있음")

    def chat_json(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        채팅 요청을 보내고 JSON을 반환한다.

        Args:
            messages: 메시지 목록
            temperature: 온도 파라미터(None이면 provider 기본값 사용)
            max_tokens: 최대 token 수(None이면 provider 기본값 사용)

        Returns:
            파싱된 JSON 객체
        """
        token_budgets = _build_token_budgets(max_tokens)
        last_error = None

        for index, token_budget in enumerate(token_budgets):
            request_kwargs = {
                "model": self.model,
                "messages": messages,
                "response_format": {"type": "json_object"},
            }
            if temperature is not None:
                request_kwargs["temperature"] = temperature
            if token_budget is not None:
                request_kwargs["max_tokens"] = token_budget

            response = create_chat_completion_with_fallback(
                self.client,
                request_logger=logger,
                **request_kwargs
            )
            choice = response.choices[0]
            message = choice.message
            finish_reason = choice.finish_reason
            content = extract_structured_response_text(message)

            try:
                return _parse_json_from_content(content)
            except Exception as exc:
                last_error = exc
                has_reasoning = bool(getattr(message, "reasoning_content", None))
                preview = _clean_response_text(content)[:200]

                if (
                    finish_reason == "length"
                    and index < len(token_budgets) - 1
                ):
                    next_budget = token_budgets[index + 1]
                    _log_retry_with_optional_budget(
                        "LLM JSON 출력이 잘려 max_tokens=%s에서 %s로 상향해 재시도",
                        "LLM JSON 출력이 잘려 재시도",
                        token_budget=token_budget,
                        next_budget=next_budget,
                    )
                    continue

                if (
                    not _clean_response_text(content)
                    and has_reasoning
                    and index < len(token_budgets) - 1
                ):
                    next_budget = token_budgets[index + 1]
                    _log_retry_with_optional_budget(
                        "LLM이 생각 내용만 반환하고 최종 JSON을 출력하지 않아 max_tokens=%s에서 %s로 상향해 재시도",
                        "LLM이 생각 내용만 반환하고 최종 JSON을 출력하지 않아 재시도",
                        token_budget=token_budget,
                        next_budget=next_budget,
                    )
                    continue

                logger.debug(
                    "LLM JSON 응답 파싱 실패: finish_reason=%s, preview=%s",
                    finish_reason,
                    preview,
                )
                raise ValueError(
                    f"LLM 응답의 JSON 형식이 유효하지 않음 (finish_reason={finish_reason})"
                ) from exc

        raise ValueError(str(last_error or "LLM 응답의 JSON 형식이 유효하지 않음"))
