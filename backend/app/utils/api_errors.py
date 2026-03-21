"""
API 오류 응답의 디버그 필드를 정리하는 유틸리티
"""

from typing import Any


def strip_debug_error_fields(payload: Any, include_debug: bool) -> Any:
    """
    API 응답에서 내부 디버그 필드를 제거한다.

    traceback은 항상 제거하고, details는 명시적으로 허용된 경우에만 유지한다.
    """
    if isinstance(payload, list):
        return [strip_debug_error_fields(item, include_debug) for item in payload]

    if not isinstance(payload, dict):
        return payload

    cleaned = {}
    for key, value in payload.items():
        if key == "traceback":
            continue
        if key == "details" and not include_debug:
            continue
        cleaned[key] = strip_debug_error_fields(value, include_debug)

    return cleaned
