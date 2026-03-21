"""
시뮬레이션 스케줄 정규화 유틸리티
"""

from __future__ import annotations

import json
import re
from typing import Any, Iterable, List, Optional


_HOUR_RANGE_PATTERN = re.compile(
    r"^\s*(?P<start>\d{1,2})(?::\d{2})?\s*-\s*(?P<end>\d{1,2})(?::\d{2})?\s*$"
)


def _finalize_hours(hours: Iterable[Any], fallback: List[int]) -> List[int]:
    normalized: List[int] = []
    seen = set()

    for value in hours:
        try:
            hour = int(value)
        except (TypeError, ValueError):
            continue

        if hour < 0 or hour > 23 or hour in seen:
            continue

        seen.add(hour)
        normalized.append(hour)

    return normalized or list(fallback)


def normalize_active_hours(raw_hours: Any, default: Optional[List[int]] = None) -> List[int]:
    """
    LLM이 문자열/JSON/리스트 등 들쭉날쭉하게 반환한 active_hours를 0-23 정수 목록으로 정규화한다.
    """
    fallback = list(default) if default is not None else list(range(8, 23))

    if raw_hours is None:
        return fallback

    if isinstance(raw_hours, (list, tuple, set)):
        return _finalize_hours(raw_hours, fallback)

    if isinstance(raw_hours, int):
        return _finalize_hours([raw_hours], fallback)

    if isinstance(raw_hours, str):
        stripped = raw_hours.strip()
        if not stripped:
            return fallback

        if stripped[0] in "[{":
            try:
                decoded = json.loads(stripped)
            except json.JSONDecodeError:
                decoded = None
            if decoded is not None:
                return normalize_active_hours(decoded, default=fallback)

        range_match = _HOUR_RANGE_PATTERN.match(stripped)
        if range_match:
            start = int(range_match.group("start"))
            end = int(range_match.group("end"))
            if 0 <= start <= 23 and 0 <= end <= 23:
                if start <= end:
                    return list(range(start, end + 1))
                return list(range(start, 24)) + list(range(0, end + 1))

        if "," in stripped:
            return _finalize_hours((part.strip() for part in stripped.split(",")), fallback)

        tokens = re.findall(r"\d{1,2}", stripped)
        if tokens:
            return _finalize_hours(tokens, fallback)

    return fallback
