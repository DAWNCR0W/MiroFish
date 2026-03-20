"""
LLM 클라이언트 래퍼
OpenAI 형식 호출을 통일해서 사용한다.
"""

import json
import re
from typing import Optional, Dict, Any, List
from openai import OpenAI

from ..config import Config
from ..utils.logger import get_logger


logger = get_logger('mirofish.llm_client')

# LM Studio 같은 일부 OpenAI 호환 서비스는 json_object를 지원하지 않으므로,
# 일반 텍스트 모드로 되돌리고 프롬프트로 JSON 출력을 제약해야 한다.
JSON_ONLY_RESPONSE_INSTRUCTION = (
    "중요: 유효한 JSON만 반환하고, Markdown 코드 블록, 설명 또는 기타 추가 텍스트는 출력하지 마세요."
)


def _build_token_budgets(max_tokens: int) -> List[int]:
    """think/reasoning 모델을 위한 단계적 출력 예산을 구성한다"""
    budgets: List[int] = []
    for candidate in (
        max_tokens,
        max(max_tokens * 2, 8192),
        max(max_tokens * 4, 16384),
    ):
        if candidate not in budgets:
            budgets.append(candidate)
    return budgets


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


def create_chat_completion_with_fallback(
    client: OpenAI,
    *,
    request_logger=None,
    **kwargs
):
    """
    chat completion을 생성하고, provider가 json_object를 지원하지 않으면 자동으로 다운그레이드한다.
    """
    try:
        return client.chat.completions.create(**kwargs)
    except Exception as exc:
        if not _should_retry_without_response_format(kwargs.get("response_format"), exc):
            raise

        fallback_kwargs = dict(kwargs)
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
    except json.JSONDecodeError:
        json_match = re.search(r'\{[\s\S]*\}', cleaned)
        if json_match:
            return json.loads(json_match.group(0))
        raise ValueError(f"LLM 응답의 JSON 형식이 유효하지 않음: {cleaned}")


class LLMClient:
    """LLM 클라이언트"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None
    ):
        self.api_key = api_key or Config.LLM_API_KEY
        self.base_url = base_url or Config.LLM_BASE_URL
        self.model = model or Config.LLM_MODEL_NAME

        if not self.api_key:
            raise ValueError("LLM_API_KEY가 설정되지 않음")

        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=Config.LLM_REQUEST_TIMEOUT,
            max_retries=Config.LLM_MAX_RETRIES,
        )

    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        response_format: Optional[Dict] = None
    ) -> str:
        """
        채팅 요청을 보낸다.

        Args:
            messages: 메시지 목록
            temperature: 온도 파라미터
            max_tokens: 최대 token 수
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
                "temperature": temperature,
                "max_tokens": token_budget,
            }

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
            content = _clean_response_text(message.content)
            has_reasoning = bool(getattr(message, "reasoning_content", None))

            if finish_reason == "length" and index < len(token_budgets) - 1:
                next_budget = token_budgets[index + 1]
                logger.warning(
                    "LLM 텍스트 출력이 max_tokens=%s에서 잘려서 %s로 상향해 재시도",
                    token_budget,
                    next_budget,
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
                logger.warning(
                    "LLM 텍스트 출력이 비어 있음 (finish_reason=%s), %s로 상향해 재시도",
                    finish_reason,
                    next_budget,
                )
                continue

            raise last_error

        raise last_error or ValueError("LLM 응답이 비어 있음")

    def chat_json(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 4096
    ) -> Dict[str, Any]:
        """
        채팅 요청을 보내고 JSON을 반환한다.

        Args:
            messages: 메시지 목록
            temperature: 온도 파라미터
            max_tokens: 최대 token 수

        Returns:
            파싱된 JSON 객체
        """
        token_budgets = _build_token_budgets(max_tokens)
        last_error = None

        for index, token_budget in enumerate(token_budgets):
            response = create_chat_completion_with_fallback(
                self.client,
                request_logger=logger,
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=token_budget,
                response_format={"type": "json_object"}
            )
            choice = response.choices[0]
            message = choice.message
            finish_reason = choice.finish_reason
            content = message.content

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
                    logger.warning(
                        "LLM JSON 출력이 max_tokens=%s에서 잘려서 %s로 상향해 재시도",
                        token_budget,
                        next_budget,
                    )
                    continue

                if (
                    not _clean_response_text(content)
                    and has_reasoning
                    and index < len(token_budgets) - 1
                ):
                    next_budget = token_budgets[index + 1]
                    logger.warning(
                        "LLM이 생각 내용만 반환하고 최종 JSON을 출력하지 않아 %s로 상향해 재시도",
                        next_budget,
                    )
                    continue

                raise ValueError(
                    f"LLM 응답의 JSON 형식이 유효하지 않음 (finish_reason={finish_reason}, preview={preview})"
                ) from exc

        raise ValueError(str(last_error or "LLM 응답의 JSON 형식이 유효하지 않음"))
