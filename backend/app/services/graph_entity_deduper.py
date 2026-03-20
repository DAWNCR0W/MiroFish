"""
기존 그래프 엔티티 중복 병합 서비스
다국어 표기/이명으로 분리된 동일 엔티티를 LLM으로 판별해 병합한다.
"""

import json
from collections import defaultdict
from typing import Any, Dict, List, Optional

from ..utils.llm_client import LLMClient
from ..utils.logger import get_logger
from .local_graph_store import LocalGraphStore


logger = get_logger("mirofish.graph_entity_deduper")


class GraphEntityDeduper:
    """기존 그래프의 중복 엔티티를 찾아 canonical node로 병합한다."""

    MAX_NODES_PER_BATCH = 40
    BATCH_OVERLAP = 10
    RELATED_NAMES_LIMIT = 6

    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        store: Optional[LocalGraphStore] = None,
    ):
        self.llm = llm_client or LLMClient()
        self.store = store or LocalGraphStore()

    @staticmethod
    def _custom_label(labels: List[str]) -> str:
        return next(
            (
                label for label in labels or []
                if label not in ["Entity", "Node"]
            ),
            "",
        )

    @classmethod
    def _chunk_contexts(cls, contexts: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
        if len(contexts) <= cls.MAX_NODES_PER_BATCH:
            return [contexts]

        batches: List[List[Dict[str, Any]]] = []
        step = max(1, cls.MAX_NODES_PER_BATCH - cls.BATCH_OVERLAP)
        for start in range(0, len(contexts), step):
            batch = contexts[start:start + cls.MAX_NODES_PER_BATCH]
            if batch:
                batches.append(batch)
            if start + cls.MAX_NODES_PER_BATCH >= len(contexts):
                break
        return batches

    @staticmethod
    def _normalize_merge_groups(raw_groups: Any, allowed_uuids: set) -> List[Dict[str, Any]]:
        normalized_groups: List[Dict[str, Any]] = []

        if not isinstance(raw_groups, list):
            return normalized_groups

        for item in raw_groups:
            reason = ""
            candidate_uuids: Any = []

            if isinstance(item, dict):
                candidate_uuids = item.get("node_uuids") or item.get("uuids") or item.get("nodes") or []
                reason = (item.get("reason") or "").strip()
            elif isinstance(item, list):
                candidate_uuids = item

            deduped_uuids: List[str] = []
            seen = set()
            for value in candidate_uuids:
                if not isinstance(value, str):
                    continue
                if value not in allowed_uuids or value in seen:
                    continue
                seen.add(value)
                deduped_uuids.append(value)

            if len(deduped_uuids) >= 2:
                normalized_groups.append({
                    "node_uuids": deduped_uuids,
                    "reason": reason,
                })

        return normalized_groups

    @staticmethod
    def _merge_overlapping_groups(groups: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not groups:
            return []

        parent: Dict[str, str] = {}
        reason_map: Dict[str, List[str]] = defaultdict(list)

        def find(value: str) -> str:
            parent.setdefault(value, value)
            if parent[value] != value:
                parent[value] = find(parent[value])
            return parent[value]

        def union(left: str, right: str) -> None:
            left_root = find(left)
            right_root = find(right)
            if left_root != right_root:
                parent[right_root] = left_root

        for group in groups:
            uuids = group["node_uuids"]
            first = uuids[0]
            for other in uuids[1:]:
                union(first, other)

        for group in groups:
            root = find(group["node_uuids"][0])
            reason = (group.get("reason") or "").strip()
            if reason and reason not in reason_map[root]:
                reason_map[root].append(reason)

        grouped: Dict[str, List[str]] = defaultdict(list)
        for group in groups:
            for uuid in group["node_uuids"]:
                root = find(uuid)
                if uuid not in grouped[root]:
                    grouped[root].append(uuid)

        merged_groups: List[Dict[str, Any]] = []
        for root, uuids in grouped.items():
            if len(uuids) < 2:
                continue
            merged_groups.append({
                "node_uuids": uuids,
                "reason": " / ".join(reason_map.get(root, [])),
            })

        return merged_groups

    @staticmethod
    def _choose_primary_uuid(contexts: List[Dict[str, Any]]) -> str:
        ranked = sorted(
            contexts,
            key=lambda item: (
                -(item.get("degree") or 0),
                -(item.get("episode_count") or 0),
                -len(item.get("summary", "") or ""),
                item.get("created_at") or "",
                item.get("name") or "",
            ),
        )
        return ranked[0]["uuid"]

    def _build_node_contexts(self, graph: Dict[str, Any]) -> List[Dict[str, Any]]:
        nodes = graph.get("nodes", []) or []
        edges = graph.get("edges", []) or []
        node_map = {
            node.get("uuid"): node
            for node in nodes
            if node.get("uuid")
        }
        related_names_map: Dict[str, List[str]] = defaultdict(list)
        degree_map: Dict[str, int] = defaultdict(int)

        for edge in edges:
            source_uuid = edge.get("source_node_uuid")
            target_uuid = edge.get("target_node_uuid")
            if source_uuid:
                degree_map[source_uuid] += 1
                target_name = node_map.get(target_uuid, {}).get("name", "")
                if target_name and target_name not in related_names_map[source_uuid]:
                    related_names_map[source_uuid].append(target_name)
            if target_uuid:
                degree_map[target_uuid] += 1
                source_name = node_map.get(source_uuid, {}).get("name", "")
                if source_name and source_name not in related_names_map[target_uuid]:
                    related_names_map[target_uuid].append(source_name)

        contexts: List[Dict[str, Any]] = []
        for node in nodes:
            node_uuid = node.get("uuid", "")
            entity_type = self._custom_label(node.get("labels", []) or [])
            if not node_uuid or not entity_type:
                continue

            contexts.append({
                "uuid": node_uuid,
                "name": node.get("name", ""),
                "type": entity_type,
                "aliases": (node.get("aliases", []) or [])[:6],
                "summary": node.get("summary", "") or "",
                "related_names": related_names_map.get(node_uuid, [])[: self.RELATED_NAMES_LIMIT],
                "degree": degree_map.get(node_uuid, 0),
                "episode_count": len(node.get("episodes", []) or []),
                "created_at": node.get("created_at"),
            })

        return contexts

    def _detect_merge_groups(
        self,
        entity_type: str,
        contexts: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        if len(contexts) < 2:
            return []

        system_prompt = """당신은 그래프 엔티티 canonicalization 전문가입니다.

목표:
- 서로 다른 언어 표기, 번역명, 음역명, 약칭 때문에 분리된 노드 중 같은 실제 엔티티를 찾는다.

중요 규칙:
1. 같은 실제 엔티티라고 매우 확실할 때만 병합 후보로 제안한다. 보수적으로 판단한다.
2. 언어만 다른 동일 기관/동일 인물/동일 조직은 병합할 수 있다.
3. 서로 관련된 기관, 상하위 조직, 같은 도시의 다른 기관, 동명이인은 병합하면 안 된다.
4. node_uuids에는 같은 실제 엔티티라고 확신하는 노드들만 넣는다.
5. 출력은 JSON 객체 하나만 반환한다.

출력 형식:
{
  "merge_groups": [
    {
      "node_uuids": ["node_a", "node_b"],
      "reason": "한 문장 설명"
    }
  ],
  "summary": "간단한 한국어 요약"
}
"""

        user_prompt = f"""엔티티 유형: {entity_type}

다음 노드들 중 같은 실제 엔티티인 것만 병합 후보로 골라 주세요.
이름, aliases, summary, related_names를 함께 보고 판단하세요.

{json.dumps(contexts, ensure_ascii=False, indent=2)}
"""

        try:
            response = self.llm.chat_json(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.1,
                max_tokens=2048,
            )
        except Exception as exc:
            logger.warning("엔티티 병합 후보 탐지 실패: type=%s, error=%s", entity_type, exc)
            return []

        return self._normalize_merge_groups(
            response.get("merge_groups", []),
            allowed_uuids={context["uuid"] for context in contexts},
        )

    def dedupe_graph(self, graph_id: str, dry_run: bool = True) -> Dict[str, Any]:
        graph = self.store.get_graph(graph_id)
        node_count_before = len(graph.get("nodes", []) or [])
        edge_count_before = len(graph.get("edges", []) or [])
        contexts = self._build_node_contexts(graph)
        context_map = {context["uuid"]: context for context in contexts}

        contexts_by_type: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for context in contexts:
            contexts_by_type[context["type"]].append(context)

        proposed_groups: List[Dict[str, Any]] = []
        llm_batches = 0

        for entity_type, typed_contexts in contexts_by_type.items():
            if len(typed_contexts) < 2:
                continue

            ordered_contexts = sorted(
                typed_contexts,
                key=lambda item: (item.get("created_at") or "", item.get("name") or ""),
            )
            raw_groups: List[Dict[str, Any]] = []
            for batch in self._chunk_contexts(ordered_contexts):
                llm_batches += 1
                raw_groups.extend(self._detect_merge_groups(entity_type, batch))

            for group in self._merge_overlapping_groups(raw_groups):
                group_contexts = [
                    context_map[uuid]
                    for uuid in group["node_uuids"]
                    if uuid in context_map
                ]
                if len(group_contexts) < 2:
                    continue

                primary_uuid = self._choose_primary_uuid(group_contexts)
                duplicate_uuids = [
                    context["uuid"] for context in group_contexts
                    if context["uuid"] != primary_uuid
                ]
                if not duplicate_uuids:
                    continue

                primary = context_map[primary_uuid]
                proposed_groups.append({
                    "entity_type": entity_type,
                    "canonical_uuid": primary_uuid,
                    "canonical_name": primary.get("name", ""),
                    "duplicate_uuids": duplicate_uuids,
                    "duplicate_names": [
                        context_map[uuid].get("name", "")
                        for uuid in duplicate_uuids
                        if uuid in context_map
                    ],
                    "reason": group.get("reason", ""),
                })

        applied_groups: List[Dict[str, Any]] = []
        removed_edges = 0

        if not dry_run:
            for group in proposed_groups:
                merge_result = self.store.merge_nodes(
                    graph_id=graph_id,
                    primary_node_uuid=group["canonical_uuid"],
                    duplicate_node_uuids=group["duplicate_uuids"],
                )
                if merge_result.get("merged_count", 0) <= 0:
                    continue

                removed_edges += merge_result.get("removed_edges", 0)
                applied_groups.append({
                    **group,
                    "merged_count": merge_result.get("merged_count", 0),
                    "removed_edges": merge_result.get("removed_edges", 0),
                })

        updated_graph = self.store.get_graph(graph_id)

        return {
            "graph_id": graph_id,
            "dry_run": dry_run,
            "node_count_before": node_count_before,
            "node_count_after": len(updated_graph.get("nodes", []) or []),
            "edge_count_before": edge_count_before,
            "edge_count_after": len(updated_graph.get("edges", []) or []),
            "llm_batches": llm_batches,
            "proposed_merge_groups": proposed_groups,
            "applied_merge_groups": applied_groups,
            "merged_group_count": len(applied_groups),
            "merged_node_count": sum(len(group["duplicate_uuids"]) for group in applied_groups),
            "removed_edge_count": removed_edges,
        }
