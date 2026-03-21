"""
OASIS Agent Profile 생성기
로컬 그래프의 엔티티를 OASIS 시뮬레이션 플랫폼이 요구하는 Agent Profile 형식으로 변환합니다.

개선 사항:
1. 로컬 그래프 검색 기능을 다시 호출해 노드 정보를 풍부하게 만듭니다.
2. 프롬프트를 최적화해 매우 상세한 인물 설정을 생성합니다.
3. 개인 엔티티와 추상적 집단 엔티티를 구분합니다.
"""

import json
import random
import time
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime

from openai import OpenAI

from ..config import Config
from ..utils.logger import get_logger
from ..utils.llm_client import (
    create_chat_completion_with_fallback,
    extract_structured_response_text,
)
from .graph_entity_reader import EntityNode
from .graph_tools import GraphToolsService
from .profile_localization import ProfileLocalizationService

logger = get_logger('mirofish.oasis_profile')


@dataclass
class OasisAgentProfile:
    """OASIS Agent Profile 데이터 구조"""
    # 공통 필드
    user_id: int
    user_name: str
    name: str
    bio: str
    persona: str

    # 선택 필드 - Reddit 스타일
    karma: int = 1000

    # 선택 필드 - Twitter 스타일
    friend_count: int = 100
    follower_count: int = 150
    statuses_count: int = 500

    # 추가 인물 설정 정보
    age: Optional[int] = None
    gender: Optional[str] = None
    mbti: Optional[str] = None
    country: Optional[str] = None
    profession: Optional[str] = None
    interested_topics: List[str] = field(default_factory=list)

    # 원본 엔티티 정보
    source_entity_uuid: Optional[str] = None
    source_entity_type: Optional[str] = None

    created_at: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d"))

    def to_reddit_format(self) -> Dict[str, Any]:
        """Reddit 플랫폼 형식으로 변환"""
        profile = {
            "user_id": self.user_id,
            "username": self.user_name,  # OASIS 라이브러리 요구사항: 필드명은 username(언더스코어 없음)
            "name": self.name,
            "bio": self.bio,
            "persona": self.persona,
            "karma": self.karma,
            "created_at": self.created_at,
        }

        # 추가 인물 정보가 있으면 포함
        if self.age:
            profile["age"] = self.age
        if self.gender:
            profile["gender"] = self.gender
        if self.mbti:
            profile["mbti"] = self.mbti
        if self.country:
            profile["country"] = self.country
        if self.profession:
            profile["profession"] = self.profession
        if self.interested_topics:
            profile["interested_topics"] = self.interested_topics

        return profile

    def to_twitter_format(self) -> Dict[str, Any]:
        """Twitter 플랫폼 형식으로 변환"""
        profile = {
            "user_id": self.user_id,
            "username": self.user_name,  # OASIS 라이브러리 요구사항: 필드명은 username(언더스코어 없음)
            "name": self.name,
            "bio": self.bio,
            "persona": self.persona,
            "friend_count": self.friend_count,
            "follower_count": self.follower_count,
            "statuses_count": self.statuses_count,
            "created_at": self.created_at,
        }

        # 추가 인물 정보 포함
        if self.age:
            profile["age"] = self.age
        if self.gender:
            profile["gender"] = self.gender
        if self.mbti:
            profile["mbti"] = self.mbti
        if self.country:
            profile["country"] = self.country
        if self.profession:
            profile["profession"] = self.profession
        if self.interested_topics:
            profile["interested_topics"] = self.interested_topics

        return profile

    def to_dict(self) -> Dict[str, Any]:
        """완전한 딕셔너리 형식으로 변환"""
        return {
            "user_id": self.user_id,
            "user_name": self.user_name,
            "name": self.name,
            "bio": self.bio,
            "persona": self.persona,
            "karma": self.karma,
            "friend_count": self.friend_count,
            "follower_count": self.follower_count,
            "statuses_count": self.statuses_count,
            "age": self.age,
            "gender": self.gender,
            "mbti": self.mbti,
            "country": self.country,
            "profession": self.profession,
            "interested_topics": self.interested_topics,
            "source_entity_uuid": self.source_entity_uuid,
            "source_entity_type": self.source_entity_type,
            "created_at": self.created_at,
        }


class OasisProfileGenerator:
    """
    OASIS Profile 생성기

    그래프의 엔티티를 OASIS 시뮬레이션에 필요한 Agent Profile로 변환합니다.

    최적화 특성:
    1. 그래프 검색 기능을 호출해 더 풍부한 컨텍스트를 가져옵니다.
    2. 기본 정보, 경력, 성격 특성, 소셜 미디어 행동 등을 포함한 매우 상세한 인물 설정을 생성합니다.
    3. 개인 엔티티와 추상적 집단 엔티티를 구분합니다.
    """

    # MBTI 유형 목록
    MBTI_TYPES = [
        "INTJ", "INTP", "ENTJ", "ENTP",
        "INFJ", "INFP", "ENFJ", "ENFP",
        "ISTJ", "ISFJ", "ESTJ", "ESFJ",
        "ISTP", "ISFP", "ESTP", "ESFP"
    ]

    # 일반적인 국가 목록
    COUNTRIES = [
        "중국", "미국", "영국", "일본", "독일", "프랑스",
        "캐나다", "호주", "브라질", "인도", "대한민국"
    ]

    # 개인 유형 엔티티(구체적 인물 설정 필요)
    INDIVIDUAL_ENTITY_TYPES = [
        "student", "alumni", "professor", "person", "publicfigure",
        "expert", "faculty", "official", "journalist", "activist"
    ]

    # 집단/기관 유형 엔티티(집단 대표 인물 설정 필요)
    GROUP_ENTITY_TYPES = [
        "university", "governmentagency", "organization", "ngo",
        "mediaoutlet", "company", "institution", "group", "community"
    ]

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model_name: Optional[str] = None,
        graph_id: Optional[str] = None
    ):
        self.api_key = api_key or Config.LLM_API_KEY
        self.base_url = base_url or Config.LLM_BASE_URL
        self.model_name = model_name or Config.LLM_MODEL_NAME

        if not self.api_key:
            raise ValueError("LLM_API_KEY가 설정되지 않았습니다")

        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=Config.LLM_REQUEST_TIMEOUT,
            max_retries=Config.LLM_MAX_RETRIES,
        )

        self.graph_id = graph_id
        self.graph_tools = GraphToolsService()
        self.profile_localizer = ProfileLocalizationService(
            api_key=self.api_key,
            base_url=self.base_url,
            model_name=self.model_name,
        )

    def generate_profile_from_entity(
        self,
        entity: EntityNode,
        user_id: int,
        use_llm: bool = True
    ) -> OasisAgentProfile:
        """
        그래프 엔티티로부터 OASIS Agent Profile을 생성합니다.

        Args:
            entity: 그래프 엔티티 노드
            user_id: 사용자 ID(OASIS용)
            use_llm: LLM으로 상세 인물 설정을 생성할지 여부

        Returns:
            OasisAgentProfile
        """
        entity_type = entity.get_entity_type() or "Entity"

        # 기본 정보
        name = entity.name
        user_name = self._generate_username(name)

        # 컨텍스트 정보 구성
        context = self._build_entity_context(entity)

        if use_llm:
            # LLM으로 상세 인물 설정 생성
            profile_data = self._generate_profile_with_llm(
                entity_name=name,
                entity_type=entity_type,
                entity_summary=entity.summary,
                entity_attributes=entity.attributes,
                context=context
            )
        else:
            # 규칙 기반으로 기본 인물 설정 생성
            profile_data = self._generate_profile_rule_based(
                entity_name=name,
                entity_type=entity_type,
                entity_summary=entity.summary,
                entity_attributes=entity.attributes
            )

        profile_data = self.profile_localizer.localize_profile(profile_data)

        return OasisAgentProfile(
            user_id=user_id,
            user_name=user_name,
            name=name,
            bio=profile_data.get("bio", f"{entity_type}: {name}"),
            persona=profile_data.get("persona", entity.summary or f"A {entity_type} named {name}."),
            karma=profile_data.get("karma", random.randint(500, 5000)),
            friend_count=profile_data.get("friend_count", random.randint(50, 500)),
            follower_count=profile_data.get("follower_count", random.randint(100, 1000)),
            statuses_count=profile_data.get("statuses_count", random.randint(100, 2000)),
            age=profile_data.get("age"),
            gender=profile_data.get("gender"),
            mbti=profile_data.get("mbti"),
            country=profile_data.get("country"),
            profession=profile_data.get("profession"),
            interested_topics=profile_data.get("interested_topics", []),
            source_entity_uuid=entity.uuid,
            source_entity_type=entity_type,
        )

    def _generate_username(self, name: str) -> str:
        """사용자 이름 생성"""
        # 특수문자를 제거하고 소문자로 변환
        username = name.lower().replace(" ", "_")
        username = ''.join(c for c in username if c.isalnum() or c == '_')

        # 중복을 피하기 위해 랜덤 접미사 추가
        suffix = random.randint(100, 999)
        return f"{username}_{suffix}"

    def _search_graph_for_entity(self, entity: EntityNode) -> Dict[str, Any]:
        """
        로컬 그래프 검색 기능을 사용해 엔티티 관련 풍부한 정보를 가져옵니다.

        Args:
            entity: 엔티티 노드 객체

        Returns:
            facts, node_summaries, context를 포함한 딕셔너리
        """
        import concurrent.futures

        entity_name = entity.name

        results = {
            "facts": [],
            "node_summaries": [],
            "context": ""
        }

        # 검색하려면 graph_id가 반드시 필요합니다.
        if not self.graph_id:
            logger.debug("그래프 검색을 건너뜁니다: graph_id가 설정되지 않았습니다")
            return results

        comprehensive_query = f"{entity_name}에 대한 모든 정보, 활동, 사건, 관계 및 배경"

        def search_edges():
            return self.graph_tools.search_graph(
                graph_id=self.graph_id,
                query=comprehensive_query,
                limit=30,
                scope="edges",
            )

        def search_nodes():
            return self.graph_tools.search_graph(
                graph_id=self.graph_id,
                query=comprehensive_query,
                limit=20,
                scope="nodes",
            )

        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                edge_future = executor.submit(search_edges)
                node_future = executor.submit(search_nodes)

                edge_result = edge_future.result(timeout=30)
                node_result = node_future.result(timeout=30)

            all_facts = set()
            if edge_result and edge_result.edges:
                for edge in edge_result.edges:
                    fact = edge.get("fact", "")
                    if fact:
                        all_facts.add(fact)
            results["facts"] = list(all_facts)

            all_summaries = set()
            if node_result and node_result.nodes:
                for node in node_result.nodes:
                    summary = node.get("summary", "")
                    node_name = node.get("name", "")
                    if summary:
                        all_summaries.add(summary)
                    if node_name and node_name != entity_name:
                        all_summaries.add(f"관련 엔티티: {node_name}")
            results["node_summaries"] = list(all_summaries)

            context_parts = []
            if results["facts"]:
                context_parts.append("사실 정보:\n" + "\n".join(f"- {f}" for f in results["facts"][:20]))
            if results["node_summaries"]:
                context_parts.append("관련 엔티티:\n" + "\n".join(f"- {s}" for s in results["node_summaries"][:10]))
            results["context"] = "\n\n".join(context_parts)

            logger.info(
                "그래프 검색 완료: %s, 사실 %s개, 관련 노드 %s개 획득",
                entity_name,
                len(results["facts"]),
                len(results["node_summaries"]),
            )

        except concurrent.futures.TimeoutError:
            logger.warning("그래프 검색 시간 초과 (%s)", entity_name)
        except Exception as e:
            logger.warning("그래프 검색 실패 (%s): %s", entity_name, e)

        return results

    def _build_entity_context(self, entity: EntityNode) -> str:
        """
        엔티티의 전체 컨텍스트 정보를 구성합니다.

        포함 내용:
        1. 엔티티 자체의 엣지 정보(사실)
        2. 연결된 노드의 상세 정보
        3. 그래프 검색으로 얻은 풍부한 정보
        """
        context_parts = []

        # 1. 엔티티 속성 정보 추가
        if entity.attributes:
            attrs = []
            for key, value in entity.attributes.items():
                if value and str(value).strip():
                    attrs.append(f"- {key}: {value}")
            if attrs:
                context_parts.append("### 엔티티 속성\n" + "\n".join(attrs))

        # 2. 관련 엣지 정보(사실/관계) 추가
        existing_facts = set()
        if entity.related_edges:
            relationships = []
            for edge in entity.related_edges:  # 개수 제한 없음
                fact = edge.get("fact", "")
                edge_name = edge.get("edge_name", "")
                direction = edge.get("direction", "")

                if fact:
                    relationships.append(f"- {fact}")
                    existing_facts.add(fact)
                elif edge_name:
                    if direction == "outgoing":
                        relationships.append(f"- {entity.name} --[{edge_name}]--> (관련 엔티티)")
                    else:
                        relationships.append(f"- (관련 엔티티) --[{edge_name}]--> {entity.name}")

            if relationships:
                context_parts.append("### 관련 사실과 관계\n" + "\n".join(relationships))

        # 3. 연결 노드의 상세 정보 추가
        if entity.related_nodes:
            related_info = []
            for node in entity.related_nodes:  # 개수 제한 없음
                node_name = node.get("name", "")
                node_labels = node.get("labels", [])
                node_summary = node.get("summary", "")

                # 기본 라벨 제외
                custom_labels = [l for l in node_labels if l not in ["Entity", "Node"]]
                label_str = f" ({', '.join(custom_labels)})" if custom_labels else ""

                if node_summary:
                    related_info.append(f"- **{node_name}**{label_str}: {node_summary}")
                else:
                    related_info.append(f"- **{node_name}**{label_str}")

            if related_info:
                context_parts.append("### 연결된 엔티티 정보\n" + "\n".join(related_info))

        # 4. 그래프 검색으로 더 풍부한 정보 획득
        graph_results = self._search_graph_for_entity(entity)

        if graph_results.get("facts"):
            # 중복 제거: 이미 존재하는 사실 제외
            new_facts = [f for f in graph_results["facts"] if f not in existing_facts]
            if new_facts:
                context_parts.append("### 그래프 검색으로 얻은 사실 정보\n" + "\n".join(f"- {f}" for f in new_facts[:15]))

        if graph_results.get("node_summaries"):
            context_parts.append("### 그래프 검색으로 얻은 관련 노드\n" + "\n".join(f"- {s}" for s in graph_results["node_summaries"][:10]))

        return "\n\n".join(context_parts)

    def _is_individual_entity(self, entity_type: str) -> bool:
        """개인 유형 엔티티인지 판단합니다."""
        return entity_type.lower() in self.INDIVIDUAL_ENTITY_TYPES

    def _is_group_entity(self, entity_type: str) -> bool:
        """집단/기관 유형 엔티티인지 판단합니다."""
        return entity_type.lower() in self.GROUP_ENTITY_TYPES

    def _generate_profile_with_llm(
        self,
        entity_name: str,
        entity_type: str,
        entity_summary: str,
        entity_attributes: Dict[str, Any],
        context: str
    ) -> Dict[str, Any]:
        """
        LLM으로 매우 상세한 인물 설정을 생성합니다.

        엔티티 유형에 따라 구분:
        - 개인 엔티티: 구체적인 인물 설정 생성
        - 집단/기관 엔티티: 대표 계정 설정 생성
        """

        is_individual = self._is_individual_entity(entity_type)

        if is_individual:
            prompt = self._build_individual_persona_prompt(
                entity_name, entity_type, entity_summary, entity_attributes, context
            )
        else:
            prompt = self._build_group_persona_prompt(
                entity_name, entity_type, entity_summary, entity_attributes, context
            )

        # 성공하거나 최대 재시도 횟수에 도달할 때까지 여러 번 시도
        max_attempts = 3
        last_error = None

        for attempt in range(max_attempts):
            try:
                response = create_chat_completion_with_fallback(
                    self.client,
                    request_logger=logger,
                    model=self.model_name,
                    messages=[
                        {"role": "system", "content": self._get_system_prompt(is_individual)},
                        {"role": "user", "content": prompt}
                    ],
                    response_format={"type": "json_object"},
                )

                message = response.choices[0].message
                content = extract_structured_response_text(message)
                has_reasoning = bool(getattr(message, "reasoning_content", None))
                if not content.strip() and has_reasoning:
                    last_error = ValueError("LLM이 사고 내용만 반환하고 최종 JSON을 출력하지 않았습니다")
                    logger.warning(
                        "LLM이 사고 내용만 반환함 (attempt %s, provider 기본 생성 설정 사용)",
                        attempt + 1,
                    )
                    continue

                # 잘렸는지 확인(finish_reason이 'stop'이 아님)
                finish_reason = response.choices[0].finish_reason
                if finish_reason == 'length':
                    logger.warning(
                        "LLM 출력이 잘림 (attempt %s, provider 기본 생성 설정 사용), 복구를 시도합니다...",
                        attempt + 1,
                    )
                    content = self._fix_truncated_json(content)

                # JSON 파싱 시도
                try:
                    result = json.loads(content)

                    # 필수 필드 검증
                    if "bio" not in result or not result["bio"]:
                        result["bio"] = entity_summary[:200] if entity_summary else f"{entity_type}: {entity_name}"
                    if "persona" not in result or not result["persona"]:
                        result["persona"] = entity_summary or f"{entity_name}는 {entity_type}입니다."

                    return result

                except json.JSONDecodeError as je:
                    logger.warning(f"JSON 파싱 실패 (attempt {attempt+1}): {str(je)[:80]}")

                    # JSON 복구 시도
                    result = self._try_fix_json(content, entity_name, entity_type, entity_summary)
                    if result.get("_fixed"):
                        del result["_fixed"]
                        return result

                    last_error = je

            except Exception as e:
                logger.warning(f"LLM 호출 실패 (attempt {attempt+1}): {str(e)[:80]}")
                last_error = e
                import time
                time.sleep(1 * (attempt + 1))  # 지수형 백오프

        logger.warning(f"LLM 인물 설정 생성 실패({max_attempts}회 시도): {last_error}, 규칙 기반 생성을 사용합니다")
        return self._generate_profile_rule_based(
            entity_name, entity_type, entity_summary, entity_attributes
        )

    def _fix_truncated_json(self, content: str) -> str:
        """잘린 JSON을 복구합니다(출력이 max_tokens 제한으로 잘린 경우)."""
        import re

        # JSON이 잘렸다면 닫히도록 시도합니다
        content = content.strip()

        # 닫히지 않은 괄호 계산
        open_braces = content.count('{') - content.count('}')
        open_brackets = content.count('[') - content.count(']')

        # 닫히지 않은 문자열이 있는지 확인합니다
        # 간단한 검사: 마지막 따옴표 뒤에 쉼표나 닫는 괄호가 없으면 문자열이 잘렸을 수 있습니다
        if content and content[-1] not in '",}]':
            # 문자열 닫기를 시도합니다
            content += '"'

        # 괄호 닫기
        content += ']' * open_brackets
        content += '}' * open_braces

        return content

    def _try_fix_json(self, content: str, entity_name: str, entity_type: str, entity_summary: str = "") -> Dict[str, Any]:
        """손상된 JSON 복구를 시도합니다."""
        import re

        # 1. 먼저 잘린 경우 복구를 시도합니다
        content = self._fix_truncated_json(content)

        # 2. JSON 부분 추출을 시도합니다
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            json_str = json_match.group()

            # 3. 문자열 내부 줄바꿈 문제를 처리합니다
            # 모든 문자열 값을 찾아 내부 줄바꿈을 바꿉니다
            def fix_string_newlines(match):
                s = match.group(0)
                # 문자열 내부의 실제 줄바꿈을 공백으로 교체합니다
                s = s.replace('\n', ' ').replace('\r', ' ')
                # 과도한 공백을 정리합니다
                s = re.sub(r'\s+', ' ', s)
                return s

            # JSON 문자열 값과 매칭합니다
            json_str = re.sub(r'"[^"\\]*(?:\\.[^"\\]*)*"', fix_string_newlines, json_str)

            # 4. 파싱을 시도합니다
            try:
                result = json.loads(json_str)
                result["_fixed"] = True
                return result
            except json.JSONDecodeError as e:
                # 5. 그래도 실패하면 더 적극적으로 복구를 시도합니다
                try:
                    # 모든 제어 문자를 제거합니다
                    json_str = re.sub(r'[\x00-\x1f\x7f-\x9f]', ' ', json_str)
                    # 연속된 모든 공백을 정리합니다
                    json_str = re.sub(r'\s+', ' ', json_str)
                    result = json.loads(json_str)
                    result["_fixed"] = True
                    return result
                except:
                    pass

        # 6. 내용에서 일부 정보를 추출해 봅니다
        bio_match = re.search(r'"bio"\s*:\s*"([^"]*)"', content)
        persona_match = re.search(r'"persona"\s*:\s*"([^"]*)', content)  # 잘렸을 수 있음

        bio = bio_match.group(1) if bio_match else (entity_summary[:200] if entity_summary else f"{entity_type}: {entity_name}")
        persona = persona_match.group(1) if persona_match else (entity_summary or f"{entity_name}은(는) {entity_type}입니다.")

        # 의미 있는 내용을 추출했다면 복구 완료로 표시합니다
        if bio_match or persona_match:
            logger.info("손상된 JSON에서 일부 정보를 추출했습니다")
            return {
                "bio": bio,
                "persona": persona,
                "_fixed": True
            }

        # 7. 완전히 실패하면 기본 구조를 반환합니다
        logger.warning("JSON 복구에 실패해 기본 구조를 반환합니다")
        return {
            "bio": entity_summary[:200] if entity_summary else f"{entity_type}: {entity_name}",
            "persona": entity_summary or f"{entity_name}은(는) {entity_type}입니다."
        }

    def _get_system_prompt(self, is_individual: bool) -> str:
        """시스템 프롬프트를 가져옵니다."""
        base_prompt = (
            "당신은 소셜 미디어 사용자 프로필 생성 전문가입니다. "
            "여론 시뮬레이션에 사용할 상세하고 사실적인 인물 설정을 생성해 가능한 한 현실 상황을 그대로 재현하세요. "
            "반드시 유효한 JSON 형식으로 반환해야 하며, 모든 문자열 값에는 이스케이프되지 않은 줄바꿈이 포함되면 안 됩니다. "
            "모든 서술형 필드는 자연스러운 한국어로 작성하세요. "
            "기업명, 기관명, 제품명, 종목 티커, MBTI, 사용자명 같은 고유명사는 원래 표기를 유지하세요."
        )
        return base_prompt

    def _build_individual_persona_prompt(
        self,
        entity_name: str,
        entity_type: str,
        entity_summary: str,
        entity_attributes: Dict[str, Any],
        context: str
    ) -> str:
        """개인 엔티티용 상세 인물 설정 프롬프트 구성"""

        attrs_str = json.dumps(entity_attributes, ensure_ascii=False) if entity_attributes else "없음"
        context_str = context[:3000] if context else "추가 컨텍스트 없음"

        return f"""엔티티의 상세한 소셜 미디어 사용자 설정을 생성해 가능한 한 현실 상황을 그대로 재현하세요.

엔티티 이름: {entity_name}
엔티티 유형: {entity_type}
엔티티 요약: {entity_summary}
엔티티 속성: {attrs_str}

컨텍스트 정보:
{context_str}

다음 필드를 포함하는 JSON을 생성하세요:

1. bio: 소셜 미디어 소개, 200자
2. persona: 상세 인물 설정 설명(2000자의 순수 텍스트), 다음을 포함:
   - 기본 정보(나이, 직업, 교육 배경, 거주지)
   - 인물 배경(중요한 경험, 사건과의 연관성, 사회적 관계)
   - 성격 특성(MBTI 유형, 핵심 성격, 감정 표현 방식)
   - 소셜 미디어 행동(게시 빈도, 콘텐츠 선호, 상호작용 스타일, 언어 특징)
   - 입장과 관점(주제에 대한 태도, 화를 내거나 감동할 수 있는 내용)
   - 독특한 특성(말버릇, 특별한 경험, 개인 취미)
   - 개인 기억(설정의 중요한 부분, 이 개인과 사건의 연관성, 사건에서의 기존 행동과 반응)
3. age: 나이 숫자(정수여야 함)
4. gender: 성별, 반드시 영어 "male" 또는 "female"
5. mbti: MBTI 유형(예: INTJ, ENFP 등)
6. country: 국가(한국어 사용, 예: "중국", "미국")
7. profession: 직업
8. interested_topics: 관심 주제 배열

중요:
- 모든 필드 값은 문자열 또는 숫자여야 하며, 줄바꿈을 사용하지 마세요
- persona는 하나의 이어진 문장으로 작성해야 합니다
- 모든 서술형 필드는 한국어로 작성하세요(gender 필드만 영어 male/female 필수)
- 기업명, 기관명, 브랜드명, 종목 티커 같은 고유명사는 원래 표기를 유지하세요
- 내용은 엔티티 정보와 일치해야 합니다
- age는 유효한 정수여야 하며, gender는 반드시 "male" 또는 "female"이어야 합니다
"""

    def _build_group_persona_prompt(
        self,
        entity_name: str,
        entity_type: str,
        entity_summary: str,
        entity_attributes: Dict[str, Any],
        context: str
    ) -> str:
        """집단/기관 엔티티용 상세 인물 설정 프롬프트 구성"""

        attrs_str = json.dumps(entity_attributes, ensure_ascii=False) if entity_attributes else "없음"
        context_str = context[:3000] if context else "추가 컨텍스트 없음"

        return f"""기관/집단 엔티티의 상세한 소셜 미디어 계정 설정을 생성해 가능한 한 현실 상황을 그대로 재현하세요.

엔티티 이름: {entity_name}
엔티티 유형: {entity_type}
엔티티 요약: {entity_summary}
엔티티 속성: {attrs_str}

컨텍스트 정보:
{context_str}

다음 필드를 포함하는 JSON을 생성하세요:

1. bio: 공식 계정 소개, 200자, 전문적이고 단정하게
2. persona: 상세 계정 설정 설명(2000자의 순수 텍스트), 다음을 포함:
   - 기관 기본 정보(정식 명칭, 기관 성격, 설립 배경, 주요 기능)
   - 계정 포지셔닝(계정 유형, 목표 수신자, 핵심 기능)
   - 발언 스타일(언어 특징, 자주 쓰는 표현, 금기 주제)
   - 게시물 특징(콘텐츠 유형, 게시 빈도, 활동 시간대)
   - 입장과 태도(핵심 주제에 대한 공식 입장, 논란 대응 방식)
   - 특별 설명(대표하는 집단 이미지, 운영 습관)
   - 기관 기억(설정의 중요한 부분, 이 기관과 사건의 연관성, 사건에서의 기존 행동과 반응)
3. age: 고정값 30(기관 계정의 가상 나이)
4. gender: 고정값 "other"(기관 계정은 other로 비개인 표시)
5. mbti: MBTI 유형, 계정 스타일 설명용(예: ISTJ는 엄격하고 보수적)
6. country: 국가(한국어 사용, 예: "중국", "미국")
7. profession: 기관 기능 설명
8. interested_topics: 관심 분야 배열

중요:
- 모든 필드 값은 문자열 또는 숫자여야 하며 null 값을 허용하지 않습니다
- persona는 하나의 이어진 문장으로 작성하고 줄바꿈을 사용하지 마세요
- 모든 서술형 필드는 한국어로 작성하세요(gender 필드만 영어 "other" 필수)
- 기업명, 기관명, 브랜드명, 종목 티커 같은 고유명사는 원래 표기를 유지하세요
- age는 정수 30이어야 하고, gender는 반드시 문자열 "other"여야 합니다
- 기관 계정 발언은 해당 정체성에 맞아야 합니다"""

    def _generate_profile_rule_based(
        self,
        entity_name: str,
        entity_type: str,
        entity_summary: str,
        entity_attributes: Dict[str, Any]
    ) -> Dict[str, Any]:
        """규칙 기반으로 기본 인물 설정 생성"""

        # 엔티티 유형에 따라 다른 설정 생성
        entity_type_lower = entity_type.lower()

        if entity_type_lower in ["student", "alumni"]:
            return {
                "bio": f"{entity_type} - 학업과 사회 이슈에 관심이 있습니다.",
                "persona": f"{entity_name}은(는) 학업과 사회적 논의에 적극적으로 참여하는 {entity_type.lower()}입니다. 관점을 나누고 동료들과 연결되는 것을 좋아합니다.",
                "age": random.randint(18, 30),
                "gender": random.choice(["male", "female"]),
                "mbti": random.choice(self.MBTI_TYPES),
                "country": random.choice(self.COUNTRIES),
                "profession": "학생",
                "interested_topics": ["교육", "사회 이슈", "기술"],
            }

        elif entity_type_lower in ["publicfigure", "expert", "faculty"]:
            return {
                "bio": "해당 분야의 전문가이자 사고 리더입니다.",
                "persona": f"{entity_name}은(는) 중요한 사안에 대한 통찰과 의견을 공유하는 잘 알려진 {entity_type.lower()}입니다. 전문성과 공적 담론에서의 영향력으로 알려져 있습니다.",
                "age": random.randint(35, 60),
                "gender": random.choice(["male", "female"]),
                "mbti": random.choice(["ENTJ", "INTJ", "ENTP", "INTP"]),
                "country": random.choice(self.COUNTRIES),
                "profession": entity_attributes.get("occupation", "전문가"),
                "interested_topics": ["정치", "경제", "문화와 사회"],
            }

        elif entity_type_lower in ["mediaoutlet", "socialmediaplatform"]:
            return {
                "bio": f"{entity_name} 공식 계정입니다. 뉴스와 업데이트를 제공합니다.",
                "persona": f"{entity_name}은(는) 뉴스를 보도하고 공적 담론을 촉진하는 미디어 엔티티입니다. 이 계정은 시의성 있는 업데이트를 공유하고 시사 이슈에 대해 팔로워와 소통합니다.",
                "age": 30,  # 기관 가상 나이
                "gender": "other",  # 기관 계정은 other 사용
                "mbti": "ISTJ",  # 기관 스타일: 엄격하고 보수적
                "country": "미상",
                "profession": "미디어",
                "interested_topics": ["일반 뉴스", "시사", "공공 사안"],
            }

        elif entity_type_lower in ["university", "governmentagency", "ngo", "organization"]:
            return {
                "bio": f"{entity_name}의 공식 계정입니다.",
                "persona": f"{entity_name}은(는) 공식 입장과 공지 사항을 전달하고 관련 이해관계자와 소통하는 기관 엔티티입니다.",
                "age": 30,  # 기관 가상 나이
                "gender": "other",  # 기관 계정은 other 사용
                "mbti": "ISTJ",  # 기관 스타일: 엄격하고 보수적
                "country": "미상",
                "profession": entity_type,
                "interested_topics": ["공공 정책", "커뮤니티", "공식 공지"],
            }

        else:
            # 기본 설정
            return {
                "bio": entity_summary[:150] if entity_summary else f"{entity_type}: {entity_name}",
                "persona": entity_summary or f"{entity_name}은(는) 사회적 논의에 참여하는 {entity_type.lower()}입니다.",
                "age": random.randint(25, 50),
                "gender": random.choice(["male", "female"]),
                "mbti": random.choice(self.MBTI_TYPES),
                "country": random.choice(self.COUNTRIES),
                "profession": entity_type,
                "interested_topics": ["일반", "사회 이슈"],
            }

    def set_graph_id(self, graph_id: str):
        """강화 검색용 그래프 ID 설정"""
        self.graph_id = graph_id

    def generate_profiles_from_entities(
        self,
        entities: List[EntityNode],
        use_llm: bool = True,
        progress_callback: Optional[callable] = None,
        graph_id: Optional[str] = None,
        parallel_count: int = 5,
        realtime_output_path: Optional[str] = None,
        output_platform: str = "reddit"
    ) -> List[OasisAgentProfile]:
        """
        엔티티로부터 Agent Profile을 일괄 생성합니다(병렬 생성 지원).

        Args:
            entities: 엔티티 목록
            use_llm: 상세 인물 설정을 생성할 때 LLM 사용 여부
            progress_callback: 진행 콜백 함수 (current, total, message)
            graph_id: 그래프 검색으로 더 풍부한 컨텍스트를 가져오기 위한 그래프 ID
            parallel_count: 병렬 생성 수, 기본 5
            realtime_output_path: 실시간으로 기록할 파일 경로(제공하면 생성할 때마다 기록)
            output_platform: 출력 플랫폼 형식 ("reddit" 또는 "twitter")

        Returns:
            Agent Profile 목록
        """
        import concurrent.futures
        from threading import Lock

        # 그래프 검색에 사용할 graph_id 설정
        if graph_id:
            self.graph_id = graph_id

        total = len(entities)
        profiles = [None] * total  # 순서를 유지하도록 미리 할당
        completed_count = [0]  # 클로저에서 수정할 수 있도록 리스트 사용
        lock = Lock()

        # 실시간 파일 기록 보조 함수
        def save_profiles_realtime():
            """생성된 profiles를 실시간으로 파일에 저장"""
            if not realtime_output_path:
                return

            with lock:
                # 생성된 profiles만 필터링
                existing_profiles = [p for p in profiles if p is not None]
                if not existing_profiles:
                    return

                try:
                    if output_platform == "reddit":
                        # Reddit JSON 형식
                        profiles_data = [p.to_reddit_format() for p in existing_profiles]
                        with open(realtime_output_path, 'w', encoding='utf-8') as f:
                            json.dump(profiles_data, f, ensure_ascii=False, indent=2)
                    else:
                        # Twitter CSV 형식
                        import csv
                        profiles_data = [p.to_twitter_format() for p in existing_profiles]
                        if profiles_data:
                            fieldnames = list(profiles_data[0].keys())
                            with open(realtime_output_path, 'w', encoding='utf-8', newline='') as f:
                                writer = csv.DictWriter(f, fieldnames=fieldnames)
                                writer.writeheader()
                                writer.writerows(profiles_data)
                except Exception as e:
                    logger.warning(f"profiles 실시간 저장 실패: {e}")

        def generate_single_profile(idx: int, entity: EntityNode) -> tuple:
            """단일 profile 생성 작업 함수"""
            entity_type = entity.get_entity_type() or "Entity"

            try:
                profile = self.generate_profile_from_entity(
                    entity=entity,
                    user_id=idx,
                    use_llm=use_llm
                )

                # 생성된 인물 설정을 콘솔과 로그에 실시간 출력
                self._print_generated_profile(entity.name, entity_type, profile)

                return idx, profile, None

            except Exception as e:
                logger.error(f"엔티티 {entity.name}의 인물 설정 생성 실패: {str(e)}")
                # 기본 profile 생성
                fallback_profile = OasisAgentProfile(
                    user_id=idx,
                    user_name=self._generate_username(entity.name),
                    name=entity.name,
                    bio=f"{entity_type}: {entity.name}",
                    persona=entity.summary or "사회적 논의에 참여하는 사람입니다.",
                    source_entity_uuid=entity.uuid,
                    source_entity_type=entity_type,
                )
                return idx, fallback_profile, str(e)

        logger.info(f"Agent 인물 설정 병렬 생성 시작: 총 {total}개, 병렬 수: {parallel_count}")

        # 스레드 풀로 병렬 실행
        with concurrent.futures.ThreadPoolExecutor(max_workers=parallel_count) as executor:
            # 모든 작업 제출
            future_to_entity = {
                executor.submit(generate_single_profile, idx, entity): (idx, entity)
                for idx, entity in enumerate(entities)
            }

            # 결과 수집
            for future in concurrent.futures.as_completed(future_to_entity):
                idx, entity = future_to_entity[future]
                entity_type = entity.get_entity_type() or "Entity"

                try:
                    result_idx, profile, error = future.result()
                    profiles[result_idx] = profile

                    with lock:
                        completed_count[0] += 1
                        current = completed_count[0]

                    # 실시간 파일 기록
                    save_profiles_realtime()

                    if progress_callback:
                        progress_callback(
                            current,
                            total,
                            f"완료 {current}/{total}: {entity.name} ({entity_type})"
                        )

                    if error:
                        logger.warning(f"[{current}/{total}] {entity.name} 기본 인물 설정 사용: {error}")
                    else:
                        logger.info(f"[{current}/{total}] 인물 설정 생성 성공: {entity.name} ({entity_type})")

                except Exception as e:
                    logger.error(f"엔티티 {entity.name} 처리 중 예외 발생: {str(e)}")
                    with lock:
                        completed_count[0] += 1
                    profiles[idx] = OasisAgentProfile(
                        user_id=idx,
                        user_name=self._generate_username(entity.name),
                        name=entity.name,
                        bio=f"{entity_type}: {entity.name}",
                        persona=entity.summary or "사회적 논의에 참여하는 사람입니다.",
                        source_entity_uuid=entity.uuid,
                        source_entity_type=entity_type,
                    )
                    # 기본 인물 설정이어도 실시간 파일에 기록
                    save_profiles_realtime()

        logger.info("인물 설정 생성 완료: 총 %s개 Agent 생성", len([p for p in profiles if p]))

        return profiles

    def _print_generated_profile(self, entity_name: str, entity_type: str, profile: OasisAgentProfile):
        """생성된 인물 설정을 콘솔에 실시간 출력(전체 내용, 생략 없음)"""
        separator = "-" * 70

        # 전체 출력 내용 구성(생략 없음)
        topics_str = ', '.join(profile.interested_topics) if profile.interested_topics else '없음'

        output_lines = [
            f"\n{separator}",
            f"[생성됨] {entity_name} ({entity_type})",
            f"{separator}",
            f"사용자 이름: {profile.user_name}",
            f"",
            f"【소개】",
            f"{profile.bio}",
            f"",
            f"【상세 인물 설정】",
            f"{profile.persona}",
            f"",
            f"【기본 속성】",
            f"나이: {profile.age} | 성별: {profile.gender} | MBTI: {profile.mbti}",
            f"직업: {profile.profession} | 국가: {profile.country}",
            f"관심 주제: {topics_str}",
            separator
        ]

        output = "\n".join(output_lines)

        logger.debug(output)

    def save_profiles(
        self,
        profiles: List[OasisAgentProfile],
        file_path: str,
        platform: str = "reddit"
    ):
        """
        플랫폼에 맞는 올바른 형식으로 Profile을 파일에 저장합니다.

        OASIS 플랫폼 형식 요구사항:
        - Twitter: CSV 형식
        - Reddit: JSON 형식

        Args:
            profiles: Profile 목록
            file_path: 파일 경로
            platform: 플랫폼 유형 ("reddit" 또는 "twitter")
        """
        if platform == "twitter":
            self._save_twitter_csv(profiles, file_path)
        else:
            self._save_reddit_json(profiles, file_path)

    def _save_twitter_csv(self, profiles: List[OasisAgentProfile], file_path: str):
        """
        Twitter Profile을 CSV 형식으로 저장합니다(OASIS 공식 요구사항 준수).

        OASIS Twitter가 요구하는 CSV 필드:
        - user_id: 사용자 ID(CSV 순서 기준 0부터 시작)
        - name: 사용자 실명
        - username: 시스템 내 사용자 이름
        - user_char: 상세 인물 설명(LLM 시스템 프롬프트에 주입되어 Agent 행동을 안내)
        - description: 짧은 공개 소개(사용자 프로필 페이지에 표시)

        user_char vs description 차이:
        - user_char: 내부 사용, LLM 시스템 프롬프트, Agent의 사고와 행동을 결정
        - description: 외부 표시, 다른 사용자에게 보이는 소개
        """
        import csv

        # 파일 확장자가 .csv인지 확인
        if not file_path.endswith('.csv'):
            file_path = file_path.replace('.json', '.csv')

        with open(file_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)

            # OASIS 요구 헤더 작성
            headers = ['user_id', 'name', 'username', 'user_char', 'description']
            writer.writerow(headers)

            # 데이터 행 작성
            for idx, profile in enumerate(profiles):
                # user_char: 완전한 인물 설정(bio + persona), LLM 시스템 프롬프트용
                user_char = profile.bio
                if profile.persona and profile.persona != profile.bio:
                    user_char = f"{profile.bio} {profile.persona}"
                # 줄바꿈 처리(CSV에서는 공백으로 대체)
                user_char = user_char.replace('\n', ' ').replace('\r', ' ')

                # description: 외부 표시용 짧은 소개
                description = profile.bio.replace('\n', ' ').replace('\r', ' ')

                row = [
                    idx,                    # user_id: 0부터 시작하는 순서 ID
                    profile.name,           # name: 실명
                    profile.user_name,      # username: 사용자 이름
                    user_char,              # user_char: 완전한 인물 설정(내부 LLM 사용)
                    description             # description: 짧은 소개(외부 표시)
                ]
                writer.writerow(row)

        logger.info(f"Twitter Profile {len(profiles)}개를 {file_path}에 저장했습니다(OASIS CSV 형식)")

    def _normalize_gender(self, gender: Optional[str]) -> str:
        """
        gender 필드를 OASIS 요구 영어 형식으로 표준화합니다.

        OASIS 요구: male, female, other
        """
        if not gender:
            return "other"

        gender_lower = gender.lower().strip()

        # 다국어 입력 매핑
        gender_map = {
            "남": "male",
            "남성": "male",
            "\u7537": "male",
            "여": "female",
            "여성": "female",
            "\u5973": "female",
            "기관": "other",
            "기타": "other",
            "\u5176\u4ed6": "other",
            # 영어는 그대로
            "male": "male",
            "female": "female",
            "other": "other",
        }

        return gender_map.get(gender_lower, "other")

    def _save_reddit_json(self, profiles: List[OasisAgentProfile], file_path: str):
        """
        Reddit Profile을 JSON 형식으로 저장합니다.

        to_reddit_format()과 일치하는 형식을 사용해 OASIS가 올바르게 읽도록 합니다.
        user_id 필드는 반드시 포함해야 하며, 이는 OASIS agent_graph.get_agent() 매칭의 핵심입니다!

        필수 필드:
        - user_id: 사용자 ID(정수, initial_posts의 poster_agent_id와 매칭)
        - username: 사용자 이름
        - name: 표시 이름
        - bio: 소개
        - persona: 상세 인물 설정
        - age: 나이(정수)
        - gender: "male", "female", 또는 "other"
        - mbti: MBTI 유형
        - country: 국가
        """
        data = []
        for idx, profile in enumerate(profiles):
            # to_reddit_format()과 일치하는 형식 사용
            item = {
                "user_id": profile.user_id if profile.user_id is not None else idx,  # 핵심: user_id는 반드시 포함해야 합니다
                "username": profile.user_name,
                "name": profile.name,
                "bio": profile.bio[:150] if profile.bio else f"{profile.name}",
                "persona": profile.persona or f"{profile.name}은(는) 사회적 논의에 참여하는 사람입니다.",
                "karma": profile.karma if profile.karma else 1000,
                "created_at": profile.created_at,
                # OASIS 필수 필드 - 모두 기본값이 있도록 보장
                "age": profile.age if profile.age else 30,
                "gender": self._normalize_gender(profile.gender),
                "mbti": profile.mbti if profile.mbti else "ISTJ",
                "country": profile.country if profile.country else "미상",
            }

            # 선택 필드
            if profile.profession:
                item["profession"] = profile.profession
            if profile.interested_topics:
                item["interested_topics"] = profile.interested_topics

            data.append(item)

        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info(f"Reddit Profile {len(profiles)}개를 {file_path}에 저장했습니다(JSON 형식, user_id 필드 포함)")

    # 기존 메서드명을 별칭으로 유지해 하위 호환성 보장
    def save_profiles_to_json(
        self,
        profiles: List[OasisAgentProfile],
        file_path: str,
        platform: str = "reddit"
    ):
        """[사용 중단] save_profiles() 메서드를 사용하세요"""
        logger.warning("save_profiles_to_json은 사용 중단되었습니다. save_profiles 메서드를 사용하세요")
        self.save_profiles(profiles, file_path, platform)
