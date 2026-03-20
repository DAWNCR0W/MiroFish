"""
그래프 엔티티 읽기 및 필터링 서비스
로컬에 저장된 그래프에서 노드와 엣지를 읽고, 시뮬레이션에 필요한 엔티티 컨텍스트를 생성한다.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from ..utils.logger import get_logger
from .local_graph_store import LocalGraphStore

logger = get_logger("mirofish.graph_entity_reader")


@dataclass
class EntityNode:
    """엔티티 노드 데이터 구조"""

    uuid: str
    name: str
    labels: List[str]
    summary: str
    attributes: Dict[str, Any]
    related_edges: List[Dict[str, Any]] = field(default_factory=list)
    related_nodes: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "uuid": self.uuid,
            "name": self.name,
            "labels": self.labels,
            "summary": self.summary,
            "attributes": self.attributes,
            "related_edges": self.related_edges,
            "related_nodes": self.related_nodes,
        }

    def get_entity_type(self) -> Optional[str]:
        for label in self.labels:
            if label not in ["Entity", "Node"]:
                return label
        return None


@dataclass
class FilteredEntities:
    """필터링된 엔티티 집합"""

    entities: List[EntityNode]
    entity_types: Set[str]
    total_count: int
    filtered_count: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entities": [entity.to_dict() for entity in self.entities],
            "entity_types": list(self.entity_types),
            "total_count": self.total_count,
            "filtered_count": self.filtered_count,
        }


class GraphEntityReader:
    """로컬 그래프 엔티티 리더"""

    def __init__(self):
        self.store = LocalGraphStore()

    def get_all_nodes(self, graph_id: str) -> List[Dict[str, Any]]:
        logger.info(f"그래프 {graph_id}의 모든 노드를 가져오는 중...")
        graph = self.store.get_graph(graph_id)
        nodes = []
        for node in graph.get("nodes", []):
            nodes.append({
                "uuid": node.get("uuid", ""),
                "name": node.get("name", ""),
                "labels": node.get("labels", []),
                "summary": node.get("summary", ""),
                "attributes": node.get("attributes", {}),
            })
        logger.info(f"총 {len(nodes)}개 노드를 가져옴")
        return nodes

    def get_all_edges(self, graph_id: str) -> List[Dict[str, Any]]:
        logger.info(f"그래프 {graph_id}의 모든 엣지를 가져오는 중...")
        graph = self.store.get_graph(graph_id)
        edges = []
        for edge in graph.get("edges", []):
            edges.append({
                "uuid": edge.get("uuid", ""),
                "name": edge.get("name", ""),
                "fact": edge.get("fact", ""),
                "source_node_uuid": edge.get("source_node_uuid", ""),
                "target_node_uuid": edge.get("target_node_uuid", ""),
                "attributes": edge.get("attributes", {}),
            })
        logger.info(f"총 {len(edges)}개 엣지를 가져옴")
        return edges

    def get_node_edges(self, graph_id: str, node_uuid: str) -> List[Dict[str, Any]]:
        edges = self.get_all_edges(graph_id)
        return [
            edge for edge in edges
            if edge.get("source_node_uuid") == node_uuid or edge.get("target_node_uuid") == node_uuid
        ]

    def filter_defined_entities(
        self,
        graph_id: str,
        defined_entity_types: Optional[List[str]] = None,
        enrich_with_edges: bool = True,
    ) -> FilteredEntities:
        logger.info(f"그래프 {graph_id}의 엔티티 필터링을 시작함...")

        all_nodes = self.get_all_nodes(graph_id)
        total_count = len(all_nodes)
        all_edges = self.get_all_edges(graph_id) if enrich_with_edges else []
        node_map = {node["uuid"]: node for node in all_nodes}

        filtered_entities: List[EntityNode] = []
        entity_types_found: Set[str] = set()

        for node in all_nodes:
            labels = node.get("labels", [])
            custom_labels = [label for label in labels if label not in ["Entity", "Node"]]
            if not custom_labels:
                continue

            if defined_entity_types:
                matching_labels = [label for label in custom_labels if label in defined_entity_types]
                if not matching_labels:
                    continue
                entity_type = matching_labels[0]
            else:
                entity_type = custom_labels[0]

            entity_types_found.add(entity_type)
            entity = EntityNode(
                uuid=node["uuid"],
                name=node["name"],
                labels=labels,
                summary=node["summary"],
                attributes=node["attributes"],
            )

            if enrich_with_edges:
                related_edges = []
                related_node_uuids = set()
                for edge in all_edges:
                    if edge.get("source_node_uuid") == node["uuid"]:
                        related_edges.append({
                            "direction": "outgoing",
                            "edge_name": edge.get("name", ""),
                            "fact": edge.get("fact", ""),
                            "target_node_uuid": edge.get("target_node_uuid", ""),
                        })
                        related_node_uuids.add(edge.get("target_node_uuid", ""))
                    elif edge.get("target_node_uuid") == node["uuid"]:
                        related_edges.append({
                            "direction": "incoming",
                            "edge_name": edge.get("name", ""),
                            "fact": edge.get("fact", ""),
                            "source_node_uuid": edge.get("source_node_uuid", ""),
                        })
                        related_node_uuids.add(edge.get("source_node_uuid", ""))

                entity.related_edges = related_edges
                entity.related_nodes = [
                    {
                        "uuid": node_map[related_uuid]["uuid"],
                        "name": node_map[related_uuid]["name"],
                        "labels": node_map[related_uuid]["labels"],
                        "summary": node_map[related_uuid].get("summary", ""),
                    }
                    for related_uuid in related_node_uuids
                    if related_uuid in node_map
                ]

            filtered_entities.append(entity)

        logger.info(
            f"필터링 완료: 전체 노드 {total_count}, 조건 충족 {len(filtered_entities)}, 엔티티 유형: {entity_types_found}"
        )

        return FilteredEntities(
            entities=filtered_entities,
            entity_types=entity_types_found,
            total_count=total_count,
            filtered_count=len(filtered_entities),
        )

    def get_entity_with_context(self, graph_id: str, entity_uuid: str) -> Optional[EntityNode]:
        all_nodes = self.get_all_nodes(graph_id)
        node_map = {node["uuid"]: node for node in all_nodes}
        node = node_map.get(entity_uuid)
        if not node:
            return None

        edges = self.get_node_edges(graph_id, entity_uuid)
        related_edges = []
        related_node_uuids = set()
        for edge in edges:
            if edge.get("source_node_uuid") == entity_uuid:
                related_edges.append({
                    "direction": "outgoing",
                    "edge_name": edge.get("name", ""),
                    "fact": edge.get("fact", ""),
                    "target_node_uuid": edge.get("target_node_uuid", ""),
                })
                related_node_uuids.add(edge.get("target_node_uuid", ""))
            else:
                related_edges.append({
                    "direction": "incoming",
                    "edge_name": edge.get("name", ""),
                    "fact": edge.get("fact", ""),
                    "source_node_uuid": edge.get("source_node_uuid", ""),
                })
                related_node_uuids.add(edge.get("source_node_uuid", ""))

        related_nodes = [
            {
                "uuid": node_map[related_uuid]["uuid"],
                "name": node_map[related_uuid]["name"],
                "labels": node_map[related_uuid]["labels"],
                "summary": node_map[related_uuid].get("summary", ""),
            }
            for related_uuid in related_node_uuids
            if related_uuid in node_map
        ]

        return EntityNode(
            uuid=node.get("uuid", ""),
            name=node.get("name", ""),
            labels=node.get("labels", []),
            summary=node.get("summary", ""),
            attributes=node.get("attributes", {}),
            related_edges=related_edges,
            related_nodes=related_nodes,
        )

    def get_entities_by_type(
        self,
        graph_id: str,
        entity_type: str,
        enrich_with_edges: bool = True,
    ) -> List[EntityNode]:
        result = self.filter_defined_entities(
            graph_id=graph_id,
            defined_entity_types=[entity_type],
            enrich_with_edges=enrich_with_edges,
        )
        return result.entities
