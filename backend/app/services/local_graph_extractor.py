"""
로컬 그래프 추출기
LLM을 사용해 텍스트 블록에서 엔티티와 관계를 추출한다.
"""

import json
from typing import Any, Dict, List, Optional

from ..utils.llm_client import LLMClient
from ..utils.ontology import normalize_ontology


class LocalGraphExtractor:
    """LLM 기반 로컬 그래프 추출기"""

    ORG_HINTS = [
        "大学", "学院", "学校", "公司", "集团", "机构", "组织", "协会",
        "政府", "部门", "委员会", "媒体", "平台", "医院", "实验室",
        "university", "college", "company", "group", "agency", "organization",
        "committee", "media", "platform", "hospital", "lab",
    ]

    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm = llm_client or LLMClient()

    @staticmethod
    def _normalize_token(value: str) -> str:
        return "".join(ch.lower() for ch in (value or "").strip() if ch.isalnum())

    @classmethod
    def _normalize_aliases(cls, aliases: Any, primary_name: str = "") -> List[str]:
        if not isinstance(aliases, list):
            return []

        primary_key = cls._normalize_token(primary_name)
        normalized_aliases: List[str] = []
        seen = set()

        for alias in aliases:
            if not isinstance(alias, str):
                continue

            cleaned = alias.strip()
            alias_key = cls._normalize_token(cleaned)
            if not cleaned or not alias_key or alias_key == primary_key or alias_key in seen:
                continue

            seen.add(alias_key)
            normalized_aliases.append(cleaned)

        return normalized_aliases

    def _normalize_entity_type(self, value: str, allowed_types: List[str], name: str = "") -> Optional[str]:
        if not allowed_types:
            return value or None

        target = self._normalize_token(value)
        mapping = {self._normalize_token(item): item for item in allowed_types}
        if target in mapping:
            return mapping[target]

        if "Organization" in allowed_types:
            lowered_name = (name or "").lower()
            if any(hint in name or hint in lowered_name for hint in self.ORG_HINTS):
                return "Organization"

        if "Person" in allowed_types:
            return "Person"

        return None

    def _normalize_edge_type(self, value: str, allowed_types: List[str]) -> Optional[str]:
        target = self._normalize_token(value)
        mapping = {self._normalize_token(item): item for item in allowed_types}
        return mapping.get(target)

    def _sanitize_entity(
        self,
        entity: Dict[str, Any],
        entity_types: List[str],
        attribute_allowlist: Dict[str, set],
    ) -> Optional[Dict[str, Any]]:
        name = (entity.get("name") or "").strip()
        entity_type = self._normalize_entity_type(entity.get("type", ""), entity_types, name)
        if not name or not entity_type:
            return None

        allowed_attrs = attribute_allowlist.get(entity_type, set())
        attributes = {}
        for key, value in (entity.get("attributes") or {}).items():
            if key in allowed_attrs and value not in [None, "", [], {}]:
                attributes[key] = value

        return {
            "name": name,
            "type": entity_type,
            "aliases": self._normalize_aliases(entity.get("aliases"), primary_name=name),
            "summary": (entity.get("summary") or "").strip(),
            "attributes": attributes,
        }

    def _sanitize_relationship(
        self,
        relationship: Dict[str, Any],
        edge_types: List[str],
        entity_types: List[str],
        edge_attribute_allowlist: Dict[str, set],
    ) -> Optional[Dict[str, Any]]:
        relation_type = self._normalize_edge_type(relationship.get("type", ""), edge_types)
        source_name = (relationship.get("source_name") or "").strip()
        target_name = (relationship.get("target_name") or "").strip()
        if not relation_type or not source_name or not target_name:
            return None

        source_type = self._normalize_entity_type(
            relationship.get("source_type", ""),
            entity_types,
            source_name,
        )
        target_type = self._normalize_entity_type(
            relationship.get("target_type", ""),
            entity_types,
            target_name,
        )

        attributes = {}
        allowed_attrs = edge_attribute_allowlist.get(relation_type, set())
        for key, value in (relationship.get("attributes") or {}).items():
            if key in allowed_attrs and value not in [None, "", [], {}]:
                attributes[key] = value

        fact = (relationship.get("fact") or "").strip()
        if not fact:
            fact = f"{source_name}와 {target_name} 사이에 {relation_type} 관계가 존재함"

        return {
            "type": relation_type,
            "source_name": source_name,
            "source_type": source_type,
            "target_name": target_name,
            "target_type": target_type,
            "fact": fact,
            "attributes": attributes,
        }

    def extract(
        self,
        text: str,
        ontology: Dict[str, Any],
        known_entities: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        ontology = normalize_ontology(ontology)
        entity_defs = ontology.get("entity_types", [])
        edge_defs = ontology.get("edge_types", [])

        entity_types = [item.get("name", "") for item in entity_defs if item.get("name")]
        edge_types = [item.get("name", "") for item in edge_defs if item.get("name")]
        entity_attribute_allowlist = {
            item.get("name"): {attr.get("name") for attr in item.get("attributes", []) if attr.get("name")}
            for item in entity_defs
            if item.get("name")
        }
        edge_attribute_allowlist = {
            item.get("name"): {attr.get("name") for attr in item.get("attributes", []) if attr.get("name")}
            for item in edge_defs
            if item.get("name")
        }

        known_entities = known_entities or []
        known_entities_text = json.dumps(known_entities[:80], ensure_ascii=False, indent=2)
        ontology_text = json.dumps(
            {
                "entity_types": entity_defs,
                "edge_types": edge_defs,
            },
            ensure_ascii=False,
            indent=2,
        )

        system_prompt = """당신은 지식 그래프 추출 도우미입니다. 당신의 임무는 텍스트에서 “소셜 미디어에서 발언할 수 있는 주체”와 그들 사이의 명확한 관계를 추출하는 것입니다.

반드시 지켜야 할 사항:
1. 제공된 ontology에 정의된 엔티티 유형과 관계 유형만 사용한다
2. 텍스트에 명시적으로 등장하거나 직접 확인 가능한 정보만 추출하고, 추측하지 않는다
3. 관계의 source_name과 target_name은 구체적인 엔티티 이름이어야 한다
4. attributes는 ontology에 정의된 속성명만 사용할 수 있다
5. 출력은 JSON 객체여야 하며, 다음만 포함해야 한다:
{
  "entities": [{"name": "...", "type": "...", "aliases": ["..."], "summary": "...", "attributes": {...}}],
  "relationships": [{"type": "...", "source_name": "...", "source_type": "...", "target_name": "...", "target_type": "...", "fact": "...", "attributes": {...}}],
  "summary": "..."
}
6. 추출할 내용이 없으면 빈 배열을 반환하고, 만들어내지 않는다
7. 관계 유형이 애매하면 ontology 안에서 가장 가까운 관계 유형 하나로 매핑한다. 관계를 새로 만들지 말고 가장 가까운 기존 관계를 사용한다
8. 엔티티 유형이 애매하면 ontology 안에서 가장 가까운 엔티티 유형으로 매핑한다. 특히 구체 유형이 불명확하면 Person 또는 Organization을 우선 사용한다
9. known entities에 이미 있는 이름이 보이면 그 엔티티를 재사용하고, 관계도 그 이름을 기준으로 연결한다
10. 텍스트에 명시적인 소속, 보도, 대응, 지지, 반대, 협력 관계가 있으면 relationships를 비우지 말고 최소 1개 이상 추출한다
11. 서로 다른 언어/문자 표기라도 같은 실제 엔티티면 새 엔티티를 만들지 말고 기존 엔티티의 name을 재사용한다
12. 다른 언어 표기, 번역명, 음역명은 entities[].aliases에 넣는다. 예: Wuhan University / 武汉大学 / 우한대학교
13. relationships의 source_name과 target_name은 가능하면 known entities의 canonical name을 그대로 사용한다
"""

        user_prompt = f"""## Ontology
{ontology_text}

## Known entities in graph
{known_entities_text}

## Text chunk
{text}

엔티티와 관계를 추출해 주세요. summary는 이 구간이 새롭게 추가한 정보를 한국어로 간단히 설명해 주세요."""

        for attempt in range(3):
            try:
                raw = self.llm.chat_json(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=max(0.1, 0.3 - 0.1 * attempt),
                    max_tokens=4096,
                )

                entities = []
                seen_entities = set()
                for item in raw.get("entities", []):
                    sanitized = self._sanitize_entity(
                        item,
                        entity_types,
                        entity_attribute_allowlist,
                    )
                    if not sanitized:
                        continue
                    dedupe_key = (
                        self._normalize_token(sanitized["name"]),
                        self._normalize_token(sanitized["type"]),
                    )
                    if dedupe_key in seen_entities:
                        continue
                    seen_entities.add(dedupe_key)
                    entities.append(sanitized)

                relationships = []
                seen_relationships = set()
                for item in raw.get("relationships", []):
                    sanitized = self._sanitize_relationship(
                        item,
                        edge_types,
                        entity_types,
                        edge_attribute_allowlist,
                    )
                    if not sanitized:
                        continue
                    dedupe_key = (
                        self._normalize_token(sanitized["type"]),
                        self._normalize_token(sanitized["source_name"]),
                        self._normalize_token(sanitized["target_name"]),
                        sanitized["fact"],
                    )
                    if dedupe_key in seen_relationships:
                        continue
                    seen_relationships.add(dedupe_key)
                    relationships.append(sanitized)

                return {
                    "entities": entities,
                    "relationships": relationships,
                    "summary": (raw.get("summary") or "").strip(),
                }
            except Exception:
                continue

        return {
            "entities": [],
            "relationships": [],
            "summary": "",
        }
