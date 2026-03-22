"""
에이전트 프로필의 표시용 언어를 한국어로 정리하는 유틸리티.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from openai import OpenAI

from ..config import Config
from ..utils.llm_client import (
    create_chat_completion_with_fallback,
    extract_structured_response_text,
)
from ..utils.logger import get_logger


logger = get_logger("mirofish.profile_localization")


class ProfileLocalizationService:
    """프로필 표시 필드를 한국어 UI에 맞게 정리한다."""

    IDEOGRAPH_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
    TRANSLATABLE_FIELDS = ("bio", "persona", "profession", "country")
    TRANSLATION_BATCH_SIZE = 3
    TRANSLATION_INDEX_FIELD = "_translation_index"
    _translation_cache: Dict[str, Dict[str, Any]] = {}

    COUNTRY_MAP = {
        "china": "중국",
        "중국": "중국",
        "\u4e2d\u56fd": "중국",
        "\u4e2d\u534e\u4eba\u6c11\u5171\u548c\u56fd": "중국",
        "us": "미국",
        "usa": "미국",
        "united states": "미국",
        "\u7f8e\u56fd": "미국",
        "미국": "미국",
        "uk": "영국",
        "united kingdom": "영국",
        "\u82f1\u56fd": "영국",
        "영국": "영국",
        "japan": "일본",
        "\u65e5\u672c": "일본",
        "일본": "일본",
        "germany": "독일",
        "\u5fb7\u56fd": "독일",
        "독일": "독일",
        "france": "프랑스",
        "\u6cd5\u56fd": "프랑스",
        "프랑스": "프랑스",
        "canada": "캐나다",
        "\u52a0\u62ff\u5927": "캐나다",
        "캐나다": "캐나다",
        "australia": "호주",
        "\u6fb3\u5927\u5229\u4e9a": "호주",
        "호주": "호주",
        "brazil": "브라질",
        "\u5df4\u897f": "브라질",
        "브라질": "브라질",
        "india": "인도",
        "\u5370\u5ea6": "인도",
        "인도": "인도",
        "south korea": "대한민국",
        "korea": "대한민국",
        "\u97e9\u56fd": "대한민국",
        "\u5357\u97e9": "대한민국",
        "대한민국": "대한민국",
        "한국": "대한민국",
    }

    PROFESSION_MAP = {
        "student": "학생",
        "alumni": "동문",
        "professor": "교수",
        "person": "개인",
        "publicfigure": "공인",
        "expert": "전문가",
        "faculty": "교직원",
        "official": "공식 계정",
        "journalist": "기자",
        "activist": "활동가",
        "university": "대학",
        "governmentagency": "정부 기관",
        "organization": "기관",
        "ngo": "비영리 단체",
        "mediaoutlet": "미디어",
        "company": "기업",
        "institution": "기관",
        "group": "집단",
        "community": "커뮤니티",
        "media": "미디어",
    }

    TOPIC_MAP = {
        "general": "일반",
        "social issues": "사회 이슈",
        "technology": "기술",
        "politics": "정치",
        "economy": "경제",
        "culture and society": "문화와 사회",
        "education": "교육",
        "public policy": "공공 정책",
        "community": "커뮤니티",
        "official announcements": "공식 공지",
        "general news": "일반 뉴스",
        "current affairs": "시사",
        "public affairs": "공공 사안",
    }

    GENDER_MAP = {
        "male": "male",
        "female": "female",
        "other": "other",
        "남": "male",
        "남성": "male",
        "\u7537": "male",
        "여": "female",
        "여성": "female",
        "\u5973": "female",
        "기타": "other",
        "\u5176\u4ed6": "other",
        "other/gender": "other",
    }

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model_name: Optional[str] = None,
    ):
        self.api_key = api_key or Config.LLM_API_KEY
        self.base_url = base_url or Config.LLM_BASE_URL
        self.model_name = model_name or Config.LLM_MODEL_NAME
        self.client = None

        if self.api_key:
            self.client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=Config.LLM_REQUEST_TIMEOUT,
                max_retries=Config.LLM_MAX_RETRIES,
            )

    @classmethod
    def contains_han_text(cls, value: Any) -> bool:
        """한자 계열 문자가 포함되었는지 대략 판단한다."""
        if isinstance(value, list):
            return any(cls.contains_han_text(item) for item in value)
        if not isinstance(value, str):
            return False
        return bool(cls.IDEOGRAPH_RE.search(value))

    def adapt_and_localize_profiles(
        self,
        profiles: List[Dict[str, Any]],
        platform: str = "reddit",
    ) -> List[Dict[str, Any]]:
        """스토리지 형식을 UI 공통 형식으로 맞춘 뒤 한국어로 정리한다."""
        adapted = [self._adapt_profile_shape(profile, platform) for profile in profiles]
        return self.localize_profiles(adapted)

    def localize_profile(self, profile: Dict[str, Any]) -> Dict[str, Any]:
        """단일 프로필을 한국어 UI용으로 정리한다."""
        localized = self.localize_profiles([profile])
        return localized[0] if localized else profile

    def localize_profiles(self, profiles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """프로필 목록을 한국어 UI용으로 정리한다."""
        normalized = [self._normalize_profile_values(profile) for profile in profiles]
        if not normalized:
            return normalized

        pending_indices: List[int] = []
        pending_payloads: List[Dict[str, Any]] = []
        pending_cache_keys: List[str] = []

        for index, profile in enumerate(normalized):
            if not self._profile_needs_translation(profile):
                continue

            cache_key = self._make_cache_key(profile)
            cached = self._translation_cache.get(cache_key)
            if cached:
                normalized[index] = dict(cached)
                continue

            pending_indices.append(index)
            pending_payloads.append(self._build_translation_payload(profile))
            pending_cache_keys.append(cache_key)

        if not pending_payloads or not self.client:
            return normalized

        for start in range(0, len(pending_payloads), self.TRANSLATION_BATCH_SIZE):
            batch_payloads = pending_payloads[start:start + self.TRANSLATION_BATCH_SIZE]
            batch_indices = pending_indices[start:start + self.TRANSLATION_BATCH_SIZE]
            batch_cache_keys = pending_cache_keys[start:start + self.TRANSLATION_BATCH_SIZE]
            translated_batch = self._translate_batch(batch_payloads)
            if not translated_batch:
                continue

            for profile_index, cache_key, translated in zip(batch_indices, batch_cache_keys, translated_batch):
                merged = self._merge_translated_fields(normalized[profile_index], translated)
                normalized[profile_index] = merged
                self._translation_cache[cache_key] = dict(merged)

        return normalized

    def _adapt_profile_shape(self, profile: Dict[str, Any], platform: str) -> Dict[str, Any]:
        """플랫폼별 저장 포맷을 프런트 공통 포맷으로 맞춘다."""
        adapted = dict(profile)
        if platform != "twitter":
            return adapted

        if "bio" not in adapted or not adapted.get("bio"):
            adapted["bio"] = adapted.get("description", "")
        if "persona" not in adapted or not adapted.get("persona"):
            adapted["persona"] = adapted.get("user_char", "")
        if "username" not in adapted and adapted.get("name"):
            adapted["username"] = adapted.get("name")
        return adapted

    def _normalize_profile_values(self, profile: Dict[str, Any]) -> Dict[str, Any]:
        """사전식 매핑만으로 해결되는 값은 먼저 정규화한다."""
        normalized = dict(profile)

        gender = normalized.get("gender")
        if isinstance(gender, str):
            normalized["gender"] = self.GENDER_MAP.get(gender.strip().lower(), gender)

        country = normalized.get("country")
        if isinstance(country, str) and country.strip():
            normalized["country"] = self._normalize_country(country)

        profession = normalized.get("profession")
        if isinstance(profession, str) and profession.strip():
            normalized["profession"] = self._normalize_profession(profession)

        topics = normalized.get("interested_topics")
        if isinstance(topics, list):
            normalized["interested_topics"] = [
                self._normalize_topic(topic) if isinstance(topic, str) else topic
                for topic in topics
            ]

        return normalized

    def _normalize_country(self, country: str) -> str:
        key = country.strip().lower()
        return self.COUNTRY_MAP.get(key, country.strip())

    def _normalize_profession(self, profession: str) -> str:
        key = profession.strip().lower()
        return self.PROFESSION_MAP.get(key, profession.strip())

    def _normalize_topic(self, topic: str) -> str:
        key = topic.strip().lower()
        return self.TOPIC_MAP.get(key, topic.strip())

    def _profile_needs_translation(self, profile: Dict[str, Any]) -> bool:
        for field in self.TRANSLATABLE_FIELDS:
            if self.contains_han_text(profile.get(field)):
                return True
        return self.contains_han_text(profile.get("interested_topics", []))

    def _build_translation_payload(self, profile: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "bio": profile.get("bio", ""),
            "persona": profile.get("persona", ""),
            "profession": profile.get("profession", ""),
            "country": profile.get("country", ""),
            "interested_topics": profile.get("interested_topics", []),
        }

    def _coerce_translation_index(self, value: Any, payload_count: int) -> Optional[int]:
        if isinstance(value, bool):
            return None

        if isinstance(value, int):
            index = value
        elif isinstance(value, str) and value.strip().isdigit():
            index = int(value.strip())
        else:
            return None

        if 0 <= index < payload_count:
            return index
        return None

    def _strip_translation_metadata(self, translated: Dict[str, Any]) -> Dict[str, Any]:
        cleaned = dict(translated)
        cleaned.pop(self.TRANSLATION_INDEX_FIELD, None)
        return cleaned

    def _align_translated_profiles(
        self,
        translated_profiles: Any,
        payload_count: int,
    ) -> List[Dict[str, Any]]:
        if not isinstance(translated_profiles, list):
            raise ValueError("번역 응답에 profiles 배열이 없습니다")

        if (
            len(translated_profiles) == payload_count
            and all(
                isinstance(item, dict) and self.TRANSLATION_INDEX_FIELD not in item
                for item in translated_profiles
            )
        ):
            return [self._strip_translation_metadata(item) for item in translated_profiles]

        aligned: List[Optional[Dict[str, Any]]] = [None] * payload_count
        for item in translated_profiles:
            if not isinstance(item, dict):
                raise ValueError("번역된 profile 항목 형식이 올바르지 않습니다")

            raw_index = item.get(self.TRANSLATION_INDEX_FIELD)
            index = self._coerce_translation_index(raw_index, payload_count)
            if index is None:
                raise ValueError(
                    f"번역된 profile 항목의 {self.TRANSLATION_INDEX_FIELD} 값이 올바르지 않습니다: {raw_index!r}"
                )
            if aligned[index] is not None:
                raise ValueError(f"번역된 profile 항목의 {self.TRANSLATION_INDEX_FIELD} 값이 중복되었습니다: {index}")

            aligned[index] = self._strip_translation_metadata(item)

        missing_indices = [str(index) for index, item in enumerate(aligned) if item is None]
        if missing_indices:
            missing_preview = ", ".join(missing_indices[:5])
            raise ValueError(
                "번역된 profiles 배열 길이가 입력과 다릅니다: "
                f"input={payload_count}, output={len(translated_profiles)}, missing_indices=[{missing_preview}]"
            )

        return [item for item in aligned if item is not None]

    def _merge_translated_fields(
        self,
        profile: Dict[str, Any],
        translated: Dict[str, Any],
    ) -> Dict[str, Any]:
        merged = dict(profile)

        for field in self.TRANSLATABLE_FIELDS:
            value = translated.get(field)
            if isinstance(value, str) and value.strip():
                merged[field] = value.strip()

        topics = translated.get("interested_topics")
        if isinstance(topics, list):
            merged["interested_topics"] = [
                str(topic).strip()
                for topic in topics
                if str(topic).strip()
            ]

        return self._normalize_profile_values(merged)

    def _make_cache_key(self, profile: Dict[str, Any]) -> str:
        payload = self._build_translation_payload(profile)
        return json.dumps(payload, ensure_ascii=False, sort_keys=True)

    def _translate_batch(self, payloads: List[Dict[str, Any]]) -> Optional[List[Dict[str, Any]]]:
        """한자 계열 프로필 필드를 한국어 UI 문장으로 번역한다."""
        if not payloads or not self.client:
            return None

        request_payloads = []
        for index, payload in enumerate(payloads):
            request_payload = dict(payload)
            request_payload[self.TRANSLATION_INDEX_FIELD] = index
            request_payloads.append(request_payload)

        system_prompt = (
            "당신은 한국어 UI 현지화 편집자입니다. "
            "입력으로 들어온 소셜 프로필 JSON 배열을 자연스러운 한국어로 번역하세요. "
            "고유명사, 사용자명, MBTI, 영문 약어는 문맥상 필요한 경우만 번역하고 가능한 한 유지하세요. "
            f"각 객체의 {self.TRANSLATION_INDEX_FIELD} 정수값은 번역하지 말고 그대로 유지하세요. "
            "모든 입력 객체에 대해 정확히 하나의 출력 객체를 반환하세요. "
            "반드시 JSON만 반환하세요."
        )
        user_prompt = json.dumps({"profiles": request_payloads}, ensure_ascii=False)

        try:
            response = create_chat_completion_with_fallback(
                self.client,
                request_logger=logger,
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
            )

            content = extract_structured_response_text(response.choices[0].message)
            data = json.loads(content)
            translated_profiles = data.get("profiles")
            return self._align_translated_profiles(translated_profiles, len(payloads))
        except Exception as error:
            logger.warning("프로필 한국어 현지화 번역에 실패했습니다: %s", error)
            return None
