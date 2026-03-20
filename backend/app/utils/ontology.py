"""
온톨로지 스키마 정규화 유틸리티
LLM 결과나 저장된 프로젝트 데이터의 들쭉날쭉한 형태를 canonical form으로 맞춘다.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List


RESERVED_ATTRIBUTE_NAMES = {"name", "uuid", "group_id", "created_at", "summary"}
SOURCE_TARGET_PATTERN = re.compile(
    r"source\s*:\s*(?P<source>[^,;]+)\s*[,;]\s*target\s*:\s*(?P<target>[^,;]+)",
    re.IGNORECASE,
)


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float, bool)):
        return str(value).strip()
    return ""


def _truncate(text: str, limit: int = 100) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def normalize_attribute_defs(raw_attributes: Any) -> List[Dict[str, str]]:
    normalized: List[Dict[str, str]] = []
    seen = set()

    def add_attribute(name: Any, attr_type: Any = "text", description: Any = "") -> None:
        attr_name = _stringify(name)
        if not attr_name or attr_name in RESERVED_ATTRIBUTE_NAMES or attr_name in seen:
            return

        seen.add(attr_name)
        normalized.append(
            {
                "name": attr_name,
                "type": _stringify(attr_type) or "text",
                "description": _stringify(description) or attr_name,
            }
        )

    if isinstance(raw_attributes, list):
        for item in raw_attributes:
            if isinstance(item, dict):
                if item.get("name"):
                    add_attribute(item.get("name"), item.get("type"), item.get("description"))
            elif isinstance(item, str):
                add_attribute(item)
    elif isinstance(raw_attributes, dict):
        if raw_attributes.get("name"):
            add_attribute(raw_attributes.get("name"), raw_attributes.get("type"), raw_attributes.get("description"))
        else:
            for key, value in raw_attributes.items():
                if isinstance(value, dict):
                    add_attribute(key, value.get("type"), value.get("description"))
                else:
                    add_attribute(key)
    elif isinstance(raw_attributes, str):
        add_attribute(raw_attributes)

    return normalized


def normalize_examples(raw_examples: Any) -> List[str]:
    if isinstance(raw_examples, list):
        return [_stringify(item) for item in raw_examples if _stringify(item)]

    example = _stringify(raw_examples)
    return [example] if example else []


def _parse_source_target_string(value: str) -> List[Dict[str, str]]:
    pairs: List[Dict[str, str]] = []

    for match in SOURCE_TARGET_PATTERN.finditer(value):
        source = _stringify(match.group("source"))
        target = _stringify(match.group("target"))
        if source and target:
            pairs.append({"source": source, "target": target})

    if pairs:
        return pairs

    if "->" in value:
        source, target = value.split("->", 1)
        source = _stringify(source)
        target = _stringify(target)
        if source and target:
            return [{"source": source, "target": target}]

    return []


def normalize_source_targets(raw_source_targets: Any) -> List[Dict[str, str]]:
    normalized: List[Dict[str, str]] = []
    seen = set()

    def add_pair(source: Any, target: Any) -> None:
        source_name = _stringify(source)
        target_name = _stringify(target)
        if not source_name or not target_name:
            return

        pair = (source_name, target_name)
        if pair in seen:
            return

        seen.add(pair)
        normalized.append({"source": source_name, "target": target_name})

    if isinstance(raw_source_targets, list):
        for item in raw_source_targets:
            if isinstance(item, dict):
                add_pair(item.get("source"), item.get("target"))
            elif isinstance(item, str):
                for pair in _parse_source_target_string(item):
                    add_pair(pair["source"], pair["target"])
    elif isinstance(raw_source_targets, dict):
        add_pair(raw_source_targets.get("source"), raw_source_targets.get("target"))
    elif isinstance(raw_source_targets, str):
        for pair in _parse_source_target_string(raw_source_targets):
            add_pair(pair["source"], pair["target"])

    return normalized


def normalize_entity_types(raw_entity_types: Any) -> List[Dict[str, Any]]:
    if not isinstance(raw_entity_types, list):
        return []

    normalized: List[Dict[str, Any]] = []
    seen = set()

    for item in raw_entity_types:
        if not isinstance(item, dict):
            continue

        name = _stringify(item.get("name"))
        if not name or name in seen:
            continue

        seen.add(name)
        normalized.append(
            {
                "name": name,
                "description": _truncate(_stringify(item.get("description"))),
                "attributes": normalize_attribute_defs(item.get("attributes")),
                "examples": normalize_examples(item.get("examples")),
            }
        )

    return normalized


def normalize_edge_types(raw_edge_types: Any) -> List[Dict[str, Any]]:
    if not isinstance(raw_edge_types, list):
        return []

    normalized: List[Dict[str, Any]] = []
    seen = set()

    for item in raw_edge_types:
        if not isinstance(item, dict):
            continue

        name = _stringify(item.get("name"))
        if not name or name in seen:
            continue

        seen.add(name)
        normalized.append(
            {
                "name": name,
                "description": _truncate(_stringify(item.get("description"))),
                "source_targets": normalize_source_targets(item.get("source_targets")),
                "attributes": normalize_attribute_defs(item.get("attributes")),
            }
        )

    return normalized


def normalize_ontology(raw_ontology: Any) -> Dict[str, Any]:
    ontology = raw_ontology if isinstance(raw_ontology, dict) else {}
    normalized = dict(ontology)
    normalized["entity_types"] = normalize_entity_types(ontology.get("entity_types"))
    normalized["edge_types"] = normalize_edge_types(ontology.get("edge_types"))
    normalized["analysis_summary"] = _stringify(ontology.get("analysis_summary"))
    return normalized
