"""
로컬 그래프 저장소
그래프 데이터를 JSON 파일로 저장하고 조회한다.
"""

import copy
import json
import os
import shutil
import threading
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..config import Config
from ..utils.ontology import normalize_ontology


class LocalGraphStore:
    """파일 기반 그래프 저장소"""

    GRAPH_ROOT = os.path.join(Config.UPLOAD_FOLDER, "graphs")

    _locks: Dict[str, threading.Lock] = {}
    _locks_guard = threading.Lock()

    @classmethod
    def _ensure_root(cls) -> None:
        os.makedirs(cls.GRAPH_ROOT, exist_ok=True)

    @classmethod
    def _graph_dir(cls, graph_id: str) -> str:
        cls._ensure_root()
        return os.path.join(cls.GRAPH_ROOT, graph_id)

    @classmethod
    def _graph_path(cls, graph_id: str) -> str:
        return os.path.join(cls._graph_dir(graph_id), "graph.json")

    @classmethod
    def _lock_for(cls, graph_id: str) -> threading.Lock:
        with cls._locks_guard:
            if graph_id not in cls._locks:
                cls._locks[graph_id] = threading.Lock()
            return cls._locks[graph_id]

    @staticmethod
    def _now() -> str:
        return datetime.now().isoformat()

    @staticmethod
    def _normalize_name(name: str) -> str:
        if not name:
            return ""
        normalized = "".join(ch.lower() for ch in name.strip() if ch.isalnum())
        return normalized

    @classmethod
    def _normalize_aliases(cls, aliases: Any, primary_name: str = "") -> List[str]:
        if not isinstance(aliases, list):
            return []

        normalized_primary = cls._normalize_name(primary_name)
        deduped: List[str] = []
        seen = set()

        for alias in aliases:
            if not isinstance(alias, str):
                continue

            cleaned = alias.strip()
            normalized = cls._normalize_name(cleaned)
            if not cleaned or not normalized or normalized == normalized_primary or normalized in seen:
                continue

            seen.add(normalized)
            deduped.append(cleaned)

        return deduped

    @classmethod
    def _node_name_keys(cls, node: Dict[str, Any]) -> set:
        keys = set()
        primary_name = cls._normalize_name(node.get("name", ""))
        if primary_name:
            keys.add(primary_name)

        for alias in node.get("aliases", []) or []:
            normalized = cls._normalize_name(alias)
            if normalized:
                keys.add(normalized)

        return keys

    @classmethod
    def _incoming_name_keys(cls, name: str, aliases: Optional[List[str]] = None) -> set:
        keys = set()
        primary_name = cls._normalize_name(name)
        if primary_name:
            keys.add(primary_name)

        for alias in cls._normalize_aliases(aliases or [], primary_name=name):
            normalized = cls._normalize_name(alias)
            if normalized:
                keys.add(normalized)

        return keys

    @classmethod
    def _merge_aliases(
        cls,
        existing_aliases: Any,
        incoming_aliases: Any,
        *,
        primary_name: str,
        incoming_name: str = "",
    ) -> List[str]:
        merged_input: List[str] = []

        if isinstance(existing_aliases, list):
            merged_input.extend(existing_aliases)
        if incoming_name:
            merged_input.append(incoming_name)
        if isinstance(incoming_aliases, list):
            merged_input.extend(incoming_aliases)

        return cls._normalize_aliases(merged_input, primary_name=primary_name)

    @staticmethod
    def _merge_attributes(existing: Dict[str, Any], incoming: Dict[str, Any]) -> Dict[str, Any]:
        merged = dict(existing or {})
        for key, value in (incoming or {}).items():
            if value not in [None, "", [], {}]:
                merged[key] = value
        return merged

    @staticmethod
    def _merge_summary(existing_summary: str, incoming_summary: str) -> str:
        existing_clean = (existing_summary or "").strip()
        incoming_clean = (incoming_summary or "").strip()

        if not incoming_clean:
            return existing_clean
        if not existing_clean:
            return incoming_clean
        if incoming_clean in existing_clean:
            return existing_clean
        if existing_clean in incoming_clean:
            return incoming_clean

        return incoming_clean if len(incoming_clean) > len(existing_clean) else existing_clean

    @staticmethod
    def _merge_unique_list(existing: Any, incoming: Any) -> List[Any]:
        merged: List[Any] = []
        seen = set()

        for collection in (existing or [], incoming or []):
            for item in collection if isinstance(collection, list) else [collection]:
                if item in seen:
                    continue
                seen.add(item)
                merged.append(item)

        return merged

    @staticmethod
    def _min_timestamp(*timestamps: Optional[str]) -> Optional[str]:
        values = [value for value in timestamps if value]
        return min(values) if values else None

    @staticmethod
    def _merge_end_timestamp(existing: Optional[str], incoming: Optional[str]) -> Optional[str]:
        if not existing or not incoming:
            return None
        return min(existing, incoming)

    @staticmethod
    def _custom_labels(labels: List[str]) -> List[str]:
        return [label for label in labels if label not in ["Entity", "Node"]]

    def create_graph(self, graph_id: str, name: str, description: Optional[str] = None) -> None:
        graph_dir = self._graph_dir(graph_id)
        os.makedirs(graph_dir, exist_ok=True)

        now = self._now()
        graph = {
            "graph_id": graph_id,
            "name": name,
            "description": description or "",
            "created_at": now,
            "updated_at": now,
            "ontology": None,
            "nodes": [],
            "edges": [],
            "episodes": [],
        }
        self._write_graph(graph_id, graph)

    def _read_graph(self, graph_id: str) -> Dict[str, Any]:
        graph_path = self._graph_path(graph_id)
        if not os.path.exists(graph_path):
            raise FileNotFoundError(f"그래프가 존재하지 않음: {graph_id}")

        with open(graph_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _write_graph(self, graph_id: str, graph: Dict[str, Any]) -> None:
        graph["updated_at"] = self._now()
        graph_dir = self._graph_dir(graph_id)
        os.makedirs(graph_dir, exist_ok=True)
        with open(self._graph_path(graph_id), "w", encoding="utf-8") as f:
            json.dump(graph, f, ensure_ascii=False, indent=2)

    def get_graph(self, graph_id: str) -> Dict[str, Any]:
        with self._lock_for(graph_id):
            return copy.deepcopy(self._read_graph(graph_id))

    def save_ontology(self, graph_id: str, ontology: Dict[str, Any]) -> None:
        with self._lock_for(graph_id):
            graph = self._read_graph(graph_id)
            graph["ontology"] = normalize_ontology(ontology)
            self._write_graph(graph_id, graph)

    def get_ontology(self, graph_id: str) -> Dict[str, Any]:
        graph = self.get_graph(graph_id)
        return normalize_ontology(graph.get("ontology"))

    def add_episode(
        self,
        graph_id: str,
        text: str,
        source: str = "document",
        metadata: Optional[Dict[str, Any]] = None,
        episode_id: Optional[str] = None,
        created_at: Optional[str] = None,
    ) -> Dict[str, Any]:
        episode = {
            "uuid": episode_id or f"ep_{uuid.uuid4().hex[:16]}",
            "type": "text",
            "data": text,
            "source": source,
            "processed": False,
            "created_at": created_at or self._now(),
            "metadata": metadata or {},
        }

        with self._lock_for(graph_id):
            graph = self._read_graph(graph_id)
            graph.setdefault("episodes", []).append(episode)
            self._write_graph(graph_id, graph)

        return copy.deepcopy(episode)

    def get_episode(self, graph_id: str, episode_id: str) -> Optional[Dict[str, Any]]:
        graph = self.get_graph(graph_id)
        for episode in graph.get("episodes", []):
            if episode.get("uuid") == episode_id:
                return episode
        return None

    def get_nodes(self, graph_id: str) -> List[Dict[str, Any]]:
        return self.get_graph(graph_id).get("nodes", [])

    def get_edges(self, graph_id: str) -> List[Dict[str, Any]]:
        return self.get_graph(graph_id).get("edges", [])

    def get_node(self, graph_id: str, node_uuid: str) -> Optional[Dict[str, Any]]:
        graph = self.get_graph(graph_id)
        for node in graph.get("nodes", []):
            if node.get("uuid") == node_uuid:
                return node
        return None

    def find_node_by_name(
        self,
        graph_id: str,
        name: str,
        entity_type: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        incoming_keys = self._incoming_name_keys(name)
        if not incoming_keys:
            return None

        graph = self.get_graph(graph_id)
        candidates = []
        for node in graph.get("nodes", []):
            if incoming_keys & self._node_name_keys(node):
                candidates.append(node)

        if not candidates:
            return None

        if entity_type:
            for candidate in candidates:
                if entity_type in self._custom_labels(candidate.get("labels", [])):
                    return candidate

        return candidates[0]

    def apply_extraction(
        self,
        graph_id: str,
        episode_id: str,
        extraction: Dict[str, Any],
        created_at: Optional[str] = None,
    ) -> Dict[str, int]:
        created_at = created_at or self._now()

        with self._lock_for(graph_id):
            graph = self._read_graph(graph_id)
            nodes = graph.setdefault("nodes", [])
            edges = graph.setdefault("edges", [])
            episodes = graph.setdefault("episodes", [])

            upserted_nodes: Dict[str, Dict[str, Any]] = {}
            added_nodes = 0
            added_edges = 0

            def find_existing_node(
                name: str,
                entity_type: Optional[str],
                aliases: Optional[List[str]] = None,
            ) -> Optional[Dict[str, Any]]:
                incoming_keys = self._incoming_name_keys(name, aliases)
                if not incoming_keys:
                    return None

                same_name = [
                    node for node in nodes
                    if incoming_keys & self._node_name_keys(node)
                ]
                if not same_name:
                    return None

                if entity_type:
                    for node in same_name:
                        if entity_type in self._custom_labels(node.get("labels", [])):
                            return node
                return same_name[0]

            def upsert_node(entity: Dict[str, Any]) -> Optional[Dict[str, Any]]:
                nonlocal added_nodes

                name = (entity.get("name") or "").strip()
                entity_type = (entity.get("type") or "").strip()
                if not name:
                    return None

                cache_key = f"{self._normalize_name(name)}::{entity_type.lower()}"
                if cache_key in upserted_nodes:
                    return upserted_nodes[cache_key]

                labels = ["Entity"]
                if entity_type:
                    labels.append(entity_type)

                aliases = self._normalize_aliases(entity.get("aliases") or [], primary_name=name)

                existing = find_existing_node(name, entity_type, aliases)
                if existing:
                    existing_labels = existing.get("labels", [])
                    for label in labels:
                        if label not in existing_labels:
                            existing_labels.append(label)
                    existing["labels"] = existing_labels

                    incoming_summary = (entity.get("summary") or "").strip()
                    existing_summary = (existing.get("summary") or "").strip()
                    existing["summary"] = self._merge_summary(existing_summary, incoming_summary)

                    existing["attributes"] = self._merge_attributes(
                        existing.get("attributes") or {},
                        entity.get("attributes") or {},
                    )
                    existing["aliases"] = self._merge_aliases(
                        existing.get("aliases") or [],
                        aliases,
                        primary_name=existing.get("name", ""),
                        incoming_name=name,
                    )
                    existing.setdefault("episodes", [])
                    if episode_id not in existing["episodes"]:
                        existing["episodes"].append(episode_id)
                    cache_keys = self._incoming_name_keys(name, aliases)
                    for alias_key in cache_keys:
                        upserted_nodes[f"{alias_key}::{entity_type.lower()}"] = existing
                    return existing

                node = {
                    "uuid": f"node_{uuid.uuid4().hex[:16]}",
                    "name": name,
                    "aliases": aliases,
                    "labels": labels,
                    "summary": (entity.get("summary") or "").strip(),
                    "attributes": entity.get("attributes") or {},
                    "created_at": created_at,
                    "episodes": [episode_id],
                }
                nodes.append(node)
                added_nodes += 1
                cache_keys = self._incoming_name_keys(name, aliases)
                for alias_key in cache_keys:
                    upserted_nodes[f"{alias_key}::{entity_type.lower()}"] = node
                return node

            for entity in extraction.get("entities", []):
                upsert_node(entity)

            for relation in extraction.get("relationships", []):
                source = upsert_node({
                    "name": relation.get("source_name"),
                    "type": relation.get("source_type"),
                    "summary": relation.get("source_summary", ""),
                    "attributes": relation.get("source_attributes", {}),
                })
                target = upsert_node({
                    "name": relation.get("target_name"),
                    "type": relation.get("target_type"),
                    "summary": relation.get("target_summary", ""),
                    "attributes": relation.get("target_attributes", {}),
                })
                relation_type = (relation.get("type") or "").strip()
                fact = (relation.get("fact") or "").strip()

                if not source or not target or not relation_type:
                    continue

                duplicate = next(
                    (
                        edge for edge in edges
                        if edge.get("name") == relation_type
                        and edge.get("source_node_uuid") == source.get("uuid")
                        and edge.get("target_node_uuid") == target.get("uuid")
                        and edge.get("fact") == fact
                    ),
                    None,
                )
                if duplicate:
                    duplicate.setdefault("episodes", [])
                    if episode_id not in duplicate["episodes"]:
                        duplicate["episodes"].append(episode_id)
                    duplicate["attributes"] = self._merge_attributes(
                        duplicate.get("attributes") or {},
                        relation.get("attributes") or {},
                    )
                    continue

                edges.append({
                    "uuid": f"edge_{uuid.uuid4().hex[:16]}",
                    "name": relation_type,
                    "fact": fact,
                    "fact_type": relation_type,
                    "source_node_uuid": source.get("uuid"),
                    "target_node_uuid": target.get("uuid"),
                    "attributes": relation.get("attributes") or {},
                    "created_at": created_at,
                    "valid_at": created_at,
                    "invalid_at": None,
                    "expired_at": None,
                    "episodes": [episode_id],
                })
                added_edges += 1

            summary = (extraction.get("summary") or "").strip()
            for episode in episodes:
                if episode.get("uuid") == episode_id:
                    episode["processed"] = True
                    if summary:
                        episode.setdefault("metadata", {})
                        episode["metadata"]["summary"] = summary
                    break

            self._write_graph(graph_id, graph)

        return {
            "added_nodes": added_nodes,
            "added_edges": added_edges,
        }

    def merge_nodes(
        self,
        graph_id: str,
        primary_node_uuid: str,
        duplicate_node_uuids: List[str],
    ) -> Dict[str, Any]:
        duplicates_to_merge = [
            node_uuid for node_uuid in duplicate_node_uuids
            if node_uuid and node_uuid != primary_node_uuid
        ]
        if not duplicates_to_merge:
            return {
                "primary_node_uuid": primary_node_uuid,
                "merged_node_uuids": [],
                "merged_count": 0,
                "removed_edges": 0,
            }

        with self._lock_for(graph_id):
            graph = self._read_graph(graph_id)
            nodes = graph.setdefault("nodes", [])
            edges = graph.setdefault("edges", [])
            node_map = {
                node.get("uuid"): node
                for node in nodes
                if node.get("uuid")
            }

            primary = node_map.get(primary_node_uuid)
            if not primary:
                raise ValueError(f"기준 노드를 찾을 수 없음: {primary_node_uuid}")

            primary.setdefault(
                "aliases",
                self._normalize_aliases(primary.get("aliases") or [], primary_name=primary.get("name", "")),
            )
            primary.setdefault("episodes", [])

            merged_node_uuids: List[str] = []

            for duplicate_uuid in duplicates_to_merge:
                duplicate = node_map.get(duplicate_uuid)
                if not duplicate:
                    continue

                for label in duplicate.get("labels", []) or []:
                    if label not in primary.get("labels", []):
                        primary.setdefault("labels", []).append(label)

                primary["summary"] = self._merge_summary(
                    primary.get("summary", ""),
                    duplicate.get("summary", ""),
                )
                primary["attributes"] = self._merge_attributes(
                    primary.get("attributes") or {},
                    duplicate.get("attributes") or {},
                )
                primary["aliases"] = self._merge_aliases(
                    primary.get("aliases") or [],
                    duplicate.get("aliases") or [],
                    primary_name=primary.get("name", ""),
                    incoming_name=duplicate.get("name", ""),
                )
                primary["episodes"] = self._merge_unique_list(
                    primary.get("episodes") or [],
                    duplicate.get("episodes") or [],
                )
                primary["created_at"] = self._min_timestamp(
                    primary.get("created_at"),
                    duplicate.get("created_at"),
                ) or primary.get("created_at")

                for edge in edges:
                    if edge.get("source_node_uuid") == duplicate_uuid:
                        edge["source_node_uuid"] = primary_node_uuid
                    if edge.get("target_node_uuid") == duplicate_uuid:
                        edge["target_node_uuid"] = primary_node_uuid

                merged_node_uuids.append(duplicate_uuid)

            if not merged_node_uuids:
                return {
                    "primary_node_uuid": primary_node_uuid,
                    "merged_node_uuids": [],
                    "merged_count": 0,
                    "removed_edges": 0,
                }

            graph["nodes"] = [
                node for node in nodes
                if node.get("uuid") not in set(merged_node_uuids)
            ]

            deduped_edges: List[Dict[str, Any]] = []
            edge_index: Dict[tuple, Dict[str, Any]] = {}

            for edge in edges:
                edge_key = (
                    edge.get("name", ""),
                    edge.get("source_node_uuid", ""),
                    edge.get("target_node_uuid", ""),
                    edge.get("fact", ""),
                )
                existing = edge_index.get(edge_key)
                if existing:
                    existing["attributes"] = self._merge_attributes(
                        existing.get("attributes") or {},
                        edge.get("attributes") or {},
                    )
                    existing["episodes"] = self._merge_unique_list(
                        existing.get("episodes") or [],
                        edge.get("episodes") or [],
                    )
                    existing["created_at"] = self._min_timestamp(
                        existing.get("created_at"),
                        edge.get("created_at"),
                    )
                    existing["valid_at"] = self._min_timestamp(
                        existing.get("valid_at"),
                        edge.get("valid_at"),
                    )
                    existing["invalid_at"] = self._merge_end_timestamp(
                        existing.get("invalid_at"),
                        edge.get("invalid_at"),
                    )
                    existing["expired_at"] = self._merge_end_timestamp(
                        existing.get("expired_at"),
                        edge.get("expired_at"),
                    )
                    continue

                edge_index[edge_key] = edge
                deduped_edges.append(edge)

            removed_edges = len(edges) - len(deduped_edges)
            graph["edges"] = deduped_edges
            self._write_graph(graph_id, graph)

        return {
            "primary_node_uuid": primary_node_uuid,
            "merged_node_uuids": merged_node_uuids,
            "merged_count": len(merged_node_uuids),
            "removed_edges": removed_edges,
        }

    def mark_episode_processed(
        self,
        graph_id: str,
        episode_id: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        with self._lock_for(graph_id):
            graph = self._read_graph(graph_id)
            for episode in graph.get("episodes", []):
                if episode.get("uuid") == episode_id:
                    episode["processed"] = True
                    if metadata:
                        episode.setdefault("metadata", {})
                        episode["metadata"].update(metadata)
                    break
            self._write_graph(graph_id, graph)

    def delete_graph(self, graph_id: str) -> None:
        graph_dir = self._graph_dir(graph_id)
        if os.path.exists(graph_dir):
            shutil.rmtree(graph_dir)

        with self._locks_guard:
            self._locks.pop(graph_id, None)
